#!/bin/sh
# Requires activated virtualenv with coverage
coverage3 run --branch $(which plainbox) self-test --unit-tests --verbose
if [ "$1" != "--skip-integration" ]; then
    coverage3 run --append --branch $(which plainbox) self-test --integration-tests --verbose
fi
coverage3 report
coverage3 html
