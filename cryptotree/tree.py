# AUTOGENERATED! DO NOT EDIT! File to edit: nbs/01_tree.ipynb (unless otherwise specified).

__all__ = ['NeuralTreeMaker', 'NeuralDecisionTree', 'DEFAULT_POLYNOMIAL_DEGREE', 'DEFAULT_DILATATION_FACTOR',
           'DEFAULT_BOUND', 'raise_error_wrong_tree', 'SigmoidTreeMaker', 'TanhTreeMaker', 'check_output_range',
           'register_output_check', 'pad_tensor', 'pad_neural_tree', 'NeuralRandomForest']

# Cell
import numpy as np

from typing import List
import torch.nn as nn
import torch

from sklearn.tree import BaseDecisionTree
from functools import partial

# Cell
from sklearn.tree import BaseDecisionTree
from sklearn.base import is_classifier

from typing import Callable
from numpy.polynomial.chebyshev import Chebyshev
from numpy.polynomial import Polynomial
from .activations import create_linear_node_comparator

DEFAULT_POLYNOMIAL_DEGREE = 16
DEFAULT_DILATATION_FACTOR = 16
DEFAULT_BOUND = 1.0

class NeuralTreeMaker:
    """Base class of Neural Decision Trees."""
    def __init__(self,
                 activation: Callable,
                 create_linear_leaf_matcher: Callable,
                 create_regression_head: Callable,
                 create_classifier_head: Callable,
                 dilatation_factor : float = DEFAULT_DILATATION_FACTOR,
                 use_polynomial : bool = False,
                 polynomial_degree : int = DEFAULT_POLYNOMIAL_DEGREE, bound: float = DEFAULT_BOUND):

        activation_fn = lambda x: activation(x * dilatation_factor)
        if use_polynomial:
            domain = [-bound, bound]
            activation_fn_numpy = lambda x: activation_fn(torch.tensor(x))
            self.activation = Chebyshev.interpolate(activation_fn_numpy,deg=polynomial_degree,domain=domain)
            self.coeffs = Polynomial.cast(self.activation).coef
        else:
            self.activation = activation_fn
            self.coeffs = None

        self.create_linear_leaf_matcher = create_linear_leaf_matcher
        self.create_regression_head = create_regression_head
        self.create_classifier_head = create_classifier_head

    def make_tree(self, tree: BaseDecisionTree):
        if is_classifier(tree):
            create_head = self.create_classifier_head
        else:
            create_head = self.create_regression_head
        neural_tree = NeuralDecisionTree(tree, self.activation, self.create_linear_leaf_matcher, create_head)
        return neural_tree

class NeuralDecisionTree(nn.Module):
    """Base class of Neural Decision Trees."""
    def __init__(self, tree: BaseDecisionTree,
                 activation: Callable,
                 create_linear_leaf_matcher: Callable,
                 create_head: Callable):
        super(NeuralDecisionTree, self).__init__()

        self.activation = activation

        self.comparator = create_linear_node_comparator(tree)
        self.matcher = create_linear_leaf_matcher(tree)

        self.head = create_head(tree)

    def forward(self,x):
        comparisons = self.comparator(x)
        comparisons = self.activation(comparisons)

        matches = self.matcher(comparisons)
        matches = self.activation(matches)

        output = self.head(matches)

        return output


# Cell
from .activations import sigmoid_linear_leaf_matcher, sigmoid_classification_head

def raise_error_wrong_tree(*args,**kwargs):
    raise Exception("Wrong supervised tree used")

class SigmoidTreeMaker(NeuralTreeMaker):
    def __init__(self, dilatation_factor : float = DEFAULT_DILATATION_FACTOR,
                 use_polynomial : bool = False,
                 polynomial_degree : int = DEFAULT_POLYNOMIAL_DEGREE, bound: float = DEFAULT_BOUND, eps=0.5):

        activation = torch.sigmoid
        create_linear_leaf_matcher = partial(sigmoid_linear_leaf_matcher,eps=eps)
        create_classifier_head = sigmoid_classification_head
        create_regression_head = raise_error_wrong_tree

        super().__init__(activation,
                 create_linear_leaf_matcher,
                 create_regression_head,
                 create_classifier_head,
                 dilatation_factor,
                 use_polynomial,
                 polynomial_degree)

# Cell
from .activations import tanh_linear_leaf_matcher, tanh_classification_head

class TanhTreeMaker(NeuralTreeMaker):
    def __init__(self, dilatation_factor : float = DEFAULT_DILATATION_FACTOR,
                 use_polynomial : bool = False,
                 polynomial_degree : int = DEFAULT_POLYNOMIAL_DEGREE, bound: float = DEFAULT_BOUND, eps=0.5):

        activation = torch.tanh
        create_linear_leaf_matcher = partial(tanh_linear_leaf_matcher,eps=eps)
        create_classifier_head = tanh_classification_head
        create_regression_head = raise_error_wrong_tree

        super().__init__(activation,
                 create_linear_leaf_matcher,
                 create_regression_head,
                 create_classifier_head,
                 dilatation_factor,
                 use_polynomial,
                 polynomial_degree)

# Cell
def check_output_range(m, i, o, threshold=1):
    rows_outside_range = ((torch.abs(o) > threshold).float().sum(dim=1) > 0).numpy()
    idx_outside_range = np.arange(len(rows_outside_range))[rows_outside_range]

    assert len(idx_outside_range) == 0, f"""Out of range outputs for module {m}: \n
    {idx_outside_range} \n
    Rows with outside range : \n
    {o.numpy()[idx_outside_range]}"""

def register_output_check(model, threshold=1):
    for c in model.children():
        if isinstance(c,nn.Linear):
            hook = partial(check_output_range, threshold=threshold)
            c.register_forward_hook(hook)

