#!/bin/sh
# Requires activated virtualenv with coverage
coverage run --branch $(which plainbox) self-test --unit-tests --verbose && \
coverage run --append --branch $(which plainbox) self-test --integration-tests --verbose && \
coverage report && \
coverage html
