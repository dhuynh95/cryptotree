# cryptotree
> Cryptotree is an implementation of Neural Random Forests, and Homomorphic Random Forests.


Cryptotree is an open-source package to allow the Decision Trees and Random Forests to be used on encrypted data, using the homomorphic encryption library [Microsoft SEAL](https://github.com/Microsoft/SEAL), and its Python wrapper [TenSEAL](https://github.com/OpenMined/TenSEAL). Cryptotree uses the recent encryption scheme [CKKS](https://eprint.iacr.org/2016/421.pdf), which is implemented in SEAL, to perform homomorphic computation. 

By leveraging the fact that Random Forests can be modeled by [Neural Random Forests](https://arxiv.org/pdf/1604.07143.pdf) (2016, Biau, Scornet & Welbl), cryptotree proposes an homomorphic evaluation of these Neural Networks in a SIMD (Single Instruction Multiple Data) manner, in order to do homomorphic evaluation of Homomorphic Random Forests.

Cryptotree therefore both implements Neural Random Forests, and Homomorphic Random Forests, and allows the use of powerful supervised models on encrypted data.

Cryptotree is developped using [nbdev](https://nbdev.fast.ai/), which allows to develop efficiently in Jupyter notebooks. The code is therefore available in the folder <code>nbs/</code>, and has been structured to be heavily documented with examples for a better understanding of cryptotree.

## Install

As of now, there are two ways to install cryptotree, which is dependent on [TenSEAL](https://github.com/OpenMined/TenSEAL) :
<ol>
    <li> Manual installation :
        <ol>
            <li>Follow the install instructions of SEAL-python : https://github.com/OpenMined/TenSEAL</li>
            <li>Git clone this repository : <code>git clone https://github.com/dhuynh95/cryptotree.git</code></li>
            <li>Cd into the repository and run the installation : <code>cd cryptotree & pip3 install . </code></li>
        </ol>
    </li>
    <li> Use Docker :
        <ol>
            <li>Git clone the cryptotree repository : <br>
                <code>git clone  https://github.com/dhuynh95/cryptotree.git</code> </li>
            <li>Create the Docker image : <code>docker build -t cryptotree .</code></li>
        </ol>
    </li>
</ol>

## Examples

A full example of the Adult income dataset can be found in https://github.com/dhuynh95/cryptotree/blob/master/examples/adult_dataset.ipynb.

It can be run easily with the Docker image, just by running the following command after the image has been successfully built : `sudo docker run -p 8888:8888 cryptotree /bin/sh /cryptotree/examples/adult_income/run_jupyter_server.sh`. This command simply performs port forwarding for the Jupyter server which will be launched. 

## Paper

https://arxiv.org/abs/2006.08299

## TODO

- Implement Baby step, Giant step for homomorphic polynomial evaluation
- Find a way to fine tune the comparator and the matcher of the neural decision trees, while preserving the invariant which is having an output in $[-1,1]$

## Contributors

- [D. Huynh](https://github.com/dhuynh95)
