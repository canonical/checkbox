#!/bin/bash

set -e

O=$(nvidia-smi nvlink -s)
#Check NVLINK are avaliable first, if only 1 NVIDIA Graphic card, output will be empty.
if [ -z "$O" ];then
    echo "System does not support NVLINK or Only 1 NVIDIA graphic card installed";
    exit 1
#If any inactive in output that means NVLINK not connected porpery or malfunction, -n use for verify output
elif echo "$O" | grep -q inactive; then
    echo "NVLINK either the bridge is missing/defective or not configured correctly";
    exit 1
else
    #"-e" use for new line character in string"
    echo -e "NVLINK are Supported!\nStatus as below:\n\n""$O"
    exit 0
fi
