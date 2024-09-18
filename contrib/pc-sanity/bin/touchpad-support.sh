#!/bin/bash
# shellcheck disable=SC2317
export LANG=C
set -euo pipefail

print_help()
{
    cat <<ENDLINE
$0 [OPTIONS]

OPTIONS:
    -p | --pressure        Check if touchpad support pressure event.
    -h | --help            Print the help manual.
ENDLINE
}

touchpad_pressure_support()
{
    while read -r line;
    do
        if [ "${line:3:4}" = "Name" ]; then
            name="${line:9:-1}"
        fi
        if [ "${line:3:3}" = "ABS" ]; then
            abs_caps="${line:7:15}"
            abs_caps_hex=$((16#"$abs_caps"))
            mt_position_x_bit=$((abs_caps_hex >> 53))
            mt_position_y_bit=$((abs_caps_hex >> 54))
            mt_support=$((mt_position_x_bit & mt_position_y_bit & 1))
            if [ $mt_support -eq 1 ]; then
                pressure_bit=$((abs_caps_hex >> 24))
                mt_pressure_bit=$((abs_caps_hex >> 58))
                support=$((pressure_bit & mt_pressure_bit & 1))

                if [ $support -eq 1 ]; then
                    echo "$name pressure bit and mt pressure bit are set"
                    exit 1
                else
                    echo "$name has no pressure capability"
                    exit 0
                fi
            fi
        fi
    done <"/proc/bus/input/devices"

    echo "Touchpad not found."
    exit 1
}

OPTS="$(getopt -o ph --long pressure,help -n 'touchpad-support.sh' -- "$@")"
eval set -- "${OPTS}"
while :; do
    case "$1" in
        ('-p'|'--pressure')
            touchpad_pressure_support
            exit ;;
        ('-h'|'--help')
            print_help
            exit ;;
        (*)
            print_help
            exit ;;
    esac
done
