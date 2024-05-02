#!/bin/bash

ip=""
outlet_port=""
pdu_type=""
reboot_duration=""

cold_reboot_raritan() {
    echo "Turn off the power of DUT by Raritan network PDU.."
    echo "System should be back after around $reboot_duration seconds.."
    echo ""
    # change duration of power reboot
    oid=".1.3.6.1.4.1.13742.6.3.5.3.1.12.1.$outlet_port"
    i=0
    result="fail"
    while [ $i -le 3 ]
    do
        echo "## change the duration of power reboot"
        snmpset -c private -v2c "$ip" "$oid" u "$reboot_duration" > /dev/null
        ret="$?"
        if [ "$ret" == 0 ]; then
            echo "changed the duration successfully!"
            result="pass"
            break
        fi
        sleep 1
        i=$((i + 1))
    done

    if [ $result == "fail" ]; then
        echo "## failed to change the duration of power reboot"  >&2
        exit 1
    fi

    # power cycle a outlet with delay
    echo ""
    oid=".1.3.6.1.4.1.13742.6.4.1.2.1.2.1.$outlet_port"
    i=0
    result="fail"
    while [ $i -le 3 ]
    do
        echo "## trigger a cold reboot by network PDU.."
        # 0: power on, 1: power off, 2: power cycle
        snmpset -c private -v2c "$ip" "$oid" i 2 > /dev/null
        ret="$?"
        if [ "$ret" == 0 ]; then
            echo "trigger a cold reboot successfully!"
            result="pass"
            break
        fi
        sleep 1
        i=$((i + 1))
    done
    if [ $result == "fail" ]; then
        echo "## failed to trigger a cold reboot" >&2
        exit 1
    fi
}

cold_reboot_apc() {
    echo "Turn off the power of DUT by APC network PDU.."
    echo "System should be back after around $reboot_duration seconds.."
    echo ""

    # change the duration of power reboot
    oid="1.3.6.1.4.1.318.1.1.4.5.2.1.5.$outlet_port"
    i=0
    result="fail"
    while [ $i -le 3 ]
    do
        echo "## change the duration of power reboot"
        snmpset -v1 -c private "$ip" "$oid" integer "$reboot_duration" > /dev/null
        ret="$?"
        if [ "$ret" == 0 ]; then
            echo "changed the duration successfully!"
            result="pass"
            break
        fi
        sleep 1
        i=$((i + 1))
    done
    if [ $result == "fail" ]; then
        echo "## failed to change the duration of power reboot"  >&2
        exit 1
    fi

    # power cycle a outlet with delay
    echo ""
    oid="1.3.6.1.4.1.318.1.1.4.4.2.1.3.$outlet_port"
    i=0
    result="fail"
    while [ $i -le 3 ]
    do
        echo "## trigger a cold reboot by network PDU.."
        # 1: power on, 2: power off, 3: power cycle
        snmpset -v1 -c private "$ip" "$oid" integer 3 > /dev/null
        ret="$?"
        if [ "$ret" == 0 ]; then
            echo "trigger a cold reboot successfully!"
            result="pass"
            break
        fi
        sleep 1
        i=$((i + 1))
    done
    if [ $result == "fail" ]; then
        echo "## failed to trigger a cold reboot" >&2
        exit 1
    fi
}


main() {
    ip=$(echo "$pdu_var" | awk -F ':' '{print $1}')
    outlet_port=$(echo "$pdu_var" | awk -F ':' '{print $2}')

    if [[ -z "$ip" || -z "$outlet_port" ]]; then
        echo -e "Error: PDU variable format is unexpected!\n"
        help_function
        exit 1
    fi

    case "$pdu_type" in
        apc) cold_reboot_apc;;
        raritan) cold_reboot_raritan;;
        *)
            echo -e "Error: Network PDU type is not supported!\n"
            help_function
            exit 1
            ;;
    esac
}

help_function() {
    echo "This script is uses for trigger a cold reboot test by network PDU"
    echo
    echo "Usage: cold_reboot_by_pdu.sh -t type -p pud-ip:outlet-port"
    echo -e "\t-t    Network PDU type. [apc]"
    echo -e "\t-p    Network PDU IP and outlet port. e.g. 10.120.33.44:2"
    echo -e "\t-d    Reboot delay duration. Default delay is 60 (seconds)"
}

while getopts "t:p:d:" opt; do
    case "$opt" in
        t) pdu_type="$OPTARG" ;;
        p) pdu_var="$OPTARG" ;;
        d) reboot_duration="$OPTARG" ;;
        ?) help_function ;;
    esac
done

if  [ -z "$pdu_type" ]; then
    echo -e "Error: Network PDU variable is needed!\n"
    help_function
    exit 1
fi

if [ -z "$pdu_var" ]; then
    echo -e "Error: PDU variable is needed!\n"
    help_function
    exit 1
fi

if [ -z "$reboot_duration" ]; then
    echo -e "Applied 60s to the Reboot delay duration!\n"
    reboot_duration=60
fi

main
