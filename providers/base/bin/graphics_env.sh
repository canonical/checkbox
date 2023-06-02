#!/bin/bash
# This script checks if the submitted VIDEO resource is from AMD or nvidia
# and if it is a discrete GPU (graphics_card_resource orders GPUs by index:
# 1 is theintegrated one, 2 is the discrete one).
#
# This script has to be sourced in order to set an environment variable that
# is used by the open source AMD driver and properties nvidia driver to
# trigger the use of discrete GPU.

DRIVER=$1
INDEX=$2

# Some environment variables(like XDG_SESSION_TYPE) are set by some services
# (like graphical-session.target), but during system suspend/resume, they will
# be unset.
ensure_xdg_session_type() {
    local max_attempts=5
    local attempt=0
    while [ -z "$XDG_SESSION_TYPE" ]; do
        sleep 1

        echo "Waiting for XDG_SESSION_TYPE to be set"
        XDG_SESSION_TYPE=$(systemctl --user show-environment | grep XDG_SESSION_TYPE | cut -d= -f2)

        attempt=$((attempt+1))
        if [ $attempt -eq $max_attempts ]; then
            >&2 echo "XDG_SESSION_TYPE was not set after $max_attempts attempts"
            exit 1
        fi
    done

    export XDG_SESSION_TYPE
}

# We only want to set the variable on systems with more than
# 1 GPU running the amdgpu/radeon/nvidia drivers.
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
elif [[ $DRIVER == "nvidia" || $DRIVER == "pcieport" ]]; then
    NB_GPU=$(udev_resource.py -l VIDEO | grep -oP -m1 '\d+')
    if [[ $NB_GPU -gt 1 ]]; then
        nvidia_nvlink_check.sh
        NVLINK=$?
        if [[ $INDEX -gt 1 && ${NVLINK} -ne 0 && "$(prime-select query)" = 'on-demand' ]]; then
            echo "Setting up PRIME GPU offloading for nvidia discrete GPU"
            export __NV_PRIME_RENDER_OFFLOAD=1
            export __GLX_VENDOR_LIBRARY_NAME=nvidia
        else
            unset __NV_PRIME_RENDER_OFFLOAD
            unset __GLX_VENDOR_LIBRARY_NAME
        fi
    fi
fi

ensure_xdg_session_type
