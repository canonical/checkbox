#!/bin/bash

codename=$(lsb_release -cs)
oemcodename=$(get-oem-info.sh --oem-codename)
platform=$(get-oem-info.sh --platform-codename)

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

listfile="/var/lib/apt/lists/${oem}.archive.canonical.com_dists_${codename}_InRelease"

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

if [ "$oemcodename" = "somerville" ]; then
    if ! [[ "$components" == *"$oemcodename-$platform"* ]]; then
        echo "platform archive is not ready"
        echo "$components"
        exit 1
    fi
fi
