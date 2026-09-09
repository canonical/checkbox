#!/bin/sh
#
# Example script demonstrating that bin/ scripts can be organized into
# category subfolders (mirroring units/) while still being invoked by
# their basename only from a job's command: field. See the miscellanea
# job "miscellanea/hello-misc" in units/miscellanea/jobs.pxu.

set -e

echo "Hello from bin/miscellanea/hello_misc.sh"
