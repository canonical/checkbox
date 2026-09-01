#!/usr/bin/env bash

KEYWORDS="hardware-transmit
          hardware-receive
          hardware-raw-clock"
for iface in /sys/class/net/*; do
    iface=${iface##*/}
    supported=true
    if [[ $iface == e* ]]; then
        output=$(ethtool -T "$iface")
        for keyword in $KEYWORDS; do
            if ! grep -q "$keyword" <<< "$output"; then
                supported=false
                break
            fi
        done
        if [[ $supported == true ]]; then
            echo "eth-interface: $iface"
            echo
        fi
    fi
done
