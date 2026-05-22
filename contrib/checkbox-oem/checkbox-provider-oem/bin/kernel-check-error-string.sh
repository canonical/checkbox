#!/bin/bash

error_string="$1"

while read -r line
do
    bootidx=$(echo "$line" | awk '{print $1}')
    if journalctl -k -b "$bootidx" -g "$error_string" > /dev/null; then
        echo "Boot $line, found \"$error_string\""
        exit 1
    fi
done < <(journalctl --list-boots)

echo "No $error_string"
