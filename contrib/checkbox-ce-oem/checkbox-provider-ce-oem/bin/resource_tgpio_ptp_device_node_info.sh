#!/usr/bin/env bash

if ! nodes=$(udevadm info /dev/ptp* 2>/dev/null | grep -E 'P: /devices/virtual/ptp/ptp[0-9]+' -A 5 | grep -Po 'DEVNAME=\K[^[:space:]]+')
then
    echo "Failed to get Virtual PTP device node." >&2
    exit 1
fi
if [ -z "${nodes}" ]
then
    echo "No Virtual PTP device node found." >&2
    exit 1
fi
for node in ${nodes}
do
    echo "ptp_device_node: ${node}"
    echo ""
done
