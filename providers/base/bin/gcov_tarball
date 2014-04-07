#!/bin/sh

set -o errexit

cd /usr/share
tar -xzf gcov.tar.gz

cd /tmp
lcov -q -c -o gcov.info
genhtml -q -o gcov gcov.info 2>/dev/null
tar -czf - gcov
