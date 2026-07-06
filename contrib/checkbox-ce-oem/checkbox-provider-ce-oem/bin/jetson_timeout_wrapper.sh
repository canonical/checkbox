#!/usr/bin/bash

set -ex

# print why command exited
print_status() {
    status=$?;
    if [ $status != 0 ]; then
        echo "ERROR: Command failed with return code $status"
    else
        echo "Command succeeded"
    fi
}

trap print_status EXIT

TIMEOUT=$1
shift 1
timeout -k 10 $TIMEOUT $@
