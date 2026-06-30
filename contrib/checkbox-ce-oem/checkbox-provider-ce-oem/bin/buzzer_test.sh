#!/bin/bash
export_pwm() {

    if [ ! -d "$node" ]; then
        echo "## Export PWM $port on PWM Chip $chipnum to system"
        echo "$port" > /sys/class/pwm/pwmchip"$chipnum"/export
        sleep 2
    fi

    if [ ! -d "$node" ]; then
        echo "## Unable to export PWM $port on PWM Chip $chipnum"
        exit 1
    fi
}

export_gpio() {

    if [ ! -d "$node" ]; then
        echo "## Export GPIO $port to system"
        echo "$port" > /sys/class/gpio/export
        sleep 2
    fi

    if [ ! -d "$node" ]; then
        echo "## Unable to export GPIO $port"
        exit 1
    fi

    direction=$(cat "$node"/direction)
    if [ "$direction" != "$direct" ]; then
        echo "$direct" > "$node"/direction
    fi
}

has_gpiod() {
    which gpioset > /dev/null 2>&1 && \
    which gpioinfo > /dev/null 2>&1 && \
    which gpiodetect > /dev/null 2>&1 && \
    which gpioget > /dev/null 2>&1
}

resolve_gpio_by_name() {
    # Resolve a GPIO line name to gpio_chip and gpio_offset using gpioinfo output.
    # Avoids relying on chip numbers which can change
    # between power cycles depending on driver probe order.
    local gpio_name="$1"
    local gpioinfo_dump found

    # Prefer the no-argument form (libgpiod >= 1.5 lists all chips at once).
    # Fall back to gpiodetect + per-chip gpioinfo for older libgpiod.
    if ! gpioinfo_dump="$(gpioinfo 2>/dev/null)" || [ -z "$gpioinfo_dump" ]; then
        gpioinfo_dump="$(
            gpiodetect | awk '{print $1}' | while read -r c; do
                gpioinfo "$c"
            done
        )"
    fi

    found="$(
        printf '%s\n' "$gpioinfo_dump" | awk -v target="$gpio_name" '
            BEGIN { found=0 }
            /^gpiochip[0-9]/ {
                chip = $1
                next
            }
            index($0, "\"" target "\"") {
                offset = $2
                sub(/:$/, "", offset)
                printf "%s %s\n", chip, offset
                found = 1
                exit
            }
            END { exit (found ? 0 : 1) }
        '
    )" || {
        echo "Error: cannot resolve GPIO name '${gpio_name}'" >&2
        echo "----- gpioinfo dump begin -----" >&2
        printf '%s\n' "$gpioinfo_dump" >&2
        echo "----- gpioinfo dump end -----" >&2
        return 1
    }

    # shellcheck disable=SC2086
    set -- $found
    gpio_chip="$1"
    gpio_offset="$2"
    return 0
}

run_gpioset() {
    value="$1"

    # gpioset keeps the line requested while the process is alive.
    # Stop any previous gpioset process first so we can safely set a new value.
    if [ -n "$gpioset_pid" ] && kill -0 "$gpioset_pid" 2>/dev/null; then
        kill "$gpioset_pid" 2>/dev/null || true
        # wait reaps the old process and releases its line request cleanly.
        wait "$gpioset_pid" 2>/dev/null || true
    fi

    # Run gpioset in background so this script can continue to interactive steps
    # while gpioset keeps driving the GPIO value.
    if gpioset --help 2>&1 | grep -q -- '--chip'; then
        gpioset -c "$gpio_chip" "${gpio_offset}=${value}" &
    else
        gpioset "$gpio_chip" "${gpio_offset}=${value}" &
    fi

    gpioset_pid=$!
    sleep 0.1

    if kill -0 "$gpioset_pid" 2>/dev/null; then
        return 0
    fi

    wait "$gpioset_pid" 2>/dev/null
    return 1
}

cleanup_gpioset() {
    # Ensure no gpioset process is left behind after the script exits.
    if [ -n "$gpioset_pid" ] && kill -0 "$gpioset_pid" 2>/dev/null; then
        kill "$gpioset_pid" 2>/dev/null || true
        wait "$gpioset_pid" 2>/dev/null || true
    fi
}

