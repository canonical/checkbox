#!/bin/bash

# Get the keyboard input device
while read -r line;
do
    if [ "${line:0:8}" = "S: Sysfs" ]; then
        sysfs="${line:9}"
    fi
    if [ "${line:0:5}" = "B: EV" ] && [ "${line:6}" = "120013" ]; then
        keyboard=1
        break
    else
        keyboard=0
    fi
done </proc/bus/input/devices

if [ $keyboard -eq 0 ]; then
    echo "Can't find keyboard to simulate lock screen"
    exit 1
fi

# Retrieve the event index of the keyboard input device
event_sysfs=$(find "/sys$sysfs" -name "event*")
event_idx=$(echo "$event_sysfs" | awk -F/ '{print $NF}')
device="/dev/input/$event_idx"
id=$(loginctl --no-legend --value list-sessions | awk '/seat/ { print $1 }')

# Simulate key event Super+L
evemu-event "${device}" --type EV_MSC --code MSC_SCAN --value 219
evemu-event --sync "${device}" --type EV_KEY --code KEY_LEFTMETA --value 1
evemu-event "${device}" --type EV_MSC --code MSC_SCAN --value 38
evemu-event --sync "${device}" --type EV_KEY --code KEY_L --value 1
evemu-event "${device}" --type EV_MSC --code MSC_SCAN --value 38
evemu-event --sync "${device}" --type EV_KEY --code KEY_L --value 0
evemu-event "${device}" --type EV_MSC --code MSC_SCAN --value 219
evemu-event --sync "${device}" --type EV_KEY --code KEY_LEFTMETA --value 0
sleep "$1"
# Simulate key event Enter
evemu-event "${device}" --type EV_MSC --code MSC_SCAN --value 28
evemu-event --sync "${device}" --type EV_KEY --code KEY_ENTER --value 1
evemu-event "${device}" --type EV_MSC --code MSC_SCAN --value 28
evemu-event --sync "${device}" --type EV_KEY --code KEY_ENTER --value 0
# Unlock the seesion
loginctl unlock-session "$id"
