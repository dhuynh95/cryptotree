# AUTOGENERATED! DO NOT EDIT! File to edit: nbs/03_polynomials.ipynb (unless otherwise specified).

__all__ = ['chebyshev_approximation', 'polynomial_approximation_coefficients', 'plot_graph_function_approximation',
           'coeffs_to_plaintext', 'compute_all_powers', 'multiply_and_add_coeffs', 'polyeval_tree', 'eval_polynomial',
           'test_polynomial']

# Cell
import tenseal.sealapi as seal
import numpy as np
from numpy.polynomial import Polynomial
from numpy.polynomial.chebyshev import Chebyshev

import matplotlib.pyplot as plt
import torch

from typing import List, Union

# Cell
def chebyshev_approximation(f, dilatation_factor=50, polynomial_degree=25, bound=1, convertToTensor=True):
    """Polynomial approximation of f using Chebyshev approximation."""
    if convertToTensor:
        f_a = lambda x: f(torch.tensor(x*dilatation_factor))
    else:
        f_a = lambda x: f(x*dilatation_factor)

    domain = [-bound,bound]

    p = Chebyshev.interpolate(f_a,deg=polynomial_degree,domain=domain)
    return p, f_a

def polynomial_approximation_coefficients(f, dilatation_factor=50, polynomial_degree=25,
                                          bound=1, convertToTensor=True):
    """Returns the coefficient of the polynomial approximation of f
    in the canonical basis."""
    p,_ = chebyshev_approximation(f, dilatation_factor, polynomial_degree, bound, convertToTensor)

    return Polynomial.cast(p).coef

def plot_graph_function_approximation(f, dilatation_factor=50, polynomial_degree=25, bound=1, convertToTensor=True):
    """Provides visualization of polynomial approximation."""

    p, f_a = chebyshev_approximation(f, dilatation_factor, polynomial_degree, bound, convertToTensor)

    domain = [-bound,bound]
    x = np.linspace(*domain,100)
    y = f_a(x)
    pred = p(x)

    fig, ax = plt.subplots()

    # plot the function
    ax.plot(x,y, 'g', label="Sigmoid")
    ax.plot(x,pred,"b-", label=f"Polynomial approximation")
    ax.legend()

    # show the plot
    fig.suptitle(f"Tchebytchev polynomials with expansion a={dilatation_factor} and degree n={polynomial_degree}")
    fig.show()

    return fig,ax

# Cell
def coeffs_to_plaintext(coeffs: List[float], encoder: seal.CKKSEncoder, scale: float) -> List[seal.Plaintext]:
    """Computes the plaintext encodings of coefficients"""
    plain_coeffs = []

    for coef in coeffs:
        plain_coeff = seal.Plaintext()
        encoder.encode(coef, scale, plain_coeff)
        plain_coeffs.append(plain_coeff)

    return plain_coeffs

def compute_all_powers(ctx : seal.Ciphertext, degree: int, evaluator: seal.Evaluator,
                       relin_keys: seal.RelinKeys, verbose=False) -> List[seal.Ciphertext]:
    """Computes all powers of a given ciphertext"""
    powers = [None] * (degree+1)
    levels = np.zeros(degree+1)

    powers[1] = ctx
    levels[0] = levels[1] = 0


    for i in range(2,degree+1):

        minlevel = i
        cand = -1

        for j in range(1, i // 2 +1):
            k = i - j
            newlevel = max(levels[k],levels[j]) + 1
            if newlevel < minlevel:
                cand = j
                minlevel = newlevel

        if verbose:
            print(f"i = {i}, i-cand = {i-cand}")
            print(f"level for cand : {levels[cand]}, level for {i-cand} : {levels[i-cand]}")
            print(f"minlevel = {minlevel}")
            print(f"cand = {cand}")

        levels[i] = minlevel

        temp = seal.Ciphertext()

        power_cand = powers[cand]
        evaluator.mod_switch_to(power_cand, powers[i-cand].parms_id(),temp)
        evaluator.multiply(temp, powers[i-cand], temp)
        evaluator.relinearize_inplace(temp, relin_keys)
        evaluator.rescale_to_next_inplace(temp)

        powers[i] = temp

    return powers

# Cell
from typing import List, Union

def multiply_and_add_coeffs(powers: List[seal.Ciphertext], plain_coeffs: List[seal.Plaintext],
                            coeffs: List[float],
                            evaluator: seal.Evaluator,
                            scale: float,
                            tol=1e-6) -> Union[seal.Ciphertext]:
    assert len(powers) == len(plain_coeffs), f"Mismatch between length between powers {len(powers)} and coeffs {len(coeffs)}"

    """Multiplies the coefficients with the corresponding powers andd adds everything.

    If the polynomial is non-constant, returns the ciphertext of the polynomial evaluation.
    Else if the polynomials is constant, the plaintext of the constant term is returned.
    """
    output = seal.Ciphertext()
    a0 = plain_coeffs[0]
    a0_added = False

    temp = seal.Ciphertext()

    for i in range(1, len(plain_coeffs)):
        # We first check if the coefficient is not too small otherwise we skip it
        coef = coeffs[i]
        if np.abs(coef) < tol:
            continue

        plain_coeff = plain_coeffs[i]
        power = powers[i]

        evaluator.mod_switch_to_inplace(plain_coeff, power.parms_id())

        evaluator.multiply_plain(power, plain_coeff, temp)
        evaluator.rescale_to_next_inplace(temp)

        if not a0_added:
            evaluator.mod_switch_to_inplace(a0, temp.parms_id())

            temp.scale = scale
            evaluator.add_plain(temp, a0, output)
            a0_added = True
        else:
            evaluator.mod_switch_to_inplace(output, temp.parms_id())
            # We rescale both to the same scale
            output.scale = scale
            temp.scale = scale
            evaluator.add_inplace(output, temp)
    if a0_added:
        return output
    else:
        return a0

# Cell
def polyeval_tree(ctx : seal.Ciphertext, coeffs: List[float],
                  evaluator: seal.Evaluator, encoder : seal.Encryptor,
                  relin_keys: seal.RelinKeys,
                  scale: float):

    degree = len(coeffs) - 1
    plain_coeffs = coeffs_to_plaintext(coeffs, encoder, scale)
    powers = compute_all_powers(ctx, degree, evaluator, relin_keys)
    output = multiply_and_add_coeffs(powers, plain_coeffs, coeffs, evaluator, scale)

    return output

# Cell
from fastcore.test import test_close

def eval_polynomial(x: float, coeffs):
    output = 0.
    for power,coeff in enumerate(coeffs):
        output += coeff * (x ** power)
    return output

def test_polynomial(x: float, coeffs, evaluator, encoder, encryptor, decryptor, relin_keys, scale, eps=1e-2):
    """Tests if the output of the polynomial, defined by the coeffs, is the same
    between the homomorphic evaluation and the regular one"""

    ptx = seal.Plaintext()
    encoder.encode(x, scale, ptx)

    ctx = seal.Ciphertext()
    encryptor.encrypt(ptx, ctx)

    output = polyeval_tree(ctx, coeffs, evaluator, encoder, relin_keys, scale)
    decryptor.decrypt(output, ptx)

    values = encoder.decode_double(ptx)

    homomorphic_output = values[0]
    expected_output = eval_polynomial(x, coeffs)

    test_close(homomorphic_output, expected_output, eps)