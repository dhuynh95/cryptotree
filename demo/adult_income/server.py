from cryptotree.cryptotree import HomomorphicNeuralRandomForest, HomomorphicTreeEvaluator
from cryptotree.polynomials import polyeval_tree
from cryptotree.seal_helper import load_seal_globals
from cryptotree.tree import SigmoidTreeMaker

from config import PRECISION_BITS

import pickle
import tenseal.sealapi as seal
from pathlib import Path

print("Loading SEAL globals ...")
load_seal_globals(globals())
print("Loading done.")

scale = pow(2.0, PRECISION_BITS)

print("Loading model ...")
h_rf = pickle.load(open("model/h_rf.pkl", "rb"))
dilatation_factor = 16
polynomial_degree = dilatation_factor

sigmoid_tree_maker = SigmoidTreeMaker(use_polynomial=True,
                                  dilatation_factor=dilatation_factor, polynomial_degree=polynomial_degree)
tree_evaluator = HomomorphicTreeEvaluator.from_model(h_rf, sigmoid_tree_maker.coeffs, 
                                                   polyeval_tree, evaluator, encoder, relin_keys, galois_keys, 
                                                   scale)
print("Loading done.")
print("Ready to compute.")

keep = True
ctx = seal.Ciphertext()
input_path = Path("input")
output_path = Path("output")
if not input_path.exists():
    input_path.mkdir()
if not output_path.exists():
    output_path.mkdir()

while keep:
    file = input("Input file name : ")
    if not file:
        keep = False
    ctx.load(context, str(input_path/file))
    print(f"Computing result on {file}")
    output = tree_evaluator(ctx)
    print(f"Computation done, saving file at {output_path/file}")
    output.save(str(output_path/file))