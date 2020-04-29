# AUTOGENERATED! DO NOT EDIT! File to edit: nbs/05_cryptotree.ipynb (unless otherwise specified).

__all__ = ['HomomorphicTreeEvaluator', 'HomomorphicDecisionTree']

# Cell
from .seal_helper import *
from .polynomials import polyeval_tree
from seal import *

import numpy as np
import torch
from typing import List, Callable

# Cell
from typing import List
from functools import partial
from .polynomials import polyeval_tree

class HomomorphicTreeEvaluator:
    """Evaluator which will perform homomorphic computation"""

    def __init__(self, b0: np.ndarray, w1, b1, w2, b2,
                 max_leaves: int, n_trees: int,
                 activation_coeffs: List[float], polynomial_evaluator: Callable,
                 evaluator: Evaluator, encoder: CKKSEncoder,
                 relin_keys: RelinKeys, galois_keys: GaloisKeys, scale: float):
        """Initializes with the weights used during computation.

        Args:
            b0: bias of the comparison step

        """
        self.slot_count = encoder.slot_count()
        self.max_leaves = max_leaves
        self.block_size = 2 * max_leaves - 1
        self.n_trees = n_trees

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

    def __call__(self, ctx: Ciphertext):

        # First we add the first bias to do the comparisons
        ctx = self.compare(ctx)
        ctx = self.match(ctx)
        outputs = self.decide(ctx)

        return outputs

    def compare(self, ctx: Ciphertext):
        evaluator.add_plain_inplace(ctx, self.b0_ptx)
        ctx = self.activation(ctx)
        return ctx

    def match(self, ctx: Ciphertext):
        ctx = matrix_multiply_diagonals(self.w1_ptx, ctx, self.evaluator, self.galois_keys)

        self.evaluator.mod_switch_to_inplace(self.b1_ptx, ctx.parms_id())
        ctx.scale(self.scale)
        self.evaluator.add_plain_inplace(ctx, self.b1_ptx)

        ctx = self.activation(ctx)
        return ctx

    def decide(self, ctx: Ciphertext):
        outputs = []
        for w_ptx,b_ptx in zip(self.w2_ptx, self.b2_ptx):
            output = Ciphertext()

            self.evaluator.mod_switch_to_inplace(w_ptx, ctx.parms_id())

            self.evaluator.multiply_plain(ctx, w_ptx, output)
            self.evaluator.rescale_to_next_inplace(output)

            evaluator.mod_switch_to_inplace(b_ptx, output.parms_id())
            output.scale(scale)

            evaluator.add_plain_inplace(output, b_ptx)
            outputs.append(output)
        return outputs

    def to_ptx(self, array):
        """Pads an array and convert it to a plaintext"""
        array = DoubleVector(list(array))

        ptx = Plaintext()
        self.encoder.encode(array, self.scale, ptx)
        return ptx

    @classmethod
    def from_tree(cls, tree: DecisionTree,
                  activation_coeffs: List[float], polynomial_evaluator: Callable,
                  evaluator: Evaluator, encoder: CKKSEncoder,
                  relin_keys: RelinKeys, galois_keys: GaloisKeys, scale: float):
        htree = HomomorphicDecisionTree(tree)

        b0, w1, b1, w2, b2 = htree.return_weights()

        max_leaves = tree.matcher.weight.data.shape[0]
        n_trees = 1

        return cls(b0, w1, b1, w2, b2, max_leaves,
                   n_trees, activation_coeffs, polynomial_evaluator,
                   evaluator, encoder, relin_keys, galois_keys, scale)

# Cell
from .tree import DecisionTree

class HomomorphicDecisionTree:
    """Extracts the weights from a decision tree."""
    def __init__(self, tree: DecisionTree):
        comparator = tree.comparator
        matcher = tree.matcher
        head = tree.head

        self.n_leaves = matcher.weight.data.shape[0]

        b0 = comparator.bias.data.numpy()
        self.b0 = self.to_list_and_duplicate(b0)

        w1 = matcher.weight.data.numpy()
        w1 = pad_along_axis(w1, w1.shape[0], axis=1)
        w1 = extract_diagonals(w1)
        self.w1 = [self.to_list_and_pad(w1[i]) for i in range(len(w1))]

        b1 = matcher.bias.data.numpy()
        self.b1 = self.to_list_and_pad(b1)

        w2 = head.weight.data.numpy()
        self.w2 = [self.to_list_and_pad(w2[c]) for c in range(len(w2))]

        b2 = head.bias.data.numpy()
        self.b2 = [self.to_list_and_pad(([b2[c] / self.n_leaves]) * self.n_leaves) for c in range(len(b2))]

    def return_weights(self):
        return self.b0, self.w1, self.b1, self.w2, self.b2

    @staticmethod
    def to_list_and_duplicate(array):
        """Takes an array, append a 0 then copies itself once more.

        This step is necessary to do matrix multiplication with Galois rotations.
        """
        array = list(array)
        array = array + [0] + array
        return array

    @staticmethod
    def to_list_and_pad(array):
        """Takes an array, append a 0 then copies itself once more.

        This step is necessary to do matrix multiplication with Galois rotations.
        """
        array = list(array)
        array = array + [0] * (len(array) - 1)
        return array