#!/bin/bash

set -e

if [[ $# -ne 2 ]]; then
    echo "ERROR: Please provide the path for the file and the timestamps count!"
    exit 1
fi

file_path=$1
expected_count=$2

# Filter out all the numbers before comma in "Event time time"
numbers=$(grep "Event time time" "$file_path" | awk -F'[,:]+' '{print $2}')

# abs() function to calculate absolute value
abs() {
    if (( $1 < 0 )); then
        echo $(( -$1 ))
    else
        echo "$1"
    fi
}

# Check if the timestamp count is correct
# the output count will be greater or smaller than "$time_count",
# because there will be the time difference between the time start to send and the time start to receive.
# However the difference shouldn't be greater than 1
actual_count=$(echo "$numbers" | wc -l)
if [[ $(abs $((actual_count - expected_count))) -gt 1 ]]; then
    echo "The expected output count doesn't match the actual output count"
    echo "Expected count: ${expected_count}"
    echo "Actual count:   ${actual_count}"
    exit 1
fi

# Check if the difference between every timestamp is equal to 1 (Intel only care about the number before ",")
prev_number=""
for number in $numbers; do
    if [[ -n "$prev_number" && $((number - prev_number)) -ne 1 ]]; then
        echo "ERROR: The difference between each timestamp is not one!"
        exit 1
    fi
    prev_number=$number
done

