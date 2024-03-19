#!/usr/bin/env bash

output=$(tr -d '\0' < /proc/device-tree/compatible)
# Set comma as delimiter
IFS=','
read -ra output_arr <<< "$output"
# Set dash as delimiter
IFS='-'
read -ra s <<< "${output_arr[1]}"
echo "SoC: ${s[0]}"
echo
