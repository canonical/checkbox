#!/bin/sh
# Requires activated virtualenv with coverage
coverage3 run --branch $(which plainbox) self-test --unit-tests --verbose && \
coverage3 run --append --branch $(which plainbox) self-test --integration-tests --verbose && \
coverage3 report && \
coverage3 html
