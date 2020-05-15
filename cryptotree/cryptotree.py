# AUTOGENERATED! DO NOT EDIT! File to edit: nbs/05_cryptotree.ipynb (unless otherwise specified).

__all__ = ['to_list_and_duplicate', 'to_list_and_pad', 'HomomorphicModel', 'HomomorphicDecisionTree',
           'HomomorphicNeuralRandomForest', 'HomomorphicTreeEvaluator', 'HomomorphicTreeFeaturizer']

# Cell
from .seal_helper import *
from .polynomials import polyeval_tree
from .linear import arrays_to_ptx, extract_diagonals, matrix_multiply_diagonals, pad_along_axis

import tenseal.sealapi as seal

import numpy as np
import torch
from typing import List, Callable

import pickle

# Cell
def to_list_and_duplicate(array):
    """Takes an array, append a 0 then copies itself once more.

    This step is necessary to do matrix multiplication with Galois rotations.
    This is used on the bias of the comparator.
    """
    array = list(array)
    array = array + [0] + array
    return array

def to_list_and_pad(array):
    """Takes an array, append a 0 then copies itself once more.

    This step is necessary to do matrix multiplication with Galois rotations.
    This is used on the diagonal vectors.
    """
    array = list(array)
    array = array + [0] * (len(array) - 1)
    return array

# Cell
from .tree import NeuralDecisionTree

class HomomorphicModel:
    """Base class for Homormorphic Decision Trees and Random Forest.

    As the Homomorphic Evaluator will only need weights, and comparator
    for the Homomorphic Featurizer, a model should only return these two.
    """
    def return_weights(self):
        return self.b0, self.w1, self.b1, self.w2, self.b2

    def return_comparator(self) -> np.ndarray:
        """Returns the comparator, which is a numpy array of the comparator,
        with -1 indices for null values. The array is repeated for Galois
        rotations before the multiplication."""

        comparator = list(self.comparator)
        comparator = comparator + [-1] + comparator
        comparator = np.array(comparator)
        return comparator

class HomomorphicDecisionTree(HomomorphicModel):
    """Homomorphic Decision Tree, which extracts appropriate weights for
    homomorphic operations from a Neural Decision Tree."""

    def __init__(self, w0, b0, w1, b1, w2, b2):
        # We first get the comparator and set to -1 the rows that were padded
        comparator = w0
        padded_rows = (comparator.sum(axis=1) == 0)

        # We then get the indices of non padded rows
        comparator = comparator.argmax(axis=1)
        comparator[padded_rows] = -1
        self.comparator = comparator

        self.n_leaves = w1.shape[0]

        # We add a 0 then copy the initial
        self.b0 = to_list_and_duplicate(b0)

        # For weights, we first pad the columns, then extract the diagonals, and pad them
        w1 = pad_along_axis(w1, w1.shape[0], axis=1)
        w1 = extract_diagonals(w1)
        self.w1 = [to_list_and_pad(w1[i]) for i in range(len(w1))]

        self.b1 = to_list_and_pad(b1)

        self.w2 = [to_list_and_pad(w2[c]) for c in range(len(w2))]

        self.b2 = [to_list_and_pad(([b2[c] / self.n_leaves]) * self.n_leaves) for c in range(len(b2))]

    @classmethod
    def from_neural_tree(cls, neural_tree: NeuralDecisionTree):
        return cls(neural_tree.return_weights())

# Cell
from .tree import NeuralRandomForest

class HomomorphicNeuralRandomForest(HomomorphicModel):
    """"""
    def __init__(self, neural_rf: NeuralRandomForest):

        homomorphic_trees = [HomomorphicDecisionTree(w0, b0, w1, b1, w2, b2)
                             for (w0, b0, w1, b1, w2, b2) in zip(*neural_rf.return_weights())]

        B0, W1, B1, W2, B2 = [], [], [], [], []
        comparator = []

        for h in homomorphic_trees:
            b0, w1, b1, w2, b2 = h.return_weights()
            B0 += b0
            W1.append(w1)
            B1 += b1
            W2.append(w2)
            B2.append(b2)
            comparator += list(h.return_comparator())

        self.comparator = comparator

        W1 = list(np.concatenate(W1, axis=-1))
        W2 = list(np.concatenate(W2, axis=-1))
        B2 = list(np.concatenate(B2, axis=-1))

        # We will multiply each class vector with the corresponding weight for each tree
        weights = neural_rf.weights
        block_size = neural_rf.n_leaves_max * 2 - 1
        weights = [[weight.item()] * block_size for weight in weights]
        weights = np.concatenate(weights)

        W2 = [w2 * weights for w2 in W2]
        B2 = [b2 * weights for b2 in B2]

        self.b0 = B0
        self.w1 = W1
        self.b1 = B1
        self.w2 = W2
        self.b2 = B2

