#!/usr/bin/env bash

awk '{
    split($0, record, " ")
    for (i in record) {
        split(record[i], data, ":")
        printf "DO: %s\nDO_REGISTER_BYTE: %s\nDI: %s\nDI_REGISTER_BYTE: %s\n\n", data[1], data[2], data[3], data[4]
    }
}' <<< "$DIGITAL_IO_LOOPBACK_SERIAL"
