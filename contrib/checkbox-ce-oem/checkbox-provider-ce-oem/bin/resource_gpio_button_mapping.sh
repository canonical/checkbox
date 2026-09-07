#!/usr/bin/env bash

awk '{
    split($0, record, " ")
    for (i in record) {
        split(record[i], data, ":")
        printf "name: %s\nport: %s\n\n", data[1], data[2]
    }
}' <<< "$GPIO_BUTTONS"
