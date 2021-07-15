#!/bin/bash

while read -r line
do
    bootidx=$(echo "$line" | cut -d " " -f1)
    if journalctl -k -b "$bootidx" | grep -q "Microcode SW error detected"; then
        echo "Boot $line, Microcode SW error detected"
        exit 1
    fi
done < <(journalctl --list-boots)

echo "No Microcode SW error detected"
