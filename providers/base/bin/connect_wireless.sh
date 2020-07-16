#!/bin/bash

# Check nmcli version
NMCLI_GTE_0_9_10=0
nmcli general 2>&1 >/dev/null
if [ $? -eq 0 ]; then
    NMCLI_GTE_0_9_10=1
fi

# Any active connections?
conn=''

if [ $NMCLI_GTE_0_9_10 -eq 0 ]; then
    active_connection=$(nmcli -f SSID,ACTIVE dev wifi list | grep yes)
    if [ $? -eq 0 ]; then
        ap=$(echo $active_connection | awk -F\' '{print $2}')
        conn=$(nmcli -t -f UUID,TYPE,NAME con list | grep wireless | grep -e "$ap$" | head -n 1 | awk -F\: '{print $1}')
    else
        conn=$(nmcli -t -f UUID,TYPE con list | grep wireless | head -n 1 | awk -F\: '{print $1}')
    fi
else
    active_connection=$(nmcli -f SSID,ACTIVE dev wifi | grep yes)
    if [ $? -eq 0 ]; then
        ap=$(echo $active_connection | awk '{print $1}')
        conn=$(nmcli -t -f UUID,TYPE,NAME con show | grep wireless | grep -e "$ap$" | head -n 1 | awk -F\: '{print $1}')
    else
        conn=$(nmcli -t -f UUID,TYPE con show | grep wireless | head -n 1 | awk -F\: '{print $1}')
    fi
fi

#Strip trailing/leading whitespace
conn=$(echo $conn |sed 's/^[ \t]*//;s/[ \t]*$//')

# Find out if wireless is enabled
if [ $NMCLI_GTE_0_9_10 -eq 0 ]; then
    nmcli nm wifi | grep -q 'enabled'
else
    nmcli radio wifi | grep -q 'enabled'
fi
if [ $? -ne 0 ]
then
    # Find out why
    rfkill list wifi | grep 'Hard blocked' | grep -q yes
    if [ $? -eq 0 ]
    then
        blkmessage='Your wireless may be hardware blocked. You may need
                    to use your wireless key/switch to re-enable it.'
        echo $blkmessage
    fi
fi

# Check if there's a connection already (wireless or otherwise)
nmcli dev status | grep -q '\<connected\>'
if [ $? -eq 0 ]
then
    # Disconnect, pause for a short time
    for iface in `(nmcli -f GENERAL dev list 2>/dev/null || nmcli -f GENERAL dev show) | grep 'GENERAL.DEVICE' | awk '{print $2}'`
    do
        if [ $NMCLI_GTE_0_9_10 -eq 0 ]; then
            nmcli dev disconnect iface $iface
        else
            nmcli dev disconnect $iface
        fi
    done
    sleep 2
fi

nmcli con up uuid "$conn"
