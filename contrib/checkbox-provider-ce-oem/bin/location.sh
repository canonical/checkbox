#!/bin/bash
# Authors: Rick Wu <rick.wu@canonical.com>

if [ -f "/tmp/ttyUSB2.log" ]; then
        rm -f /tmp/ttyUSB2.log
fi
timeout 30 cat /dev/ttyUSB2 | tee -a /tmp/ttyUSB2.log &
echo "Check GPS status..."
echo -ne "AT+QGPS?\r" > /dev/ttyUSB2
grep "+QGPS: 1" /tmp/ttyUSB2.log
if [ $? = 1 ];then
    echo -e "GPS is not ON...\nTurning the GPS ON"
    echo -ne "AT+QGPS=1\r" > /dev/ttyUSB2
    sleep 2
else
    echo "GPS is ON"
fi
echo "Getting GPS location data..."
result=1
for i in {1..10};
do
    echo "Attempt number ${i}"
    echo -ne "AT+QGPSLOC=2\r" > /dev/ttyUSB2
    locations=$(grep "+QGPSLOC:" /tmp/ttyUSB2.log)
    if [[ $? = "1" ]]; then
        echo "GPS signal not fix..."
        sleep 2
    else
        echo "GPS signal is fix"
        result=0
        break
    fi
done
if [ $result == 1 ]; then
    echo "Can not get GPS location data.."
else
    latitude=$(echo "$locations" | awk -F, '{print $2}')
    longitude=$(echo "$locations" | awk -F, '{print $3}')
    echo "Latitude : ${latitude}" 
    echo "Longitude : ${longitude}"
fi
exit ${result}