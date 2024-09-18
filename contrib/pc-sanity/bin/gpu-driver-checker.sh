#!/bin/bash

set -e

result=0

# Available driver check in each GPU
for gpu in $(lspci -n -d ::0x0300| awk '{print $1}') \
           $(lspci -n -d ::0x0302| awk '{print $1}') \
           $(lspci -n -d ::0x0380| awk '{print $1}'); do
    if [[ ${gpu} != "0000"* ]]; then
        gpu="0000:${gpu}"
    fi
    vendor=$(cat /sys/bus/pci/devices/"${gpu}"/vendor)
    device=$(cat /sys/bus/pci/devices/"${gpu}"/device)
    if [ ! -d "/sys/bus/pci/devices/${gpu}/driver" ]; then
        echo "E: Your GPU ${gpu} (${vendor}:${device}) hasn't driver."
        sudo lspci -nnvk -s "$gpu"
        result=255
    else
        driver=$(basename "$(readlink /sys/bus/pci/devices/"${gpu}"/driver)")
        echo "Your GPU ${gpu} is using ${driver}."
    fi
done


# Check nvidia driver
nvidia_version=$(modinfo nvidia 2>/dev/null| grep "^version"| awk '{print $2}')
if [ -n "$nvidia_version" ]; then
    nvidia_pkg_prefix="nvidia-driver-"
    signed_nvidia_prefix="linux-modules-nvidia"
    echo "Nvidia version is ${nvidia_version}."
    if ! modinfo nvidia| grep -q "^signer:.*Canonical Ltd. Kernel Module Signing"; then
        echo "E: Your nvidia driver is not signed by Canonical."
        echo "E: Expecting ${signed_nvidia_prefix}-${nvidia_version%%.*}-$(uname -r)."
        result=255
    else
        echo "Nvidia driver is signed."
    fi
    pkg="${nvidia_pkg_prefix}${nvidia_version%%.*}"
    support=$(apt show "${pkg}" 2>/dev/null| grep "^Support:"| awk '{print $2}')
    if [ "$support" = "LTSB" ]; then
        echo "Nvidia driver is LTS version."
    elif [ "$support" = "PB" ]; then
        echo "Nvidia driver is production version."
    else
        echo "E: ${pkg} is not LTS version, please check."
        apt-cache madison "$pkg"
        result=255
    fi
fi

exit $result
