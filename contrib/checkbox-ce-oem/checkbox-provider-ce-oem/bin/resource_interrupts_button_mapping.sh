#!/usr/bin/env bash

awk '{
    split($0, record, " ")
    for (i in record) {
        printf "name: %s\n\n", record[i]
    }
}' <<< "$INTERRUPTS_BUTTONS"
