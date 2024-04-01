#!/bin/bash

usb_dr_modes=()
udc_list=()

# A list "usb_dr_modes" to store the path of "dr_mode"
mapfile -t usb_dr_modes < <(find "/sys/firmware/devicetree/base/" -name "dr_mode")

# A list "udc_list" to store the "UDC" listed under sysfs
mapfile -t udc_list < <(ls "/sys/class/udc/")

# Path to mapping UDC and USB node
device_path="/sys/devices/platform/"

gadget_path="/sys/kernel/config/usb_gadget"
vid="0xabcd"
pid="0x1234"
language="0x409"  # specifically refers to the English language (English-US).

otg_info() {
    # Mapping following information: 
    # USB port, USB node, working mode(host/device/otg), UDC
    # Read -c list from checkbox var $OTG
    # e.g. OTG=USB-C1:11200000 USB-Micro:112a1000
    IFS=' ' read -ra usb_list <<< "$1"

    # For loop to split $OTG by space, we intend to map the USB node 
    # input by checkbox config to the USB node that exists in the system.
    for usb in "${usb_list[@]}"; do     
    
        # Split by ":" and assigne to "port" "node".
        IFS=':' read -r port node <<< "$usb"
    
        # For loop to mapping checkbox config to the dr_mode that exist in the system.
        for dr_mode_file in "${usb_dr_modes[@]}"; do
            
            # usb_node is the USB node of dr_mode
            usb_node=$(awk -F'[/@]' '{print $(NF-1)}' <<< "$dr_mode_file")

            # otg_mode is the working mode of the USB node. Could be in host/device/otg
            otg_mode=$(tr -d '\0' < "$dr_mode_file")

            # The USB ports and nodes input through the checkbox configuration 
            # will be mapped to the UDC (USB Device Controller) in the system.
            if [ "$node" == "$usb_node" ]; then
                echo -e "USB_port: $port"
                echo -e "USB_Node: $usb_node"
                echo -e "Mode: $otg_mode"
                found_udc="None"

                # For loop to mapping UDC to checkbox config
                # We observed a few patterns on different ARM-based platforms.
                for udc in "${udc_list[@]}"; do
                    
                    # UDC name is include USB node.
                    # UDC name is not the same as USB node, but can find USB node under UDC folder.
                    # UDC name is not the same as USB node, but can find UDC folder is under the USB node.
                    if [[ "$udc" == *"$usb_node"* ]] ||
                       [[ $(find "$device_path" -wholename "*/$udc/$usb_node*") ]] ||
                       [[ $(find "$device_path" -wholename "*$usb_node*/udc/$udc") ]]; then
                        found_udc="$udc"
                        break
                    fi
                done
                echo -e "UDC: $found_udc\n"
            fi
        done
    done
}

init_gadget() {
    # Remove the OTG gadget module if it has already been loaded, 
    # as loading the gadget module will occupy the USB port."
    IFS=',' read -ra modules <<< "$(lsmod | awk '/^libcomposite/ {print $4}')"
    echo -e "\nInfo: Attempting to remove preloaded gedget module ..."
    for module in "${modules[@]}"; do
        if [[ $module == g_* ]]; then
            echo -e "\nInfo: Removing $module ..."
            modprobe -r "$module"
            echo -e "\nInfo: Done!"
        fi
    done
    local probe_module configfs
    probe_module=$(lsmod | grep libcomposite)
    configfs=$(mount | grep configfs)
    if [ -z "$probe_module" ]; then
        echo -e "\nInfo: Probing libcomposite ..."
        modprobe libcomposite || exit 1
    else
        echo -e "\nInfo: libcomposite already probed!"
    fi
    if [ -z "$configfs" ]; then
        echo -e "\nInfo: Mounting configfs ..."
        mount -t configfs none "$(dirname "$gadget_path")" || exit 1
    else
        echo -e "\nInfo: configfs is already mounted!"
        echo -e "\n$configfs"
    fi
    echo -e "\nInfo: Done!"
}

