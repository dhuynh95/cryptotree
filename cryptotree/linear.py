# AUTOGENERATED! DO NOT EDIT! File to edit: nbs/04_linear.ipynb (unless otherwise specified).

__all__ = ['pad_along_axis', 'arrays_to_ptx', 'extract_diagonals', 'matrix_multiply_diagonals', 'sum_reduce',
           'dot_product_plain', 'test_sum', 'test_dot_product_plain']

# Cell
import numpy as np
import tenseal.sealapi as seal
from typing import List

# Cell
def pad_along_axis(array: np.ndarray, target_length, axis=0):
    """Pads an array to a given target length, on a given axis."""
    pad_size = target_length - array.shape[axis]
    axis_nb = len(array.shape)

    if pad_size <= 0:
        return array

    npad = [(0, 0) for x in range(axis_nb)]
    npad[axis] = (0, pad_size)

    b = np.pad(array, pad_width=npad, mode='constant', constant_values=0)

    return b

# Cell
def arrays_to_ptx(arrays: List[np.ndarray], encoder: seal.CKKSEncoder, scale: float) -> List[seal.Plaintext]:
    """Converts an array of arrays to an array of plaintexts."""
    outputs = []
    for array in arrays:
        ptx = seal.Plaintext()
        encoder.encode(DoubleVector(list(array)), scale, ptx)
        outputs.append(ptx)
    return outputs

# Cell
def extract_diagonals(matrix: np.ndarray) -> List[np.ndarray]:
    """Extracts the diagonals of the matrix"""
    assert matrix.shape[0] == matrix.shape[1], "Non square matrix"
    dim = matrix.shape[0]

    diagonals = []

    for i in range(dim):
        diagonal = []
        for j in range(dim):
            diagonal.append(matrix[j][(j+i) % dim])
        diagonal = np.array(diagonal)
        diagonals.append(diagonal)
    return diagonals

# Cell
def matrix_multiply_diagonals(diagonals: List[seal.Plaintext], ctx: seal.Ciphertext,
                              evaluator: seal.Evaluator, galois_keys: seal.GaloisKeys):
    output = seal.Ciphertext()

    for i in range(len(diagonals)):

        temp = seal.Ciphertext()
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

# Cell
def sum_reduce(ctx: seal.Ciphertext, evaluator: seal.Evaluator,
               galois_keys: seal.GaloisKeys, n_slot: int):
    """Sums all the coefficients of the ciphertext, supposing that coefficients up to n_slot
    are non zero. The first coefficient of the output will then be the sum of the coefficients."""
    n = int(np.ceil(np.log2(n_slot)))

    temp = seal.Ciphertext()
    output = seal.Ciphertext()

    for i in range(n):
        if i == 0:
            evaluator.rotate_vector(ctx, 2**i, galois_keys, temp)
            evaluator.add(ctx, temp, output)
        else:
            evaluator.rotate_vector(output, 2**i, galois_keys, temp)
            evaluator.add_inplace(output, temp)
    return output

def dot_product_plain(ctx: seal.Ciphertext, ptx: seal.Plaintext,
                      evaluator: seal.Evaluator, galois_keys: seal.GaloisKeys, n_slot: int):
    """Computes the dot product between a ciphertext and a plaintext"""
    output = seal.Ciphertext()

    evaluator.multiply_plain(ctx, ptx, output)
    output = sum_reduce(output, evaluator, galois_keys, n_slot)

    return output

# Cell
from fastcore.test import test_close

def test_sum(x: List[float], evaluator, encoder, encryptor, decryptor, scale, eps=1e-2):
    """Tests if the output of the polynomial, defined by the coeffs, is the same
    between the homomorphic evaluation and the regular one"""
    n_slot = len(x)

    ptx = seal.Plaintext()
    encoder.encode(x, scale, ptx)

    ctx = seal.Ciphertext()
    encryptor.encrypt(ptx, ctx)

    output = sum_reduce(ctx, evaluator, galois_keys, n_slot)
    decryptor.decrypt(output, ptx)

    values = encoder.decode_double(ptx)

    homomorphic_output = values[0]
    expected_output = np.sum(x)

    test_close(homomorphic_output, expected_output, eps)

def test_dot_product_plain(x: List[float], y: List[float],
                           evaluator, encoder, encryptor, decryptor,
                           galois_keys,
                           scale, eps=1e-2):
    """Tests if the output of the polynomial, defined by the coeffs, is the same
    between the homomorphic evaluation and the regular one"""
    assert len(x) == len(y), f"x and y must have same length {len(x)} != {len(y)}"
    n_slot = len(x)

    ptx = seal.Plaintext()
    encoder.encode(x, scale, ptx)

    ctx = seal.Ciphertext()
    encryptor.encrypt(ptx, ctx)

    pty = seal.Plaintext()
    encoder.encode(y, scale, pty)

    output = dot_product_plain(ctx, pty, evaluator, galois_keys, n_slot)
    decryptor.decrypt(output, ptx)

    values = encoder.decode_double(ptx)

    homomorphic_output = values[0]
    expected_output = np.dot(x, y)

    test_close(homomorphic_output, expected_output, eps)