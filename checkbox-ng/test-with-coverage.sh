#!/bin/sh
# Requires activated virtualenv with coverage
coverage run --branch setup.py test && \
    coverage run --append --branch $(which plainbox) self-test --verbose && \
    coverage report && \
    coverage html
