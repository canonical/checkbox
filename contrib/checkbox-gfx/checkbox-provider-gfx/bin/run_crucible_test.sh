#!/bin/bash
test_string=$1
# --fork is used because the documentation indicates that it will prevent
# individual tests from crashing the main thread. Remove it if debugging
(cd /usr/local/checkbox-gfx/crucible; XDG_RUNTIME_DIR=/run/user/1000
./bin/crucible run --fork $test_string > /tmp/crucible_out.txt)

# Show the standard output
cat /tmp/crucible_out.txt

# This is a workaround for the fact that crucible ls-tests shows top-level
# tests such as:
# func.depthstencil.stencil-triangles.clear-0x17.ref-0x17.compare-op-always
# .pass-op-zero.fail-op-invert
# but the test has multiple versions (.q0, .q1, .q2), which will return an
# error if run together, even if they do not return an error when running
# separately with the same result. So this just runs everything together and
# checks to see if the output mentions any failed tests.
if(grep "crucible: info   : fail 0" /tmp/crucible_out.txt); then
echo "The test indicates no test failures. Passing test!"
  rm /tmp/crucible_out.txt
  exit 0
fi
>&2 echo "Non-zero test failure value. Test failed!"
rm /tmp/crucible_out.txt
exit 1