setup_gpio_backend() {
    use_gpiod=0

    # Prefer GPIO line names through gpiod when those tools are available.
    if has_gpiod; then
        if ! resolve_gpio_by_name "$port"; then
            exit 1
        fi

        use_gpiod=1
        echo "## Use gpiod backend on ${gpio_chip} line ${gpio_offset} (resolved from name '${port}')"
        return
    fi

    echo "gpiod tools not available, falling back to legacy sysfs GPIO export"
    # if the port is a number, then use sysfs GPIO export.
    if [[ ! "$port" =~ ^[0-9]+$ ]]; then
        echo "Error: GPIO name format '${port}' requires gpioset/gpioinfo/gpioget"
        exit 1
    fi

    if [ ! -d /sys/class/gpio ]; then
        echo "Error: /sys/class/gpio is not available on this system"
        exit 1
    fi

    node="/sys/class/gpio/gpio$port"
    direct="out"
    echo "## Use sysfs GPIO backend on gpio$port"
    export_gpio
}

test_pwm_buzzer() {
    # Make sounds with different musical scale by pwm
    echo "Configure $type chip$chipnum pwm$port"
    echo "Setting up duty cycle to 0.125 sec"
    echo '125000' > "$node"/duty_cycle

    for i in 262 277 294 311 330 349 370 392 415;
    do
        pd=$((1000000000 / "$i"))
        echo "Setting up period to $pd nano seconds"
        echo "$pd" > "$node"/period
        sleep 0.8
    done

}

test_buzzer() {
    result_pre="Buzzer $name test"

    echo "## $type is activated"
    echo "## Start $type Buzzer $name test"
    echo "## Set $type $port to $enable"
    if [ "$type" == 'gpio' ]; then
        if [ "$use_gpiod" == '1' ]; then
            if ! run_gpioset "$enable"; then
                echo "Error: failed to set GPIO ${gpio_chip}:${gpio_offset} to ${enable}"
                exit 1
            fi
        else
            enable_node="$node"/value
            echo "$enable" > "$enable_node"
        fi
    else
        enable_node="$node"/enable
        echo "$enable" > "$enable_node"
        test_pwm_buzzer
    fi

    while true
    do
        echo "Do you hear the sound from buzzer $name? (y/n)"
        read -r result
        if [ "$result" == "n" ]; then
            echo "$result_pre: FAILED"
            exit 1
        elif [ "$result" == "y" ]; then
            break
        fi
    done

    echo "## Set $type $port to $disable"
    if [ "$type" == 'gpio' ] && [ "$use_gpiod" == '1' ]; then
        if ! run_gpioset "$disable"; then
            echo "Error: failed to set GPIO ${gpio_chip}:${gpio_offset} to ${disable}"
            exit 1
        fi
    else
        echo "$disable" > "$enable_node"
    fi
    while true
    do
        echo "Is the buzzer $name stop? (y/n)"
        read -r result
        if [ "$result" == "n" ]; then
            echo "$result_pre: FAILED"
            exit 1
        elif [ "$result" == "y" ]; then
            break
        fi
    done
    echo "$result_pre: PASSED"
}

main() {
    if [ "$enable" == "1" ]; then
        disable=0
    else
        disable=1
    fi
    if [ "$type" == "gpio" ]; then
        # Prefer gpiod when available, fallback to legacy sysfs export.
        setup_gpio_backend
    elif [ "$type" == "pwm" ]; then
        node="/sys/class/pwm/pwmchip$chipnum/pwm$port"
        direct="out"
        export_pwm
    else
        echo "Error: Unknown type!!"
        exit 1
    fi
    # Test buzzer
    test_buzzer
}

trap cleanup_gpioset EXIT

help_function() {
    echo "This script is uses for test GPIO/PWM buzzer"
    echo "Will change GPIO/PWM value to make a sound from buzzer"
    echo
    echo "Usage: button_test.sh -t type -n button_name -p gpio_port -e [0|1]"
    echo -e "\t-e    the state to make a sound from buzzer. [0|1]"
    echo -e "\t-n    button name."
    echo -e "\t-p    gpio or pwm port. GPIO accepts a line name when gpiod tools are available, otherwise a global GPIO number."
    echo -e "\t-c    pwm chip number"
    echo -e "\t-t    type of test target in gpio or pwm"
}

while getopts "n:p:e:t:c:" opt; do
    case "$opt" in
        n) name="$OPTARG" ;;
        p) port="$OPTARG" ;;
        e) enable="$OPTARG" ;;
        t) type="$OPTARG" ;;
        c) chipnum="$OPTARG" ;;
        ?) help_function ;;
    esac
done

if [[ -z $name || -z $port || -z $enable || -z $type ]]; then
    echo -e "Error: Button name, port number, type and enable-state is needed!\n"
    help_function
    exit 1
elif [ "$type" == 'pwm' ] && [ -z "$chipnum" ]; then
    echo -e "Error: Chip number is needed if type in PWM!\n"
    help_function
    exit 1
fi
main