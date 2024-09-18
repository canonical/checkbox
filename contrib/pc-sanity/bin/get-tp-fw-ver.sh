#!/bin/bash

PARA=$1

help()
{
    echo "Execute the script directly by running"
    echo "./get-tp-fw-ver.sh"
}

case $PARA in
-h)
    help
    exit 1
    ;;
*)
    ;;
esac

while read -r line;
do
    if [ "${line:3:4}" = "Name" ]; then
        name="${line:9:-1}"
    fi
    if [ "${line:3:4}" = "Phys" ]; then
        phys="${line:8}"
    fi
    if echo "$name" | grep -q "Touchpad"; then
        if echo "$phys" | grep -q "i2c"; then
            device="$phys"
            break
        fi
    fi
done < "/proc/bus/input/devices"

tp_path=$(udevadm info /sys/bus/i2c/devices/"$device" | grep "P:" | cut -d " " -f2)
sub=$(echo "$tp_path" | sed -E 's/\/i2c-[A-Z].*//')
bus=$(basename "$sub")
id=$(echo "$bus" | sed -E 's/i2c-//')
hid_desc=$(sudo i2ctransfer -f -y "$id" w2@0x2c 0x20 0x00 r26)

major=$(echo "$hid_desc" | cut -d " " -f26)
minor=$(echo "$hid_desc" | cut -d " " -f25)
major_hex=$(echo "$major" | sed -E 's/0x0?//')
minor_hex=$(echo "$minor" | sed -E 's/0x//')
version="$major_hex.$minor_hex"

echo "major: $major, minor: $minor, version: $version"
