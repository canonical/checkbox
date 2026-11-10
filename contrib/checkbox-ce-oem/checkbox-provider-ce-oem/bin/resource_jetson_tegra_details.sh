#!/usr/bin/env bash

# Fail visibly: a Jetson plan on a machine with no device-tree model
# is a setup problem, not an empty result.
if [ ! -e /proc/device-tree/model ]; then
    echo "/proc/device-tree/model not found - not a Jetson device?" >&2
    exit 1
fi
echo "qspi-version: $(cat /sys/class/dmi/id/bios_date 2>/dev/null)--$(cat /sys/class/dmi/id/bios_version 2>/dev/null)"
echo "model: $(tr -d '\0' < /proc/device-tree/model)"
