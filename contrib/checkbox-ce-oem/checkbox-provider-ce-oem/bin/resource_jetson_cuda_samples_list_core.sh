#!/usr/bin/env bash

# The deb and snap variants bootstrap in the same plans: stay quiet
# when the deb variant covers this device, fail visibly when no
# cuda-samples variant is present at all.
if [ ! -f /snap/cuda-samples/current/etc/cuda-samples.list ]; then
    [ -x /opt/nvidia/run-cuda-samples.py ] && exit 0
    echo "cuda-samples not found (neither snap nor deb runner)" >&2
    exit 1
fi
while IFS= read -r f; do printf "name: %s\n\n" "$f"; done < /snap/cuda-samples/current/etc/cuda-samples.list
