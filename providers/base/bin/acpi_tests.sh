#!/bin/bash

OEM_OSI_LIST=( Linux-Dell-Video Linux-Lenovo-NV-HDMI-Audio Linux-HPI-Hybrid-Graphics )
for osi in "${OEM_OSI_LIST[@]}"
do
	grep -q -r "$osi" /sys/firmware/acpi/* && exit 1
done

exit 0
