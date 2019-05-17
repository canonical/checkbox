#!/bin/bash

if `grep -q "replaced by netplan" /etc/network/interfaces`; then
    # Get our configs from netplan
    for directory in "etc" "run" "lib"; do
        for configfile in `find /$directory/netplan -type f -name *.yaml`; do
            echo "Config File $configfile:"
            cat $configfile
            echo ""
        done
    done
else
    # get configs from Network Manager instead
    echo "Network Manager:"
    nmcli device show
fi
