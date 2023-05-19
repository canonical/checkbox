#!/bin/bash

device_check="true"
service_check="true"
fwts_supported="false"
fwts_check="true"


fwts_support_check(){
    echo -e "\n## Check if support fwts.."
    if  type -p fwts > /dev/null ; then
        echo "FWTS supported"
        fwts_supported="true"
    fi
}

run_fwts(){
    echo -e "\n## Run fwts of test: $*"
    fwts -r "$output_dir"/fwts_klog_oops.log "$@"
}

fwts_log_check(){
    echo -e "\n## Check fwts log failures.."
    fwts_log_path="$output_dir"/fwts_klog_oops.log
    if [[ -f "$fwts_log_path" ]]; then
        sleep_test_log_check.py -v --ignore-warning -t all "$output_dir"/fwts_klog_oops.log
        return_code=$?
        if [[ $return_code != 0 ]]; then
            fwts_check="false"
        fi
    else
        fwts_check="false"
    fi
}

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
        fwts_support_check
        if "$fwts_supported"; then
            run_fwts "klog" "oops"
            fwts_log_check
        fi
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
       [[ -n "$compare_dir" && "$device_check" == "false" ]] || \
       [[ -n "$fwts_opt" && "$fwts_check" == "false" ]]; then
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
    echo -e "\t-f    Do fwts log failures check"
}

service_opt=""
fwts_opt=""
output_dir=""
compare_dir=""
while getopts "d:c:sf" opt; do
    case "$opt" in
        d) output_dir="$OPTARG" ;;
        c) compare_dir="$OPTARG" ;;
        s) service_opt="True" ;;
        f) fwts_opt="True" ;;
        ?) help_function ;;
    esac
done

main
