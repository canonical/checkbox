#!/usr/bin/env bash

awk '{
        count = split($0, record, " ")
        for (i = 1; i <= count; i++) {
            split(record[i], data, ":")
            if (length(data) == 2) {
                # Example: BUZZER_EN:1
                #   BUZZER_EN is the GPIO line name
                #   You can find the name via /sys/kernel/debug/gpio or the gpioinfo command
                port = data[1]
                enable_value = data[2]
            } else if (length(data) == 3) {
                # Example: buzzer1:498:0
                port = data[2]
                enable_value = data[3]
            }
            printf "name: %s\nport: %s\nenable_value: %s\n\n", data[1], port, enable_value
        }
    }' <<< "$GPIO_BUZZER"
