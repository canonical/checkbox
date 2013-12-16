#!/bin/sh
# Because python3-coverage is still broken
rm -rf htmlcov
# Requires activated virtualenv with coverage
coverage3 run --branch $(which plainbox) self-test --unit-tests --fail-fast --quiet
if [ "$1" != "--skip-integration" ]; then
    coverage3 run --append --branch $(which plainbox) self-test --integration-tests --fail-fast --quiet
fi
# coverage3 report
coverage3 html
