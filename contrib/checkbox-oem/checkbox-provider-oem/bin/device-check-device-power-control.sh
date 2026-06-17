#!/bin/bash

FOUND=0

while read -r line;
do
    state=$(cat "$line")
    if [ "$state" = "on" ]; then
        FOUND=1
        #dpath="${line:0:-14}"
        echo "$line:on"
        #udevadm info -a "$dpath"
    fi
done< <(find /sys/devices -name control | grep "power/control")

if [ $FOUND -eq 1 ]; then
    echo "According to agreement [1], HWE will try to fix it as many as possible."
    echo "[1] https://chat.canonical.com/canonical/pl/zab9uy3qajn7teua9jkbgh49ac"
    exit 1
fi
