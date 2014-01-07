#!/bin/sh
# On recent enough Debian/Ubuntu you can run this with python3-coverage (or
# python3.4-coverage) to run coverage with standard packages, without
# virtualenv. Everywhere else the default 'coverage3' should work fine.
#
# Because python3-coverage is still broken
rm -rf htmlcov
coverage=${1:-coverage3}
# Requires activated virtualenv with coverage
$coverage run --branch $(which plainbox) self-test --unit-tests --fail-fast --quiet
if [ "$1" != "--skip-integration" ]; then
    $coverage run --append --branch $(which plainbox) self-test --integration-tests --fail-fast --quiet
fi
# coverage3 report
$coverage html
