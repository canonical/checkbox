#!/usr/bin/env bash

# The deb and snap variants bootstrap in the same plans: stay quiet
# when the deb variant covers this device, fail visibly when no
# tensorrt-samples variant is present at all.
if [ ! -f /snap/tensorrt-samples/current/etc/tensorrt-samples.list ]; then
    [ -x /opt/nvidia/run-tensorrt-samples.py ] && exit 0
    echo "tensorrt-samples not found (neither snap nor deb runner)" >&2
    exit 1
fi
while IFS= read -r f; do printf "name: %s\n\n" "$f"; done < /snap/tensorrt-samples/current/etc/tensorrt-samples.list