create_gadget() {
    echo -e "\nInfo: Attempting to create gadget ..."
    if [ ! -d "$gadget_path/g1" ]; then
        mkdir "$gadget_path/g1" || exit 1
    fi
    if [ ! -d "$gadget_path/g1/strings/$language" ]; then
        mkdir "$gadget_path/g1/strings/$language" || exit 1
    fi
    echo "$vid" > "$gadget_path/g1/idVendor" || exit 1
    echo "$pid" > "$gadget_path/g1/idProduct" || exit 1
    echo -e "\nInfo: Done!"
}

create_config() {
    echo -e "\nInfo: Attempting to create config ..."
    if [ ! -d "$gadget_path/g1" ]; then
        create_gadget
    fi
    if [ ! -d "$gadget_path/g1/configs/c.1" ]; then
        mkdir "$gadget_path/g1/configs/c.1" || exit 1
    fi
    echo 120 > "$gadget_path/g1/configs/c.1/MaxPower" || exit 1
    echo -e "\nInfo: Done!"
}

create_function() {
    echo -e "\nInfo: Attempting to create function ..."
    local function=$1
    modprobe "usb_f_$function" || exit 1
    if [ ! -d "$gadget_path/g1/functions/$function.0" ]; then
        mkdir "$gadget_path/g1/functions/$function.0" || exit 1
    fi
    if [ "$function" == "mass_storage" ]; then
        tmp=$(mktemp -d)
        dd if=/dev/zero of="$tmp/lun0.img" bs=1M count=16
        mkdosfs -F 32 "$tmp/lun0.img"
        echo "$tmp/lun0.img" > "$gadget_path/g1/functions/$function.0/lun.0/file" || exit 1
    fi
    ln -s "$gadget_path/g1/functions/$function.0" "$gadget_path/g1/configs/c.1" || exit 1
    echo -e "\nInfo: Done!"
}

activate() {
    echo -e "\nInfo: Attempting to activate function ..."
    echo "$1" > "$gadget_path/g1/UDC" || exit 1
    echo -e "\nInfo: Done!"
}

teardown() {
    local function
    echo -e "\nInfo: Attempting to teardown ..."
    if [ -d "$gadget_path/g1" ]; then
        echo "" > "$gadget_path/g1/UDC" || exit 1
        for function in "$gadget_path/g1/configs/c.1/"*; do
            function=$(basename "$function")
            if [[ "$function" != "MaxPower" && "$function" != "bmAttributes" && "$function" != "strings" ]]; then
                rm -f "$gadget_path/g1/configs/c.1/$function"
                rmdir "$gadget_path/g1/functions/$function"
            fi
        done
        rmdir "$gadget_path/g1/configs/c.1/"
        rmdir "$gadget_path/g1/strings/$language"
        rmdir "$gadget_path/g1"
    else
        echo -e "\nInfo: $gadget_path/g1 is not exist"
    fi
    echo -e "\nInfo: teardown done!"
}


main() {
    if [[ -n "$udc" && -n "$function" ]]; then
        init_gadget
        create_gadget
        create_config
        create_function "$function"
        activate "$udc"
        echo -e "\nInfo: USB OTG gadget has been probed ...\"
                \nInfo: Press ENTER to teardown the test environment once your test is finied."
        read -r
        teardown
    elif [[ -n "$config" ]]; then
        otg_info "$config"
    fi
}


help_function() {
    echo "This script is used to test multiple USB OTG functions."
    echo
    echo "Usage: multiple-otg.sh -u {udc_address} -f [acm|ecm|mass_storage] -c {checkbox config argument OTG}"
    echo -e "\t-u    The UDC address under /sys/class/udc. e.g., 11201000.usb"
    echo -e "\t-f    Support function in acm/ecm/mass_storage."
    echo -e "\t-c    Checkbox config argument OTG"
}

while getopts "u:f:c:" opt; do
    case "$opt" in
        u) udc="$OPTARG" ;;
        f) function="$OPTARG" ;;
        c) config="$OPTARG" ;;
        ?) help_function ;;
    esac
done

if [[ -z "$udc" && -z "$function" && -z "$config" ]]; then
    echo -e "Error: Argument expected!!"
    help_function
    exit 1
fi

main
