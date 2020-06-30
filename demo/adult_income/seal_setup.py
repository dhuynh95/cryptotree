"""Setup of SEAL variables. 

This will create the SEAL globals used during computation, such as the public key,
secret key, the relinearization keys, and the Galois keys, and save them in the
seal folder.
"""

from cryptotree.seal_helper import create_seal_globals, save_seal_globals
from config import poly_modulus_degree, moduli, PRECISION_BITS

if __name__ == "__main__":
    create_seal_globals(globals(), poly_modulus_degree, moduli, PRECISION_BITS, use_local=False)
    save_seal_globals(globals(), save_pk=True, save_sk=True)