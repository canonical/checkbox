#!/bin/bash

device_check="true"
service_check="true"

service_check() {
    echo -e "\n## Check system service.."
    COUNT=$(systemctl --system --no-ask-password --no-pager --no-legend list-units --state=failed | wc -l)
    printf "Found %s failed units\n" "$COUNT"
    if [ "$COUNT" != 0 ]; then
        printf "\nFailed units:\n"
        systemctl --system --no-ask-password --no-pager list-units --state=failed
        service_check="false"
    fi
}

dump() {
    echo "## Dump the devices information to $output_dir.."
    mkdir -p "$output_dir"
    lspci -i "$SNAP"/usr/share/misc/pci.ids > "$output_dir"/lspci_log
    iw dev | grep "Interface\|addr\|ssid" > "$output_dir"/wifi_conn
    checkbox-support-lsusb -f "$CHECKBOX_RUNTIME"/var/lib/usbutils/usb.ids -s | sort > "$output_dir"/lsusb_log
    echo "dump devices complete"
    sync
}

compare() {
    echo -e "\n## Compare the devices.."
    if ! diff -u "$compare_dir"/lspci_log "$output_dir"/lspci_log; then
        echo "lspci mismatch during cycle"
        device_check="false"
    fi
    if ! diff -u "$compare_dir"/wifi_conn "$output_dir"/wifi_conn; then
        echo "wifi mismatch during cycle"
        device_check="false"
    fi
    if ! diff -u "$compare_dir"/lsusb_log "$output_dir"/lsusb_log; then
        echo "lsusb mismatch during cycle"
        device_check="false"
    fi

    [[ "$device_check" == "true" ]] && echo "Device match during reboot cycle"
}

main() {
    if  [[ -n "$output_dir" ]]; then
        dump
    fi

    if [[ -n "$compare_dir" ]]; then
        if  [[ -z "$output_dir" ]]; then
            echo -e "Error: Please provide output directory!\n"
            help_function
            exit 1
        fi
        compare
    fi

    if [[ -n "$service_opt" ]]; then
        service_check
    fi

    if [[ -n "$service_opt" && "$service_check" == "false" ]] || \
       [[ -n "$compare_dir" && "$device_check" == "false" ]]; then
        exit 1
    fi
}


help_function() {
    echo "This script is uses for collect device and compare the difference of device during every reboot iteration"
    echo
    echo "Usage: cold_reboot_by_pdu.sh -t type -p pud-ip:outlet-port"
    echo -e "\t-d    Output directory."
    echo -e "\t-c    The target directory for comparing device"
    echo -e "\t-s    Do service check"
}

service_opt=""
output_dir=""
compare_dir=""
while getopts "d:c:s" opt; do
    case "$opt" in
        d) output_dir="$OPTARG" ;;
        c) compare_dir="$OPTARG" ;;
        s) service_opt="True" ;;
        ?) help_function ;;
    esac
done

main
