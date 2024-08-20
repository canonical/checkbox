#!/bin/bash
export_gpio() {

    if [ ! -d "$gpio_node" ]; then
        echo "## Export GPIO $port to system"
        echo "$port" > /sys/class/gpio/export
        sleep 2
    fi

    if [ ! -d "$gpio_node" ]; then
        echo "## Unable to export GPIO $port"
        exit 1
    fi

    direction=$(cat "$gpio_node"/direction)
    if [ "$direction" != "$gpio_direct" ]; then
        echo "$gpio_direct" > "$gpio_node"/direction
    fi
}
 
test_button() {
    press_result="fail"
    release_result="fail"

    init_value=$(cat "$gpio_node"/value)
    echo "## Keep press $name button"
    i=0
    while [ $i -le 30 ]
    do
        press_value=$(cat "$gpio_node"/value)
        if [ "$init_value" != "$press_value" ]; then
            echo "PASS: $name button was pressed!"
            press_result="pass"
            break
        fi
        sleep 1
        i=$((i + 1))
    done
    if [ $press_result != "pass" ]; then
        echo "## Could not detect any signal while you press $name button"
        exit 1
    fi

    echo "## Release $name button"
    while [ $i -le 30 ]
    do
        rel_value=$(cat "$gpio_node"/value)
        if [ "$init_value" == "$rel_value" ]; then
            echo "PASS: $name button was released!"
            release_result="pass"
            break
        fi
        sleep 1
        i=$((i + 1))
    done
    if [ "$release_result" != "pass" ]; then
        echo "## the value is not match the origial value while you release $name button"
        exit 1
    fi
}

interrupts_button() {
    init_count=$(awk -v "key=$name" '$0~key {printf $2}' /proc/interrupts)
    if [ -z "$init_count" ]
    then
        echo "ERROR: $name button not found"
        exit 1
    fi
    echo "Press and release the $name button."
    i=0
    while [ $i -le 30 ]
    do
        curr_count=$(awk -v "key=$name" '$0~key {printf $2}' /proc/interrupts)
        if [ "$curr_count" -gt "$init_count" ] && [ $(((curr_count - init_count) % 2)) -eq 0 ]
        then
            echo "PASS: Interrupt detected!"
            exit 0
        fi
        sleep 1
        i=$((i + 1))
    done
    echo "ERROR: Interrupt detected fail"
    exit 1
}

main() {
    if [ "$type" == "gpio" ]; then
        gpio_node="/sys/class/gpio/gpio$port"
        gpio_direct="in"
        # Configure GPIO interface if needed
        export_gpio
        # Test button
        test_button
    else
        interrupts_button
    fi
}

help_function() {
    echo "This script is uses for test GPIO/interrupts button"
    echo "Will detect GPIO value or interrupts while user press button"
    echo
    echo "Usage: button_test.sh -t type -n button_name -p gpio_port"
    echo -e "\t-t    button test type. [gpio|interrupts]"
    echo -e "\t-n    button name."
    echo -e "\t-p    gpio port. for gpio_button test only."
}


while getopts "t:n:p:" opt; do
    case "$opt" in
        t) type="$OPTARG" ;;
        n) name="$OPTARG" ;;
        p) port="$OPTARG" ;;
        ?) help_function ;;
    esac
done

if  [[ "$type" != "gpio" && "$type" != "interrupts" ]]; then
    echo -e "Error: Test type is not supported!\n"
    help_function
    exit 1
fi

if [ -z "$name" ]; then
    echo -e "Error: Button name is needed!\n"
    help_function
    exit 1
fi

if [[ "$type" == "gpio" && -z $port ]]; then
    echo -e "Error: port number is needed for gpio button test!\n"
    help_function
    exit 1
fi
main