# Cell
def pad_tensor(tensor, target, dim=0, value=0):
    # If the tensor is already at the target size we return it
    if tensor.shape[dim] >= target:
        return tensor
    else:
        shape = list(tensor.shape)
        shape[dim] = target - tensor.shape[dim]

        padding = torch.ones(shape) * value
        output = torch.cat([tensor,padding], dim=dim)
        return output

def pad_neural_tree(neural_tree, n_nodes_max, n_leaves_max):
    w0, b0 = neural_tree.comparator.weight.data.clone(), neural_tree.comparator.bias.data.clone()

    # First we pad the output size of the comparator
    neural_tree.comparator = nn.Linear(w0.shape[1], n_nodes_max)
    neural_tree.comparator.weight.data = pad_tensor(w0, n_nodes_max, dim=0)
    neural_tree.comparator.bias.data = pad_tensor(b0, n_nodes_max, dim=0)

    w1, b1 = neural_tree.matcher.weight.data.clone(), neural_tree.matcher.bias.data.clone()
    # Then we pad the output and the input size of the matcher
    neural_tree.matcher = nn.Linear(n_nodes_max, n_leaves_max)
    neural_tree.matcher.weight.data = pad_tensor(pad_tensor(w1, n_nodes_max, dim=1), n_leaves_max, dim=0)
    neural_tree.matcher.bias.data = pad_tensor(b1, n_leaves_max, dim=0)

    w2, b2 = neural_tree.head.weight.data.clone(), neural_tree.head.bias.data.clone()
    neural_tree.head = nn.Linear(n_leaves_max, w2.shape[0])
    neural_tree.head.weight.data = pad_tensor(w2, n_leaves_max, dim =1)
    neural_tree.head.bias.data = b2

# Cell
class NeuralRandomForest(nn.Module):
    def __init__(self, trees: List[BaseDecisionTree],
                 tree_maker: NeuralTreeMaker,
                 weights: torch.Tensor = None, trainable_weights:bool = False,
                 bias: torch.Tensor = None, trainable_bias:bool = False):

        super(NeuralRandomForest, self).__init__()

        self.n_trees = len(trees)
        self.activation = tree_maker.activation

        # First we need to create the neural trees
        neural_trees = []
        n_nodes = []
        n_leaves = []
        for tree in trees:
            neural_tree = tree_maker.make_tree(tree)
            n_nodes.append(neural_tree.comparator.weight.data.shape[0])
            n_leaves.append(neural_tree.matcher.weight.data.shape[0])
            neural_trees.append(neural_tree)

        # Then we pad our neural trees according to the biggest tree in the forest
        n_nodes_max = max(n_nodes)
        n_leaves_max = max(n_leaves)

        for neural_tree in neural_trees:
            pad_neural_tree(neural_tree, n_nodes_max, n_leaves_max)

        self.neural_trees = neural_trees

        # Then we create the parameters for the Neural Random Forest
        comparators = [neural_tree.comparator.weight.data.unsqueeze(-1) for neural_tree in neural_trees]
        comparator = torch.cat(comparators, dim=-1)
        comparator = comparator.permute(1,0,2)
        comparator = nn.Parameter(comparator)
        self.register_parameter("comparator", comparator)

        comparator_bias = [neural_tree.comparator.bias.data.unsqueeze(-1) for neural_tree in neural_trees]
        comparator_bias = torch.cat(comparator_bias, dim=-1)
        comparator_bias = nn.Parameter(comparator_bias)
        self.register_parameter("comparator_bias", comparator_bias)

        matchers = [neural_tree.matcher.weight.data.unsqueeze(-1) for neural_tree in neural_trees]
        matcher = torch.cat(matchers, dim=-1)
        matcher = nn.Parameter(matcher)
        self.register_parameter("matcher", matcher)

        matcher_bias = [neural_tree.matcher.bias.data.unsqueeze(-1) for neural_tree in neural_trees]
        matcher_bias = torch.cat(matcher_bias, dim=-1)
        matcher_bias = nn.Parameter(matcher_bias)
        self.register_parameter("matcher_bias",matcher_bias)

        heads = [neural_tree.head.weight.data.unsqueeze(-1) for neural_tree in neural_trees]
        head = torch.cat(heads, dim=-1)
        head = nn.Parameter(head)
        self.register_parameter("head", head)

        head_bias = [neural_tree.head.bias.data.unsqueeze(-1) for neural_tree in neural_trees]
        head_bias = torch.cat(head_bias, dim=-1)
        head_bias = nn.Parameter(head_bias)
        self.register_parameter("head_bias", head_bias)

        if not torch.is_tensor(weights):
            weights = torch.ones(self.n_trees) * (1. / self.n_trees)

        if trainable_weights:
            weights = nn.Parameter(weights)
            self.register_parameter("weights", weights)
        else:
            self.register_buffer("weights", weights)

        if not torch.is_tensor(bias):
            c = neural_tree.head.weight.data.shape[0]
            bias = torch.zeros(c)

        if trainable_bias:
            bias = nn.Parameter(bias)
            self.register_parameter("bias",bias)
        else:
            self.register_buffer("bias",bias)

    def forward(self, x):
        comparisons = torch.einsum("kj,jil->kil",x,self.comparator) + self.comparator_bias.unsqueeze(0)
        comparisons = self.activation(comparisons)

        matches = torch.einsum("kjl,ijl->kil",comparisons, self.matcher) + self.matcher_bias
        matches = self.activation(matches)

        outputs = torch.einsum("kjl,cjl->kcl",matches,self.head) + self.head_bias
        outputs = (outputs * self.weights.expand_as(outputs)).sum(dim=-1)
        outputs = outputs + self.bias.expand_as(outputs)

        return outputs