FROM ubuntu:19.10

# Install binary dependencies
RUN apt-get update && \
    apt-get install -qqy \
    g++ \
    git \
    make \
    cmake \
    python3 \
    python3-dev \
    python3-pip \
    sudo \
    libdpkg-perl \
    --no-install-recommends

# Copy all files to container
COPY ./ /app

# Build SEAL
WORKDIR /app/SEAL-Python/SEAL/native/src
RUN cmake . && \
    make && \
    make install

# Install requirements
WORKDIR /app/SEAL-Python/
RUN pip3 install -r requirements.txt

# Build pybind11
WORKDIR /app/SEAL-Python/pybind11
RUN mkdir build
WORKDIR /app/SEAL-Python/pybind11/build
RUN cmake .. && \
    make check -j 4 && \
    make install

# Build wrapper
WORKDIR /app/SEAL-Python/
RUN python3 setup.py build_ext -i && \
    python3 setup.py install

# Clean-up
RUN apt-get clean && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# Install cryptotree
WORKDIR /app
RUN pip3 install setuptools
RUN pip3 install -e .
RUN pip3 install jupyter notebook .