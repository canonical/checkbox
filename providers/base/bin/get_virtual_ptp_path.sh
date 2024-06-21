#!/bin/bash

# Check if udevadm is available
if ! command -v udevadm &> /dev/null; then
    echo "udevadm command not found. Please ensure it is installed."
    exit 1
fi

# Run udevadm info to get information about /dev/ptp* devices
udevadm_output=$(udevadm info /dev/ptp*)

# Use awk to extract sections that contain the desired pattern
awk_output=$(echo "$udevadm_output" | awk '/P: \/devices\/virtual\/ptp\/ptp[0-9]+/' RS="\n\n" ORS="\n\n")

# Use grep to extract the device names
device_names=$(echo "$awk_output" | grep -Po 'DEVNAME=\K[^[:space:]]+')

# Print the device names
if [ -n "$device_names" ]; then
    echo "$device_names"
fi
