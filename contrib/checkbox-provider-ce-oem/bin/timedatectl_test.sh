#!/bin/bash
set -e
snap="test-strict-confinement.timedatectl"

get_timezone (){
    $snap 2>&1 | grep -oP "Time zone:\s+\K\S+"
}

set_timezone (){
    $snap -a "set-timezone $1"
}

get_ntp (){
    $snap 2>&1 | grep -oP "NTP service:\s+\K\S+"
}

set_ntp (){
    $snap -a "set-ntp $1"
}

get_date (){
    $snap 2>&1 | grep -oP "Local time:\s\D{3}\s\K\d{4}-\d{2}-\d{2}"
}

set_date (){
    $snap -a "set-time $1"
}

check_timezone (){
    # check_timezone takes one arguments. timezone.
    # e.g. check_timezone Asia/Taipei
    echo "Info: Attempting to set timezone to $1"
    set_timezone "$1"
    current_timezone="$(get_timezone)"
    echo "Info: Current Timezone is $current_timezone"
    if [ "$current_timezone" = "$1" ]; then
        echo "Info: Timezone setting successfully!"
    else
        echo "Error: Timezone setting failed!"
        exit 1
    fi
}

toggle_ntp (){
    # toggle_ntp takes one arguments. toggle true or false.
    # e.g. toggle_ntp {true|false}
    expect_status="active"
    if [ "$1" = false ]; then
        expect_status="inactive"
    fi
    echo "Info: Attempting to toggle NTP service $expect_status ..."
    set_ntp "$1"
    if [ "$(get_ntp)" != "$expect_status" ]; then
        echo "Error: NTP service failed to toggled to $expect_status"
        exit 1
    fi
    echo "Info: NTP service is now $expect_status"
}

restore_ntp (){
    # restore_ntp takes one arguments. Restore to active or inactive.
    # e.g. restore_nt {active|inactive}
    echo "Info: Restore NTP setting..."
    if [ "$1" = "active" ]; then
        toggle_ntp true
    else
        toggle_ntp false
    fi
}

test_timezone (){
    # This function intends to test if the sysyem is able to set
    # timezone and restore it.
    ori_timezone="$(get_timezone)"
    target_timezone="Asia/Taipei"
    if [ "$ori_timezone" = "Asia/Taipei" ]; then
        target_timezone="UTC"
    fi
    echo "Info: Starting to test setting timezone ..."
    echo "Info: Original timezone is $ori_timezone"
    echo "Info: Starting timezone test ..."
    check_timezone "$target_timezone"
    echo "Info: Restore timezone ..."
    check_timezone "$ori_timezone"
}

test_ntp (){
    # This function intends to test following
    # 1. If the NTP service can be toggle active and inactive.
    # 2. Able to set system local time to a certain date while NTP
    #    service is inactive.
    # 3. System local time is able to sync with NTP while NTP service
    #    is active.

    ori_ntp="$(get_ntp)"
    if [ "$ori_ntp" = "active" ]; then
        toggle_ntp false
    fi
    mock_date="2024-02-09"
    echo "Info: Attempting to set date to a mock up date $mock_date"
    set_date "$mock_date"
    date="$(get_date)"
    if [ "$date" != "$mock_date" ]; then
        echo "Error: Set date failed!"
        exit 1
    fi
    echo "Info: Mock up date set and checked."
    echo "Info: Local date is $date"
    echo "Info: Starting to test NTP sync."
    toggle_ntp true
    sleep 3
    date="$(get_date)"
    echo "Info: Local date is $date"
    if [ "$date" != "$mock_date" ]; then
        echo "Info: Date is sync up with NTP server."

    else
        echo "Error: Date is not sync up with NTP server."
        restore_ntp "$ori_ntp"
        exit 1
    fi
    restore_ntp "$ori_ntp"
}

main (){
    case "$function" in
        "timezone" )
            test_timezone ;;
        "ntp" )
            test_ntp ;;
        * )
            echo "Error: Unknown function to test!"
            exit 1
    esac
}

help_function() {
    echo "This script is uses for test datetimectl to set time, timezone and NTP sync."
    echo
    echo "Usage: timedatectl_test.sh -f {test_function}. {timezone|ntp}"
    echo -e "\t-f    The function to test. We have two functions are able to test. {timezone|ntp}"
}

while getopts "f:" opt; do
    case "$opt" in
        f) function="$OPTARG" ;;
        ?) help_function ;;
    esac
done

if [[ -z $function ]]; then
    echo -e "Error: test function is needed!\n"
    help_function
    exit 1
fi

main
