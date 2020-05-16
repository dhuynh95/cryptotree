import streamlit as st
import pandas as pd
import numpy as np
import torch
import pickle

import tenseal.sealapi as seal
from pathlib import Path

import pickle
from cryptotree.preprocessing import Featurizer, ColumnSelector, Reshaper
from cryptotree.cryptotree import HomomorphicTreeFeaturizer

from config import PRECISION_BITS

st.title("Demo Adult Income")

st.header("I - Data input")

st.write("Enter your data here : ")

dtypes = pickle.load(open("data/dtypes.pkl", "rb"))
example = pd.read_csv("data/example.csv")

categorical_columns = ["WorkClass","Education","MaritalStatus", "Occupation", "Relationship", 
"Race", "Gender", "NativeCountry"]

data = {}

for col, dtype in dtypes.iteritems():
    if col in categorical_columns:
        values = dtype.categories.values
        values2idx = dict(zip(values, range(len(values))))
        
        example_value = example[col].values[0]
        example_idx = values2idx[example_value]
        
        data[col] = st.selectbox(col, values, index=example_idx)
    else:
        example_value = example[col].values[0]
        
        data[col] = st.number_input(col, value=example_value)

st.header("II - Encrypting the data")

# Here we setup the SEAL encryptor and decryptor
path = Path("seal")
parms = seal.EncryptionParameters(seal.SCHEME_TYPE.CKKS)
parms.load(str(path/"parms"))
context = seal.SEALContext.Create(parms, True, seal.SEC_LEVEL_TYPE.TC128)

secret_key = seal.SecretKey()
secret_key.load(context, str(path/"secret_key"))

encoder = seal.CKKSEncoder(context)
encryptor = seal.Encryptor(context, secret_key)
decryptor = seal.Decryptor(context, secret_key)

scale = pow(2.0, PRECISION_BITS)

pipe = pickle.load(open("preprocess/pipe.pkl", "rb"))
homomorphic_featurizer = HomomorphicTreeFeaturizer.load("preprocess/homomorphic_featurizer.pkl",
encoder, encryptor, scale, use_symmetric_key=True)

file_name = st.text_input("Input file name", value="data.ctx")

if st.button("Encrypt"):
    row = {key : [value] for key,value in data.items()}
    row = pd.DataFrame(row)
    x = pipe.transform(row).reshape(-1)
    ctx = homomorphic_featurizer.encrypt(x)

    path = Path("input")
    if not path.exists():
        path.mkdir()
    ctx.save(str(path/file_name))
    st.write(f"Data encrypted at {path/file_name}")

st.header("III - Decrypting the result")

output_file_name = st.text_input("Output file name", value="data.ctx")
st.write("Probability of having a salary > 50k : ")

output_path = Path("output")
if st.button("Decrypt"):
    ctx = seal.Ciphertext()
    ctx.load(context, str(output_path/output_file_name))
    ptx = seal.Plaintext()
    decryptor.decrypt(ctx, ptx)

    values = encoder.decode_double(ptx)[:2]
    proba = torch.softmax(torch.tensor(values), dim=0).numpy()[1]

    st.progress(float(proba))