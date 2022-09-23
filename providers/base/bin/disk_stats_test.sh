#!/bin/bash

#Simple script to gather some data about a disk to verify it's seen by the OS
#and is properly represented.  Defaults to sda if not passed a disk at run time

DISK="sda"
STATUS=0

check_return_code() {
    if [ "${1}" -ne "0" ]; then
        echo "ERROR: retval ${1} : ${2}" >&2
        if [[ $STATUS -eq 0 ]]; then
            STATUS=${1}
        fi
        if [ $# -gt 2 ]; then
            shift
            shift
            for item in "$@"; do
                echo "output: ""$item"
            done
        fi
    fi
}

if [[ "$1" != '' ]]; then
    DISK="$1"
fi

nvdimm="pmem"
if [ -z "${DISK##*"$nvdimm"*}" ];then
    echo "Disk $DISK appears to be an NVDIMM, skipping"
    exit "$STATUS"
fi

#Check /proc/partitions, exit with fail if disk isn't found
grep -w -q "$DISK" /proc/partitions
check_return_code $? "Disk $DISK not found in /proc/partitions"

#Next, check /proc/diskstats
grep -w -q -m 1 "$DISK" /proc/diskstats
check_return_code $? "Disk $DISK not found in /proc/diskstats"

#Verify the disk shows up in /sys/block/
ls /sys/block/*"$DISK"* > /dev/null 2>&1
check_return_code $? "Disk $DISK not found in /sys/block"

#Verify there are stats in /sys/block/$DISK/stat
[[ -s "/sys/block/$DISK/stat" ]]
check_return_code $? "stat is either empty or nonexistant in /sys/block/$DISK/"

#Get some baseline stats for use later
PROC_STAT_BEGIN=$(grep -w -m 1 "$DISK" /proc/diskstats)
SYS_STAT_BEGIN=$(cat /sys/block/"$DISK"/stat)

#Generate some disk activity using hdparm -t
hdparm -t "/dev/$DISK" 2&> /dev/null

#Sleep 5 to let the stats files catch up
sleep 5

#Make sure the stats have changed:
PROC_STAT_END=$(grep -w -m 1 "$DISK" /proc/diskstats)
SYS_STAT_END=$(cat /sys/block/"$DISK"/stat)

[[ "$PROC_STAT_BEGIN" != "$PROC_STAT_END" ]]
check_return_code $? "Stats in /proc/diskstats did not change" \
    "$PROC_STAT_BEGIN" "$PROC_STAT_END"

check_return_code $? "Stats in /sys/block/$DISK/stat did not change" \
    "$SYS_STAT_BEGIN" "$SYS_STAT_END"

if [[ $STATUS -eq 0 ]]; then 
    echo "PASS: Finished testing stats for $DISK"
fi

exit "$STATUS"
