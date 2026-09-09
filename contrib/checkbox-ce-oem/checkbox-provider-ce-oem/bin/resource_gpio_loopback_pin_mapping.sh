#!/usr/bin/env bash

awk '{
    split($0, record, " ")
    for (i in record) {
        split(record[i], data, ":")
        printf "OUTPUT_GPIO_CHIP_NUMBER: %s\nPHYSICAL_OUTPUT_PORT: %s\nGPIO_OUTPUT_PIN: %s\nINPUT_GPIO_CHIP_NUMBER: %s\nPHYSICAL_INPUT_PORT: %s\nGPIO_INPUT_PIN: %s\n", data[1], data[2], data[3], data[4], data[5], data[6]
    }
}' <<< "$GPIO_LOOPBACK_PIN_MAPPING"
