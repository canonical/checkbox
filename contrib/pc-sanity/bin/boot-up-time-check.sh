#!/bin/bash
#
# Expected that on boot up time must be less than 2 minutes based on systemd-analyze results
#

echo "The graphical.target status is:"
if (systemctl is-active graphical.target); then
    if [[ $(cat /etc/X11/default-display-manager) == "/usr/sbin/gdm3" ]]; then
        systemctl is-active --quiet gdm3.service || RET=$?
        if [[ "$RET" -ne 0 ]]; then
            echo "gdm3.service is not active. Exit code: $RET"
            exit "$RET"
        fi

        OUTPUT=$(systemd-analyze)
        BOOTUP_TIME=$(echo "$OUTPUT" | grep "Startup finished.*=" | cut -d "=" -f2 | sed -n 's/^ *\([0-9]*\)min.*/\1/p')
        # BOOTUP_TIME is an empty string when less than 1min

        if [[ -n "$BOOTUP_TIME" && "$BOOTUP_TIME" -ge 2 ]]; then
            echo "Boot up time was 2 minutes or longer:"
            echo "$OUTPUT"
            exit 1
        fi

        exit 0
    fi
fi
