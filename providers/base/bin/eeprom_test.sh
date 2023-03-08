#!/bin/bash
eeprom_path=$(find /sys/devices/platform/ -name eeprom)
if [ ! "$eeprom_path" ];
then
echo "Error: Can't find EEPROM in system!!"
exit 1
fi
status=0
# This for loop is just in case multiple EEPROMs are on the platform. 
for eeprom in $eeprom_path
do
# Generates random data for test. 
data=$(echo $RANDOM | md5sum | head -c 10)
echo "Write data ${data} into ${eeprom}"
if (echo "$data" > "$eeprom")
then
    echo "Write data ${data} successfully"
    echo "Read data back from EEPROM"
    # Dump the content of EEPROM as a log.
    od -c < "$eeprom"
    # The content of EEPROM should be something like this:
    # root@ubuntu:~# cat "$eeprom_path"|od -c
    # 0000000   1   2   e   8   6   0   6   7   0   9  \n 377 377 377 377 377
    # 0000020 377 377 377 377 377 377 377 377 377 377 377 377 377 377 377 377
    # *
    # ...
    # So if we capture the first line of content for the EEPROM.
    # It will be 12e8606709, and it is exactly the data we put in.
    read_data=$(awk 'NR==1{printf $i}' "$eeprom")
    if [ "$data" == "$read_data" ];
    then
    echo "Read back data ${read_data} correct!"
    else
    echo "Read back data ${data} fail"
    status=1
    fi
else
    echo "Write data ${data} fail"
    status=1
fi
done
exit "$status"