# Cell
from typing import List
from functools import partial
from .tree import NeuralDecisionTree

class HomomorphicTreeEvaluator:
    """Evaluator which will perform homomorphic computation"""

    def __init__(self, b0: np.ndarray, w1, b1, w2, b2,
                 activation_coeffs: List[float], polynomial_evaluator: Callable,
                 evaluator: seal.Evaluator, encoder: seal.CKKSEncoder,
                 relin_keys: seal.RelinKeys, galois_keys: seal.GaloisKeys, scale: float):
        """Initializes with the weights used during computation.

        Args:
            b0: bias of the comparison step

        """
        self.slot_count = encoder.slot_count()

        self.evaluator = evaluator
        self.encoder = encoder
        self.relin_keys = relin_keys
        self.galois_keys = galois_keys
        self.scale = scale

        self.activation = partial(polynomial_evaluator, coeffs=activation_coeffs,
                                            evaluator=evaluator, encoder=encoder,
                                            relin_keys=relin_keys, scale=scale)

        self.b0_ptx = self.to_ptx(b0)
        self.w1_ptx = [self.to_ptx(w) for w in w1]
        self.b1_ptx = self.to_ptx(b1)
        self.w2_ptx = [self.to_ptx(w) for w in w2]
        self.b2_ptx = [self.to_ptx(b) for b in b2]

    def __call__(self, ctx: seal.Ciphertext):

        # First we add the first bias to do the comparisons
        ctx = self.compare(ctx)
        ctx = self.match(ctx)
        outputs = self.decide(ctx)

        return outputs

    def compare(self, ctx: seal.Ciphertext) -> seal.Ciphertext:
        """Applies comparisons homomorphically.

        It first adds the thresholds, then compute the activation.
        """
        output = seal.Ciphertext()
        evaluator.add_plain(ctx, self.b0_ptx, output)
        output = self.activation(output)
        return output

    def match(self, ctx: seal.Ciphertext) -> seal.Ciphertext:
        """Applies matching homomorphically.

        First it does the matrix multiplication with diagonals, then activate it.
        """
        output = matrix_multiply_diagonals(self.w1_ptx, ctx, self.evaluator, self.galois_keys)

        self.evaluator.mod_switch_to_inplace(self.b1_ptx, output.parms_id())
        output.scale = self.scale
        self.evaluator.add_plain_inplace(output, self.b1_ptx)

        output = self.activation(output)
        return output

    def decide(self, ctx: seal.Ciphertext) -> seal.Ciphertext:
        """Applies the decisions homomorphically.

        For each class, multiply the ciphertext with the corresponding weight of that class and
        add the bias afterwards.
        """
        outputs = []
        for w_ptx,b_ptx in zip(self.w2_ptx, self.b2_ptx):
            output = seal.Ciphertext()

            self.evaluator.mod_switch_to_inplace(w_ptx, ctx.parms_id())

            self.evaluator.multiply_plain(ctx, w_ptx, output)
            self.evaluator.rescale_to_next_inplace(output)

            evaluator.mod_switch_to_inplace(b_ptx, output.parms_id())
            output.scale = self.scale

            evaluator.add_plain_inplace(output, b_ptx)
            outputs.append(output)
        return outputs

    def to_ptx(self, array):
        """Pads an array and convert it to a plaintext"""
        array = list(array)

        ptx = seal.Plaintext()
        self.encoder.encode(array, self.scale, ptx)
        return ptx

    @classmethod
    def from_model(cls, model: HomomorphicModel,
                  activation_coeffs: List[float], polynomial_evaluator: Callable,
                  evaluator: seal.Evaluator, encoder: seal.CKKSEncoder,
                  relin_keys: seal.RelinKeys, galois_keys: seal.GaloisKeys, scale: float):
        """Creates an Homomorphic Tree Evaluator from a model, i.e a neural tree or
        a neural random forest. """
        b0, w1, b1, w2, b2 = model.return_weights()

        return cls(b0, w1, b1, w2, b2, activation_coeffs, polynomial_evaluator,
                   evaluator, encoder, relin_keys, galois_keys, scale)

# Cell
class HomomorphicTreeFeaturizer:
    """Featurizer used by the client to encode and encrypt data."""
    def __init__(self, comparator: np.ndarray,
                 encoder: seal.CKKSEncoder, encryptor: seal.Encryptor, scale: float):
        self.comparator = comparator
        self.encryptor = encryptor
        self.encoder = encoder
        self.scale = scale

    def encrypt(self, x: np.ndarray):
        features = x[self.comparator]
        features[self.comparator == -1] = 0
        features = list(features)

        ptx = seal.Plaintext()
        encoder.encode(features, scale, ptx)

        ctx = seal.Ciphertext()
        encryptor.encrypt(ptx, ctx)
        return ctx

    def save(self, path:str):
        pickle.dump(self.comparator, open(path, "wb"))