#!/bin/bash

if [ ! -d /sys/"$1"/wwan ]; then
    echo "wwan interface not exist"
    exit 1
fi

interface=$(basename /sys/"$1"/wwan/*/)
if [ ! -e /dev/"$interface"at0 ]; then
    echo "/dev/""$interface""at0" not exist
    exit 1
fi

#set power state on to make FCC unlock hook been called
mmcli -m /sys"$1" --set-power-state-on

#try to query functionality multiple times in case modem not ready
for _ in {1..3};
do
    if echo -e "at+cfun?\r\n" > /dev/"$interface"at0 & timeout 1 cat /dev/"$interface"at0 |
        grep -q "+CFUN: 1"; then
        echo "$interface unlocked"
        exit 0
    fi
done

echo "$interface locked"
echo "Please check if fcc unlock service installed and executed correclty"
exit 1
