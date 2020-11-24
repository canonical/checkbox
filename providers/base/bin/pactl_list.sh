#!/bin/bash

EXIT_CODE=0

for device in "sources" "sinks"
do
    if ! pactl list $device short | grep -v -E "monitor|auto_null"
    then
        echo "No available $device found"
        case $device in
            "sources")
            EXIT_CODE=$(( EXIT_CODE+1 ))
            ;;
            "sinks")
            EXIT_CODE=$(( EXIT_CODE+2 ))
        esac
    fi
done

exit $EXIT_CODE