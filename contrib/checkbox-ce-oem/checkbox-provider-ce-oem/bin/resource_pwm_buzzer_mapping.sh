#!/usr/bin/env bash

awk '{
    split($0, record, " ")
    for (i in record) {
        split(record[i], data, ":")
        printf "name: %s\nchip: %s\nport: %s\nenable_value: %s\n", data[1], data[2], data[3], data[4]
    }
}' <<< "$PWM_BUZZER"
