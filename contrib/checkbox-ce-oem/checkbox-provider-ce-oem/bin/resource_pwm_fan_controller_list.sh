#!/usr/bin/env bash

if [ -z "$PWM_FAN_CONTROLLERS" ]; then
    exit 0
fi
awk '{split($0, arr, "|"); for (i in arr) {printf "name: %s\n\n", arr[i]}}' <<< "$PWM_FAN_CONTROLLERS"
