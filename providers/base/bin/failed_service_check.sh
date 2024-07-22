#!/bin/bash

COUNT=$(systemctl --system --no-ask-password --no-pager --no-legend list-units --state=failed | wc -l)
printf "Found %s failed units\n" "$COUNT"
if [ "$COUNT" -eq 0 ]; then
    exit 0
else
    printf "\nFailed units:\n"
    systemctl --system --no-ask-password --no-pager list-units --state=failed

    for service in $(systemctl --system --no-ask-password --no-pager --no-legend list-units --state=failed --plain | awk '{print $1}'); do
        printf "\nLogs for %s:\n" "$service"
        journalctl -u "$service" | tail -n 50
    done
fi
exit 1
