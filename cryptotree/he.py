# AUTOGENERATED! DO NOT EDIT! File to edit: nbs/homomorphic_tree.ipynb (unless otherwise specified).

__all__ = ['print_vector', 'ptx_value', 'ctx_value', 'print_ctx', 'print_ptx', 'chebyshev_approximation',
           'polynomial_approximation_coefficients', 'plot_graph_function_approximation', 'coeffs_to_plaintext',
           'compute_all_powers', 'multiply_and_add_coeffs', 'apply_comparator', 'vrep', 'extract_diagonals',
           'print_range_ctx', 'print_range_ptx']

# Cell
from numpy.polynomial import Polynomial
import matplotlib.pyplot as plt
import torch
from numpy.polynomial.chebyshev import Chebyshev

def print_vector(vec, print_size=4, prec=3):
    slot_count = len(vec)
    print()
    if slot_count <= 2*print_size:
        print("    [", end="")
        for i in range(slot_count):
            print(" " + (f"%.{prec}f" % vec[i]) + ("," if (i != slot_count - 1) else " ]\n"), end="")
    else:
        print("    [", end="")
        for i in range(print_size):
            print(" " + (f"%.{prec}f" % vec[i]) + ",", end="")
        if len(vec) > 2*print_size:
            print(" ...,", end="")
        for i in range(slot_count - print_size, slot_count):
            print(" " + (f"%.{prec}f" % vec[i]) + ("," if (i != slot_count - 1) else " ]\n"), end="")
    print()

def ptx_value(ptx, i=0):
    result = DoubleVector()
    encoder.decode(ptx,result)
    value = result[i]
    return value

def ctx_value(ctx, i=0):
    ptx = Plaintext()
    decryptor.decrypt(ctx, ptx)
    value = ptx_value(ptx,i)
    return value

def print_ctx(ctx):
    ptx = Plaintext()
    decryptor.decrypt(ctx, ptx)
    result = DoubleVector()
    encoder.decode(ptx,result)
    print_vector(result, 3, 7)

def print_ptx(ptx):
    result = DoubleVector()
    encoder.decode(ptx,result)
    print_vector(result, 3, 7)

def chebyshev_approximation(f, dilatation_factor=50, polynomial_degree=25, bound=1, convertToTensor=True):
    if convertToTensor:
        f_a = lambda x: f(torch.tensor(x*dilatation_factor))
    else:
        f_a = lambda x: f(x*dilatation_factor)

    domain = [-bound,bound]

    p = Chebyshev.interpolate(f_a,deg=polynomial_degree,domain=domain)
    return p, f_a

def polynomial_approximation_coefficients(f, dilatation_factor=50, polynomial_degree=25,
                                          bound=1, convertToTensor=True):
    p,_ = chebyshev_approximation(f, dilatation_factor, polynomial_degree, bound, convertToTensor)

    return Polynomial.cast(p).coef

def plot_graph_function_approximation(f, dilatation_factor=50, polynomial_degree=25, bound=1, convertToTensor=True):

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
def coeffs_to_plaintext(coeffs: List[float], encoder: CKKSEncoder, scale: float):
    plain_coeffs = []

    for coef in coeffs:
        plain_coeff = Plaintext()
        encoder.encode(coef, scale, plain_coeff)
        plain_coeffs.append(plain_coeff)

    return plain_coeffs

def compute_all_powers(ctx : Ciphertext, degree: int, evaluator: Evaluator,
                       relin_keys: RelinKeys, verbose=False):

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

        temp = Ciphertext()

        power_cand = powers[cand]
        evaluator.mod_switch_to(power_cand, powers[i-cand].parms_id(),temp)
        evaluator.multiply(temp, powers[i-cand], temp)
        evaluator.relinearize_inplace(temp, relin_keys)
        evaluator.rescale_to_next_inplace(temp)

        powers[i] = temp

    return powers

# Cell
def multiply_and_add_coeffs(powers: List[Ciphertext], plain_coeffs: List[Plaintext],
                            coeffs: List[float],
                            evaluator: Evaluator, encryptor: Encryptor,
                            tol=1e-3, verbose=False) -> Ciphertext:
    assert len(powers) == len(plain_coeffs), f"Mismatch between length between powers {len(powers)} and coeffs {len(coeffs)}"
    output = Ciphertext()

    x = ctx_value(powers[1])

    expected_output = coeffs[0]
    encryptor.encrypt(plain_coeffs[0],output)

    temp = Ciphertext()

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

        evaluator.mod_switch_to_inplace(output, temp.parms_id())
        output.scale(pow(2.0,PRECISION_BITS))
        temp.scale(pow(2.0,PRECISION_BITS))
        evaluator.add_inplace(output, temp)

        expected_output = coef * (x ** i)
        if verbose:
            print(f"{i} Expected output : {expected_output}, output : {ctx_value(temp)}")
    return output

# Cell
import torch.nn as nn

def apply_comparator(ctx: Ciphertext, comparator: nn.Linear,
                     encoder: CKKSEncoder, evaluator: Evaluator) -> Ciphertext:
    output = Ciphertext()
    row_ptx = Plaintext()

    bias_ptx = Plaintext()
    bias = DoubleVector(list(comparator.bias.data.numpy()))
    encoder.encode(bias, scale, bias_ptx)

    for i in range(matrix.shape[0]):
        row = matrix[i]
        source = row.argmax()
        rotation = source - i

        # We encode the current row
        row = list(row)
        encoder.encode(row,scale, row_ptx)

        temp = Ciphertext()
        evaluator.multiply_plain(ctx, row_ptx, temp)
        evaluator.rescale_to_next_inplace(temp)

        if np.abs(rotation) > 0:
            evaluator.rotate_vector_inplace(temp, rotation, galois_keys)

        if i == 0:
            output = temp
        else:
            evaluator.add_inplace(output,temp)

    evaluator.mod_switch_to_inplace(bias_ptx, output.parms_id())
    output.scale(scale)
    evaluator.add_plain_inplace(output, bias_ptx)

    return output

# Cell
def vrep(x: List, n:int) -> List:
    k = n // len(x)
    rest = n % len(x)
    output = x * k + x[:rest]
    return output

# Cell
def extract_diagonals(matrix, encoder: CKKSEncoder) -> List[Plaintext]:
    assert matrix.shape[0] == matrix.shape[1], "Non square matrix"
    dim = matrix.shape[0]

    diagonals = []
    diagonal_ptx = Plaintext()
    for i in range(dim):
        diagonal = []
        for j in range(dim):
            diagonal.append(matrix[j][(j+i) % dim])
        encoder.encode(DoubleVector(diagonal), scale, diagonal_ptx)
        diagonals.append(diagonal_ptx)
    return diagonals

# Cell
def print_range_ctx(ctx, end=0, begin=0):
    r = range(begin,end)
    for i in r:
        print(ctx_value(ctx, i))

def print_range_ptx(ptx, end=0, begin=0):
    r = range(begin,end)
    for i in r:
        print(ptx_value(ptx, i))