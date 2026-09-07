#!/usr/bin/env bash

# Fail visibly: the lockdown interface is expected on Jetson kernels.
if [ ! -f /sys/kernel/security/lockdown ]; then
    echo "/sys/kernel/security/lockdown not found" >&2
    exit 1
fi
# lockdown mode can be none, integrity or confidentiality
lockdown_mode=$(grep -o "\[.*\]" < /sys/kernel/security/lockdown | sed 's/\[//g ; s/\]//g')
echo "mode: $lockdown_mode"
