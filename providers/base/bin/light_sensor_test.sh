#!/bin/bash

#Check if light sensor driver available, this section will be retired after checkbox resource jobs implement the light sensor in Device check
#Bug for reference LP #1864960 and LP #1980797
als_sensors=$(udevadm info --export-db|grep IIO_SENSOR_PROXY_TYPE |grep als)

#Check iio_sensor_als is ready and available first.
if [ -z "$als_sensors" ]
then
    echo "Light sensor is not found"
    exit 1
else
    echo "Light sensor is available"
    echo "$als_sensors"
fi

echo -e "\e[91mStart testing Ambient Light Sensor......\e[0m"
sleep 2
echo -e "\e[92mwaiting for sensor to be covered......\e[0m"
sleep 3

#Output and print light sensor events 5 sec to light_sensor_test.log
timeout 5 monitor-sensor | tee "$PLAINBOX_SESSION_SHARE"/light_sensor_test.log &


#Print backlight value for 5 sec on the screen
for i in {1..10}
do
    echo "Current Backlight Percentage is:" "$(gdbus call --session --dest org.gnome.SettingsDaemon.Power --object-path /org/gnome/SettingsDaemon/Power --method org.freedesktop.DBus.Properties.Get org.gnome.SettingsDaemon.Power.Screen Brightness)"| tr -d '()<>,'
    sleep 0.5
done

# Fail when the user didn't wave their hand and no events have been collected.
if [[ $(grep -c "Light changed" "$PLAINBOX_SESSION_SHARE"/light_sensor_test.log) -lt 5 ]]; then
echo -e "\e[91mFAIL: Not enough data to be collect, Please rerun the test case and wave your hand around Light Sensor.\e[0m"
exit 1
fi


#Print 5 values of the Light sensor value form log file
for i in {1..5}
do 
    echo "Ambient light sensor value $i: " "$(grep 'Light' "$PLAINBOX_SESSION_SHARE"/light_sensor_test.log | awk '{print $3}' | sed -n "$i"p)"
done
exit 0

