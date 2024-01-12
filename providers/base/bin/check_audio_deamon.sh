#!/bin/bash

if [ -z "$(command -v pactl)" ]; then
    if [ -n "$(command -v pw-cli)" ] ;then
        echo "Daemon is pipewire, use pipewire function"
        exit 0
    else
        # shouldn't be here,
        # if requires: package.name in ['pulseaudio-utils', 'pipewire']
        echo "No pipewire or pulseaudio installed!! Stop test"
        exit 2
    fi
elif pactl info | grep -iq pipewire ; then
    echo "Daemon is pipewire, use pipeiwre function"
    exit 0
else
    echo "Daemon is pulseaudio, use pulseaudio function"
    exit 1
fi
