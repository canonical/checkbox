#!/bin/bash

SESSION_ID=$(loginctl --no-legend --value list-sessions | awk '/seat/ { print $1 }')
SESSION_TYPE=$(loginctl show-session "$SESSION_ID" -p Type)

if [ -n "$DISPLAY" ]; then
    echo "Get DISPLAY from environment variable"
else
    if [ "$SESSION_TYPE" = "Type=wayland" ]; then
        STR=$(pgrep -a "Xwayland")
        NO_WAYLAND_STR=${STR#*Xwayland }
        DISPLAY=${NO_WAYLAND_STR/ */}
    elif [ "$SESSION_TYPE" = "Type=x11" ]; then
        DISPLAY=$(w | grep gnome-session | awk '{ print $3 }')
    else
        echo "Unsupported session type"
        exit 1
    fi
fi

if [ "${DISPLAY:0:1}" != ":" ]; then
    echo "No valid display for the gnome-session"
    exit 1
fi

while read -r line;
do
    if [ "${line:0:22}" = "OpenGL renderer string" ]; then
        if [ "${line:24:8}" = "llvmpipe" ]; then
            echo "${line}"
            echo "Please check if the ID is supported by upstream mesa."
            echo "Here is an example:"
            echo "https://gitlab.freedesktop.org/mesa/mesa/-/blob/main/include/pci_ids/iris_pci_ids.h"
            echo "And check if the supported ID has been backported to ubuntu, LP: #1998893."
            exit 1
        fi
    fi
done< <(glxinfo -B -display "$DISPLAY")
