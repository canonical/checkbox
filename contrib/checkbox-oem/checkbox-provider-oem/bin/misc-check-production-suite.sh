#!/bin/bash

if [ -n "$SNAP" ]; then
    HOSTFS_ROOT="/var/lib/snapd/hostfs"
else
    HOSTFS_ROOT=""
fi

LSB_RELEASE="$HOSTFS_ROOT/etc/lsb-release"
APT_LISTS="$HOSTFS_ROOT/var/lib/apt/lists"

codename=$(grep "DISTRIB_CODENAME=" "$LSB_RELEASE" | cut -d= -f2)
oemcodename=$(misc-get-oem-info.sh --oem-codename)
platform=$(misc-get-oem-info.sh --platform-codename)
release_number=$(grep "DISTRIB_RELEASE=" "$LSB_RELEASE" | cut -d= -f2)

if [ -z "$codename" ] || [ -z "$oemcodename" ] || [ -z "$platform" ]; then
    echo "Can't get oem info from the platform"
    exit 0
fi

case "$oemcodename" in
    (somerville)
        oem="dell"
        ;;
    (stella)
        oem="hp"
        ;;
    (sutton)
        oem="lenovo"
        ;;
    (*)
        echo "Unsupported OEM codename $oemcodename"
        exit 1
        ;;
esac

listfile="${APT_LISTS}/${oem}.archive.canonical.com_dists_${codename}_InRelease"

if [ ! -f "$listfile" ]; then
    echo "The list file doesn't exist"
    exit 1
fi

components=$(grep "Components" "$listfile")

if ! [[ "$components" == *"$oemcodename"* ]]; then
    echo "oem archive is not ready"
    echo "$components"
    exit 1
fi

if [[ "$release_number" > "24.00" ]] || [[ "$release_number" == "24.04" ]]; then
    # For versions 24.04 and newer, check platform archives for all OEMs
    if ! [[ "$components" == *"$oemcodename-$platform"* ]]; then
        echo "platform archive is not ready"
        echo "$components"
        exit 1
    fi
elif [[ "$release_number" == "22.04" ]]; then
    # For 22.04, only check somerville
    if [ "$oemcodename" = "somerville" ]; then
        if ! [[ "$components" == *"$oemcodename-$platform"* ]]; then
            echo "platform archive is not ready"
            echo "$components"
            exit 1
        fi
    fi
fi
