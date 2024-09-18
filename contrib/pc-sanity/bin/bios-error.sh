#!/bin/bash

OUTPUT=$(journalctl -b -k | grep -A 20 "ACPI BIOS Error")
RET=$?

if [ $RET -eq 0 ]; then
    DATE=$(cat < /sys/class/dmi/id/bios_date)
    RELEASE=$(cat < /sys/class/dmi/id/bios_release)
    VEN=$(cat < /sys/class/dmi/id/bios_vendor)
    VER=$(cat < /sys/class/dmi/id/bios_version)
    echo "!!! ACPI BIOS Error detected !!!"
    echo "BIOS date: $DATE"
    echo "BIOS release: $RELEASE"
    echo "BIOS vendor: $VEN"
    echo "BIOS version: $VER"
    echo "$OUTPUT"
    exit 1
fi
