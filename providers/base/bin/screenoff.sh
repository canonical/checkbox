#!/bin/bash

while read -r line;
do
    if [ "${line:0:7}" = "N: Name" ]; then
        name="${line:9:-1}"
    fi
    if [ "${line:0:8}" = "S: Sysfs" ] && [ "$keyboard" -eq 1 ]; then
        sysfs="${line:9}"
	break
    fi
    if [ "$name" = "AT Translated Set 2 keyboard" ] ||
       [ "${name:0:26}" = "Logitech Wireless Keyboard" ]; then
        keyboard=1
    else
        keyboard=0
    fi
done </proc/bus/input/devices

event_sysfs=$(find "/sys$sysfs" -name "event*")
event_idx=$(echo "$event_sysfs" | awk -F/ '{print $NF}')
device="/dev/input/$event_idx"

evemu-event "${device}" --type EV_MSC --code MSC_SCAN --value 219
evemu-event --sync "${device}" --type EV_KEY --code KEY_LEFTMETA --value 1
evemu-event "${device}" --type EV_MSC --code MSC_SCAN --value 38
evemu-event --sync "${device}" --type EV_KEY --code KEY_L --value 1
evemu-event "${device}" --type EV_MSC --code MSC_SCAN --value 38
evemu-event --sync "${device}" --type EV_KEY --code KEY_L --value 0
evemu-event "${device}" --type EV_MSC --code MSC_SCAN --value 219
evemu-event --sync "${device}" --type EV_KEY --code KEY_LEFTMETA --value 0
sleep "$1"
evemu-event "${device}" --type EV_MSC --code MSC_SCAN --value 28
evemu-event --sync "${device}" --type EV_KEY --code KEY_ENTER --value 1
evemu-event "${device}" --type EV_MSC --code MSC_SCAN --value 28
evemu-event --sync "${device}" --type EV_KEY --code KEY_ENTER --value 0
loginctl unlock-session
