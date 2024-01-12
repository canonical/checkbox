#!/bin/bash
export_gpio() {
    if [ ! -d "$gpio_node" ]; then
        echo "## Export GPIO $port to system"
        echo "$port" > "$path"/export
        sleep 2
    fi

    if [ ! -d "$gpio_node" ]; then
        echo "## Unable to export GPIO $port"
        exit 1
    fi
    echo "out" > "$gpio_node"/direction
}

test_gpio_leds() {
    echo "Testing $name on GPIO $port ..."
    ori_status=$(cat "$gpio_node"/value)
    i=0
    while [ "$i" -le 3 ]; do
        for y in 0 1; do
            echo "$y" > "$gpio_node"/value
            sleep 1
        done
        i=$((i+1))
    done
    echo "$ori_status" > "$gpio_node"/value
}

test_sysfs_leds() {
    ori_status=$(cat /sys/class/leds/"$name"/brightness)
    for i in $(seq 1 3); do
        for y in 1 0 ; do
            echo $y > /sys/class/leds/"$name"/brightness
            test "cat /sys/class/leds/$name/brightness" == $y || exit 1
            sleep 1
        done
    done
    echo "$ori_status" > /sys/class/leds/"$name"/brightness
}

main() {
    if [ "$type" == "gpio" ]; then
        path="/sys/class/gpio"
        gpio_node="$path/gpio$port"
        # Configure GPIO interface if needed
        export_gpio
        # Test button
        test_gpio_leds
    else
        test_sysfs_leds
    fi
}

help_function() {
    echo "This script is uses for test GPIO/SYSFS leds"
    echo "Will light GPIO/SYSFS leds up"
    echo
    echo "Usage: leds_test.sh -t led_type -n led_name -p gpio_port"
    echo -e "\t-t    led type [gpio|sysfs]"
    echo -e "\t-n    led name"
    echo -e "\t-p    gpio port"
}


while getopts "t:n:p:" opt; do
    case "$opt" in
        t) type="$OPTARG" ;;
        n) name="$OPTARG" ;;
        p) port="$OPTARG" ;;
        ?) help_function ;;
    esac
done

if [ -z "$type" ]; then
    echo -e "Error: LED type is needed!"
    help_function
    exit 1
elif [ "$type" == "gpio" ]; then   
    if [ -z "$name" ] && [ -z "$port" ]; then
        echo -e "Error: LED name and GPIO port number is needed for GPIO LED test.\n"
        help_function
        exit 1
    fi
else
    if [ -z "$name" ]; then
        echo -e "Error: LED name is needed for SYSFS LED test.\n"
        help_function
        exit 1
    fi
fi
main