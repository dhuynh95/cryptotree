FROM openmined/tenseal

COPY . /cryptotree
WORKDIR /cryptotree

RUN pip3 install -e .
