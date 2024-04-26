#!/bin/bash

get_active_interfaces() {
    local net_state=$1
    # Get current network state
    ip -o link show | grep 'state UP' | awk -F ': ' '{print $2}' > "$net_state"
}

disable_net() {
    local target_interface=$1
    local default_net_state=$2
    parent_eth=$(grep -oP "(?<=$target_interface@)\w+" "$default_net_state")
    # Disable all network interfaces that are not under test
    while IFS= read -r line; do
        if [[ "$line" != *"$target_interface"* ]] && [[ "$line" != "$parent_eth" ]]; then
            echo "Attempting to disable $line"
            ip link set down dev "$line"
            sleep 3
        fi
    done < "$default_net_state"
}

restore_net() {
    local target_interface=$1
    local default_net_state=$2
    # Restore all network interfaces state
    while IFS= read -r line; do
        if [[ "$line" != *"$target_interface"* ]]; then
            echo "Attempting to restore $line"
            ip link set up dev "$line"
            sleep 3
        fi
    done < "$default_net_state"
}

check_resote_net() {
    for ((i=1; i <= 5; i++))
    do
        net_check=0
        restore_net "$src_if" "$original_net_state"
        sleep 20 # wait for every network interface up and get IP before exit
        get_active_interfaces "$current_net_state"
        if diff "$original_net_state" "$current_net_state" > /dev/null; then
            echo "Info: All network states are restored successfully."
            break
        else
            echo "Error: Not all network states are restored."
            echo "Info: Trying again."
            net_check=1
        fi
    done
    if [ "$net_check" -ne 0 ]; then
        echo "Error: Not able to restore network states."
        exit 1
    fi
}


tcp_echo() {
    local target=$1
    local port=$2
    local loop=$3
    local file=$4
    local inloop=1000
    if [ "$loop" -lt "$inloop" ]; then
        group_loop=1
        inloop="$loop"
    # Deal with the loop is not multiple of 1000.
    elif [ $((loop % inloop)) == 0 ]; then
        group_loop=$((loop / inloop))
    else
        group_loop=$((loop / inloop + 1))
    fi
    status=0
    # Dividing the whole test into a small test group, to prevent the cost to much effort to get a failure result.
    for ((x=1; x <= "$group_loop"; x++))
    do
        for ((i=1; i <= "$inloop"; i++))
        do
            # Redirect stdout and stderr to a variable while suppressing errors
            # Will use BASH /dev/tcp device to handle TCP socket.
            # Ref: https://tiswww.case.edu/php/chet/bash/bashref.html
            echo=$( (timeout 1 echo "ID-$x-$i: TCP echo test!" > /dev/tcp/"$target"/"$port") 2>&1 )
            # It will get empty value if the TCP echo success.
            if [[ -n "$echo" ]]; then
                echo "ID-$x-$i: TCP echo to $target port $port Failed!" | tee -a "$file"
                echo "$echo" >> "$file"
                status=1
            fi
        done
        # Stop testing if group test failed
        if [ "$status" -eq 1 ]; then
            break
        fi
    done
    return "$status"
}

main() {
    echo "Info: Attempting to test TCP echo stress ..."
    echo "Info: Disabling network interfaces that not under test ..."
    original_net_state=$(mktemp)
    current_net_state=$(mktemp)
    get_active_interfaces "$original_net_state"
    disable_net "$src_if" "$original_net_state"
    echo "Info: Checking if target is avaliable ..."
    start_time=$(date +%s)
    for ((i=1; i <= 5; i++))
    do
        ping_state=0
        if ping -I "$src_if" "$dst_ip" -c 3; then
            echo "Info: target is avaliable!"
            break
        else
            echo "Error: Retry ping!"
            ping_state=1
            sleep 5
        fi
    done
    if [ "$ping_state" -ne 0 ]; then
        echo "Error: target $dst_ip is unavaliable"
        echo "Info: Restore default network ..."
        check_resote_net
        exit 1
    fi
    echo "Info: Starting to test TCP ping stress."
    echo "Info: It will take time so please be patient."
    echo "Info: Will print out log when failed."
    if tcp_echo "$dst_ip" "$dst_port" "$loop" "$file"; then
        echo "Info: TCP stress test completed for $loop times!"
    else
        echo "Error: TCP stress test failed."
        echo "Info: Please refer to $file for more detail!"
    fi
    end_time=$(date +%s)
    interval=$(("$end_time" - "$start_time"))
    hours=$((interval / 3600))
    minutes=$((interval % 3600 / 60))
    seconds=$((interval % 60))
    echo "Time interval: $hours hours, $minutes minutes, $seconds seconds"
    echo "Info: Restore default network ..."
    check_resote_net
    if [ "$status" -ne 0 ]; then
        exit 1
    fi
}

help_function() {
    echo "This script is uses for TCP echo stress test."
    echo "Run nc command on the server before you start to test"
    echo "The following command can listen on certain port and direct message to log file."
    echo " $ nc -lk -p {port} | tee test.log"
    echo "Usage: tcpping.sh -s {src_eth_interface} -i {dst_IP} -p {dst_port} -l {num_of_loop} -o {file_to_log}"
    echo -e "\t-s    Source ethernet interface. e.g. eth0 or pfe0"
    echo -e "\t-i    Destination server IP address."
    echo -e "\t-p    Destination server port number, should be one of number in range 1024 to 65535"
    echo -e "\t-l    Number of the test loop."
    echo -e "\t-o    Output the fail log to file"
}

while getopts "s:i:p:l:o:" opt; do
    case "$opt" in
        s) src_if="$OPTARG" ;;
        i) dst_ip="$OPTARG" ;;
        p) dst_port="$OPTARG" ;;
        l) loop="$OPTARG" ;;
        o) file="$OPTARG" ;;
        ?) help_function ;;
    esac
done

if [[ -z "$src_if" || -z "$dst_ip" || -z "$dst_port" || -z "$loop" || -z "$file" ]]; then
    echo "Error: Source network interface, Destination IP address,port,\
 Number of test loop and the output file are needed!"
    help_function
    exit 1
fi

main
