#!/usr/bin/env bash
CUDA_PATH=$(find /usr/local -maxdepth 1 -type d -iname "cuda*")/bin
export PATH=$PATH:$CUDA_PATH
gpu_burn 14400 | grep -v -e '^[[:space:]]*$' -e "errors:" -e "Summary at"
