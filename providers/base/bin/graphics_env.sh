#!/bin/bash
# This script checks if the submitted VIDEO resource is from AMD and if it is
# a discrete GPU (graphics_card_resource orders GPUs by index: 1 is the
# integrated one, 2 is the discrete one).
#
# This script has to be sourced in order to set an environment variable that
# is used by the open source AMD driver to trigger the use of discrete GPU.

DRIVER=$1
INDEX=$2

# We only want to set the DRI_PRIME env variable on systems with more than
# 1 GPU running the amdgpu/radeon drivers.
if [[ $DRIVER == "amdgpu" || $DRIVER == "radeon" ]]; then
    NB_GPU=$(udev_resource.py -l VIDEO | grep -oP -m1 '\d+')
    if [[ $NB_GPU -gt 1 ]]; then
        if [[ $INDEX -gt 1 ]]; then
            # See https://wiki.archlinux.org/index.php/PRIME
            echo "Setting up PRIME GPU offloading for AMD discrete GPU"
            if ! cat /var/log/Xorg.0.log ~/.local/share/xorg/Xorg.0.log 2>&1 | grep -q DRI3; then
                PROVIDER_ID=$(xrandr --listproviders | grep "Sink Output" | awk '{print $4}' | tail -1)
                SINK_ID=$(xrandr --listproviders | grep "Source Output" | awk '{print $4}' | tail -1)
                xrandr --setprovideroffloadsink "${PROVIDER_ID}" "${SINK_ID}"
            fi
            export DRI_PRIME=1
        else
            export DRI_PRIME=
        fi
    fi
fi
