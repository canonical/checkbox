#!/bin/bash

# Establish the system type based on DMI info
TYPE=$(dmidecode -t 3 | awk '/Type:/ { print $2 }')
echo "Type: " "$TYPE"

BATTERY="NO"
while IFS= read -r -d '' device
do
    if [ "$(cat "$device")" == "Battery" ]; then
        BATTERY="YES"
    fi
done <   <(find /sys -name "type" -print0)

echo "Battery: " $BATTERY

case $TYPE in
Notebook|Laptop|Portable)
    exit 0
    ;;
*)
    # Give the system a second chance based on the battery info
    if [ $BATTERY == "YES" ]; then
    	exit 0
   	else
   		exit 1
   	fi
    ;;
esac
