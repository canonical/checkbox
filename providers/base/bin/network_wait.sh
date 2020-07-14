#!/bin/bash

x=1
while true; do
    state=$(/usr/bin/nmcli -t -f STATE nm 2>/dev/null)
    if [[ $? != 0 ]]; then
        state=$(/usr/bin/nmcli -t -f STATE general 2>/dev/null)
        rc=$?
        if [[ $rc != 0 ]]; then
            exit $rc
        fi
    fi
    if [ "$state" = "connected" ]; then
        echo $state
        exit 0
    fi

    x=$(($x + 1))
    if [ $x -gt 12 ]; then
        echo $state
        exit 1
    fi

    sleep 5
done
