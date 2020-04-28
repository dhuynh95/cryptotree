# AUTOGENERATED! DO NOT EDIT! File to edit: nbs/04_cryptotree.ipynb (unless otherwise specified).

__all__ = ['HomomorphicTreeEvaluator', 'extract_diagonals', 'matrix_multiply_diagonals', 'add_bias_ptx', 'LinearCtx',
           'pad_along_axis']

# Cell
from typing import List

class HomomorphicTreeEvaluator:
    """Evaluator which will perform homomorphic computation"""

    def __init__(self, b0: np.ndarray, w1, b1, w2, b2,
                 slot_count: int, max_leaves: int, n_trees: int
                 activation_coeffs: List[float],
                 evaluator: Evaluator, encoder: CKKSEncoder,
                 relin_keys: RelinKeys, galois_keys: GaloisKeys):
        """Initializes with the weights used during computation.

        Args:
            b0: bias of the comparison step

        """
        self.slot_count = slot_count
        self.max_leaves = max_leaves
        self.block_size = 2 * max_leaves - 1
        self.n_trees = n_trees

        self.evaluator = evaluator
        self.encoder = encoder
        self.relin_keys = relin_keys
        self.galois_keys = galois_keys

    def __call__(self, ctx: Ciphertext):
        b0 = DoubleVector(list(self.b0))
        b0_ptx = Plaintext()

        # First we add the first bias to do the comparisons
        evaluator.add_plain_inplace(ctx, b0_ptx)
        ctx =

# Cell
def extract_diagonals(matrix: np.ndarray, encoder: CKKSEncoder) -> List[Plaintext]:
    """Extracts the diagonals of the matrix"""
    assert matrix.shape[0] == matrix.shape[1], "Non square matrix"
    dim = matrix.shape[0]

    diagonals = []

    for i in range(dim):
        diagonal = []
        for j in range(dim):
            diagonal.append(matrix[j][(j+i) % dim])
        diagonal_ptx = Plaintext()
        encoder.encode(DoubleVector(diagonal), scale, diagonal_ptx)
        diagonals.append(diagonal_ptx)
    return diagonals

# Cell
def matrix_multiply_diagonals(diagonals: List[Plaintext], ctx: Ciphertext,
                              evaluator: Evaluator, galois_keys: GaloisKeys):
    output = Ciphertext()

    for i in range(len(diagonals)):

        temp = Ciphertext()
        diagonal = diagonals[i]

        evaluator.rotate_vector(ctx, i, galois_keys, temp)

        evaluator.mod_switch_to_inplace(diagonal, temp.parms_id())
        evaluator.multiply_plain_inplace(temp, diagonal)
        evaluator.rescale_to_next_inplace(temp)

        if i == 0:
            output = temp
        else:
            evaluator.add_inplace(output, temp)

    return output

def add_bias_ptx(bias: np.ndarray, ctx: Ciphertext, evaluator: Evaluator):
    bias = DoubleVector(list(bias))
    bias_ptx = Plaintext()
    encoder.encode(bias, scale, bias_ptx)

    evaluator.mod_switch_to_inplace(bias_ptx, ctx.parms_id())
    ctx.scale(scale)

    output = Ciphertext()
    evaluator.add_plain(ctx, bias_ptx, output)
    return output

class LinearCtx():
    def __init__(self, matrix, bias):
        self.diagonals = extract_diagonals(matrix)
        self.bias = bias

    def __call__(self, ctx):
        pass

# Cell
def pad_along_axis(array: np.ndarray, target_length, axis=0):

    pad_size = target_length - array.shape[axis]
    axis_nb = len(array.shape)

    if pad_size <= 0:
        return array

    npad = [(0, 0) for x in range(axis_nb)]
    npad[axis] = (0, pad_size)

    b = np.pad(array, pad_width=npad, mode='constant', constant_values=0)

    return b