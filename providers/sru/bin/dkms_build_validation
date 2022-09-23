#!/bin/bash
# Copyright 2017 Canonical Ltd.
# Written by:
#   Taihsiang Ho (tai271828) <taihsiang.ho@canonical.com>
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

ubuntu_release=`lsb_release -r | cut -d ':' -f 2 | xargs`

if [ $ubuntu_release = '22.04' ]; then
    kernel_ver_min=`dkms status | awk -F ', ' {'print $2'} | sort -V | uniq | head -1`
    kernel_ver_max=`dkms status | awk -F ', ' {'print $2'} | sort -V | uniq | tail -1`
else
    kernel_ver_min=`dkms status | awk -F ', ' {'print $3'} | sort -V | uniq | head -1`
    kernel_ver_max=`dkms status | awk -F ', ' {'print $3'} | sort -V | uniq | tail -1`
fi
kernel_ver_current=`uname -r`

number_dkms_min=`dkms status | grep $kernel_ver_min | grep installed | wc -l`
number_dkms_max=`dkms status | grep $kernel_ver_max | grep installed | wc -l`

scan_log="/var/log/apt/term.log"

# kernel_ver_max should be the same as kernel_ver_current
if [ "$kernel_ver_current" != "$kernel_ver_max" ]; then
    echo "Current using kernel version does not match the latest built DKMS module."
    echo "Your running kernel: $kernel_ver_current"
    echo "Latest DKMS module built on kernel: $kernel_ver_max"
    echo "Maybe the target DKMS was not built,"
    echo "or you are not running the latest available kernel."
    echo
    echo "=== DKMS status ==="
    dkms status
    exit 1
fi

# compare the number of dkms modules of min and max kernels
if [ "$number_dkms_min" -ne "$number_dkms_max" ]; then
    echo "$number_dkms_min modules for $kernel_ver_min"
    echo "$number_dkms_max modules for $kernel_ver_max"
    echo "DKMS module number is inconsistent. Some modules may not be built."
    echo
    echo "=== DKMS status ==="
    dkms status
fi

# scan the APT log during system update
error_message="Bad return status for module build on kernel: $kernel_ver_current"
error_in_log=`grep "$error_message" $scan_log | wc -l`
if [ "$error_in_log" -gt 0 ]; then
   echo "Found dkms build error messages in $scan_log"
   echo
   echo "=== build log ==="
   grep "$error_message" $scan_log -A 5 -B 5
   exit 1
fi

