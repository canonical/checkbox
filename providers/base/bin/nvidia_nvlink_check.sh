#!/bin/bash

set -e

O=$(nvidia-smi nvlink -s)
# If the system doesn't support NVLINK, the output will be None.
if [ -z "$O" ]; then
    echo "System does not support NVLINK."
    exit 1
# If any inactive in output that means NVLINK not connected porpery or malfunction, -n use for verify output
elif echo "$O" | grep -iq inactive; then
    echo "NVLINK either the bridge is missing/defective or not configured correctly.";
    exit 1
else
    #"-e" use for new line character in string"
    echo -e "NVLINK Supported!\nStatus as below:\n\n""$O"
    exit 0
fi
