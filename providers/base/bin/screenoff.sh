#!/bin/bash

#The MIT License (MIT)
#
#Copyright (c) 2023 Kai-Chuan Hsieh
#
#Permission is hereby granted, free of charge, to any person obtaining a copy
#of this software and associated documentation files (the "Software"), to deal
#in the Software without restriction, including without limitation the rights
#to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
#copies of the Software, and to permit persons to whom the Software is
#furnished to do so, subject to the following conditions:
#
#The above copyright notice and this permission notice shall be included in
#all copies or substantial portions of the Software.
#
#THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
#IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
#FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
#AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
#LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
#OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
#THE SOFTWARE.

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
