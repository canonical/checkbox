#!/bin/bash

for i in $(mmcli --simple-status -L | \
               awk '/freedesktop\/ModemManager1\/Modem/ {print $1;}'); do
        mmcli -m $i
done
