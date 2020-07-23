#!/bin/bash

# Script to test CPU load imposed by a simple disk read operation
#
# Copyright (c) 2016 Canonical Ltd.
#
# Authors
#   Rod Smith <rod.smith@canonical.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3,
# as published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# The purpose of this script is to run disk stress tests using the
# stress-ng program.
#
# Usage:
#   disk_cpu_load.sh [ --max-load <load> ] [ --xfer <mebibytes> ]
#                    [ --verbose ] [ <device-filename> ]
#
# Parameters:
#  --max-load <load> -- The maximum acceptable CPU load, as a percentage.
#                       Defaults to 30.
#  --xfer <mebibytes> -- The amount of data to read from the disk, in
#                        mebibytes. Defaults to 4096 (4 GiB).
#  --verbose -- If present, produce more verbose output
#  <device-filename> -- This is the WHOLE-DISK device filename (with or
#                       without "/dev/"), e.g. "sda" or "/dev/sda". The
#                       script finds a filesystem on that device, mounts
#                       it if necessary, and runs the tests on that mounted
#                       filesystem. Defaults to /dev/sda.


set -e


get_params() {
    disk_device="/dev/sda"
    verbose=0
    max_load=30
    xfer=4096
    while [ $# -gt 0 ] ; do
        case $1 in
            --max-load) max_load="$2"
                shift
                ;;
            --xfer) xfer="$2"
                shift
                ;;
            --verbose) verbose=1
                ;;
            *) disk_device="/dev/$1"
               disk_device=$(echo "$disk_device" | sed "s/\/dev\/\/dev/\/dev/g")
               if [ ! -b "$disk_device" ] ; then
                   echo "Unknown block device \"$disk_device\""
                   echo "Usage: $0 [ --max-load <load> ] [ --xfer <mebibytes> ]"
                   echo "             [ device-file ]"
                   exit 1
               fi
               ;;
        esac
        shift
    done
} # get_params()


# Find the sum of all values in an array
# Input:
#   $1 - The array whose values are to be summed
# Output:
#   $total - The sum of the values
sum_array() {
    local array=("${@}")
    total=0
    for i in "${array[@]}"; do
        (( total+=i ))
    done
} # sum_array()


# Compute's CPU load between two points in time.
# Input:
#   $1 - CPU statistics from /proc/stat from START point, in a string of numbers
#   $2 - CPU statistics from /proc/stat from END point, in a string of numbers
#   These values can be obtained via $(grep "cpu " /proc/stat | tr -s " " | cut -d " " -f 2-)
# Ouput:
#   $cpu_load - CPU load over the two measurements, as a percentage (0-100)
compute_cpu_load() {
    local start_use
    local end_use
    IFS=' ' read -r -a start_use <<< "$1"
    IFS=' ' read -r -a end_use <<< "$2"
    local diff_idle
    (( diff_idle=end_use[3]-start_use[3] ))

    sum_array "${start_use[@]}"
    local start_total=$total
    sum_array "${end_use[@]}"
    local end_total=$total

    local diff_total
    local diff_used
    (( diff_total=end_total-start_total ))
    (( diff_used=diff_total-diff_idle ))

    if [ "$verbose" == "1" ] ; then
        echo "Start CPU time = $start_total"
        echo "End CPU time = $end_total"
        echo "CPU time used = $diff_used"
        echo "Total elapsed time = $diff_total"
    fi

    if [ "$diff_total" != "0" ] ; then
        cpu_load=$(echo "($diff_used*100)/$diff_total" | bc)
    else
        cpu_load=0
    fi
} # compute_cpu_load()


#
# Main program body....
#

get_params "$@"
retval=0
echo "Testing CPU load when reading $xfer MiB from $disk_device"
echo "Maximum acceptable CPU load is $max_load"
blockdev --flushbufs "$disk_device"
start_load="$(grep "cpu " /proc/stat | tr -s " " | cut -d " " -f 2-)"
if [ "$verbose" == "1" ] ; then
    echo "Beginning disk read...."
fi
dd if="$disk_device" of=/dev/null bs=1048576 count="$xfer" &> /dev/null
if [ "$verbose" == "1" ] ; then
    echo "Disk read complete!"
fi
end_load="$(grep "cpu " /proc/stat | tr -s " " | cut -d " " -f 2-)"
compute_cpu_load "$start_load" "$end_load"
echo "Detected disk read CPU load is $cpu_load"
if [ "$cpu_load" -gt "$max_load" ] ; then
    retval=1
    echo "*** DISK CPU LOAD TEST HAS FAILED! ***"
fi
exit $retval
