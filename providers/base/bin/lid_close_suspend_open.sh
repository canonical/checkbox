#! /usr/bin/bash
prev_suspend_number=$(cat /sys/power/suspend_stats/success)
echo "Number of successful suspends until now: $prev_suspend_number"
echo "Please close the lid and wait for 5 sec to make it suspend~"
echo "============================================================="
echo ""
runTime="10 second"
endTimeout=$(date -d "$runTime" +%s)
echo "Wait for lid close ..."
echo "-------------------------------------------------------------"
while [ "$(date +%s)" -le "$endTimeout" ]
do
    state=$(cat /proc/acpi/button/lid/*/state | awk '{print $2}')
    echo "Lid state: $state"
    if [ "$state" = "closed" ]
    then
        echo "Wait for lid open ..."
        echo "-------------------------------------------------------------"
        endTimeout=$(date -d "$runTime" +%s)
        now_suspend_number="-1"
        while [ "$(date +%s)" -le "$endTimeout" ]
        do
            state=$(cat /proc/acpi/button/lid/*/state | awk '{print $2}')
            if [ "$state" = "open" ]
            then
                echo "Lid state: $state"
                echo "Checking the number of successful suspends until now ..."
                now_suspend_number=$(cat /sys/power/suspend_stats/success)
                echo "Number of successful suspends until now: $now_suspend_number"
                echo ""
                if [ "$now_suspend_number" -gt "$prev_suspend_number" ]
                then
                    echo "============================================================="
                    echo "Suspend checking successful!!!"
                    exit 0
                else
                    sleep 0.5
                fi
            else
                sleep 0.5
            fi
        done
        echo "============================================================="
        if [ "$now_suspend_number" -eq "-1" ]
        then
            echo "Lid is not opened within $runTime!!! Please try again~~"
        else
            echo "This DUT didn't suspend successfully!!!"
        fi
        exit 1
    else
        sleep 0.5
    fi
done
echo "============================================================="
echo "Lid is not closed within $runTime!!!"
exit 1
