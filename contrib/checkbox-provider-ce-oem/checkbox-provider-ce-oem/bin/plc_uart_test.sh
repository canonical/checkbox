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

port=$1
uart_device=$2

gpio_node="/sys/class/gpio/gpio$port"
gpio_direct="out"
tmp_file=$(mktemp)
RET=$?
if [ "$RET" -ne 0 ]; then
    echo "Error: Can't create temp file, Exists.."
    exit 1
fi

export_gpio

echo "Pull high for GPIO $port"
echo 1 > "$gpio_node"/value
echo "Initial a serial connection to $uart_device"
stty -F "$uart_device" 115200 raw
echo "send message to $uart_device"
echo -ne "\x16\x16\x24\x02\x00\x00\x00\x00\x00\x00\x03\x00\xAB\x9F" > "$uart_device"

echo "Switch GPIO $port from low to high"
echo 0 > "$gpio_node"/value && sleep 1 && echo 1 > "$gpio_node"/value

echo
echo "Capture serial console logs to $tmp_file"
(timeout 15 cat "$uart_device" | od -t x1) | tee "$tmp_file"

echo
echo "Validate the console output via $uart_device"
check_pattern="16 16 01 02 00 00 00 00 00 00 00 00 85 31 16 16"
i=0
while [ $i -le 30 ]
do
    grep "$check_pattern" "$tmp_file" && echo "PASS: PLC reset message detected" && exit 0
    sleep 1
    i=$((i + 1))
done
echo "ERROR: PLC reset message detected fail"
exit 1