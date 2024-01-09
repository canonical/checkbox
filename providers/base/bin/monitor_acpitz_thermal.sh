#!/bin/bash

THERMAL_PATH="/sys/class/thermal/thermal_zone"
THERMALS=$(find $THERMAL_PATH*[0-9])
ACPITZ_THERMAL_PATH=""
# Get the acpitz thermal
for t in $THERMALS; do
    THERMAL_TYPE=$(cat "$t/type")
    if [ "$THERMAL_TYPE" = "acpitz" ]; then
        ACPITZ_THERMAL_PATH=$t
        break
    fi
done
# Check acpitz thermal can be found
if [ -z "$ACPITZ_THERMAL_PATH" ]; then
    echo "Cannot find the acpitz thermal"
    exit 1
fi
echo "The path of acpitz thermal: $ACPITZ_THERMAL_PATH"
# Do testing and monitor the temperature
ACPITZ_TEMP="$ACPITZ_THERMAL_PATH/temp"
TEMP_BEFORE=$(cat "$ACPITZ_TEMP")
echo "Temperature before stress: $TEMP_BEFORE"
if ! [ "$TEMP_BEFORE" -gt 0 ]; then
    echo "Invalid temperature, it should be more than 0"
    exit 1
fi
echo "Running stress for 5 minutes"
stress-ng --matrix 0 -t 5m
TEMP_AFTER=$(cat "$ACPITZ_TEMP")
echo "Temperature after stress: $TEMP_AFTER"
if ! [ "$TEMP_AFTER" -gt "$TEMP_BEFORE" ]; then
    echo "The temperature after stress testing should be higher than before"
    exit 1
fi