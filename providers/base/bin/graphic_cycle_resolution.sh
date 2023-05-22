#!/bin/bash
# shellcheck disable=SC1091

while [ $# -gt 0 ]
do
    case "$1" in
        --index)
            shift
            INDEX=$1
        ;;
        --after-suspend)
            shift
            KEYWORD="after_suspend"
        ;;
        *)
            echo "Not recognize $1"
            usage
        ;;
    esac
    shift
done

if [[ $XDG_SESSION_TYPE == "wayland" ]]
then
    gnome_randr_cycle.py --keyword="${INDEX}_${KEYWORD}" --screenshot-dir="$PLAINBOX_SESSION_SHARE"
else
    xrandr_cycle.py --keyword="${INDEX}_${KEYWORD}" --screenshot-dir="$PLAINBOX_SESSION_SHARE"
fi