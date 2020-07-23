#!/bin/bash

if grep -q "replaced by netplan" /etc/network/interfaces; then
    # Get our configs from netplan
    for directory in "etc" "run" "lib"; do
        while IFS= read -r -d '' configfile; do
            echo "Config File $configfile:"
            cat "$configfile"
            echo ""
        done <   <(find /$directory/netplan -type f -name "*.yaml" -print0)
    done
else
    # get configs from Network Manager instead
    echo "Network Manager:"
    nmcli device show
fi
