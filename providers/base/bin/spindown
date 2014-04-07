#!/bin/bash
#
# Copyright (C) 2012 Canonical
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#

get_load_cycle()
{
	smartctl -A /dev/sda | grep Load_Cycle_Count | awk '{print $10}'	
}

get_time_secs()
{
	date "+%s"
}

if [ $EUID -ne 0 ]; then
	echo "Need to run as root e.g. use sudo"
	exit 1
fi

hdparm -B 127 /dev/sda

TEST_FILE=test
MAX_TIMEOUT=60
MAX_ITERATIONS=10

dirty_disk()
{
	rm -f ${TEST_FILE}
	touch ${TEST_FILE}
	truncate -s 4K ${TEST_FILE}
}

drop_caches()
{
	sync
	(echo 1 | sudo tee /proc/sys/vm/drop_caches) > /dev/null
	(echo 2 | sudo tee /proc/sys/vm/drop_caches) > /dev/null
	(echo 3 | sudo tee /proc/sys/vm/drop_caches) > /dev/null
}


find_load_cycle_threshold()
{
	lc1=0
	lc2=0
	count=0
	TIMEOUT=1

	echo Attempting to find Spin Down timeout for this HDD
	while [ $lc1 -eq $lc2 -a $TIMEOUT -lt $MAX_TIMEOUT ]
	do
		lc1=$(get_load_cycle)
		count=$((count + 1))

		dirty_disk
		drop_caches

		sleep $TIMEOUT
		lc2=$(get_load_cycle)
		n=$((lc2 - lc1))
		echo Checking with timeout: $TIMEOUT seconds, Load Cycles: $n
		if [ $TIMEOUT -lt 15 ]; then
			TIMEOUT=$((TIMEOUT + 1))
		else
			TIMEOUT=$((TIMEOUT + $TIMEOUT/5))
		fi
	done
}

exercise_load_cycle()
{
	echo "Attempting to exercise load cycle on HDD"

	i=0
	t1=$(get_time_secs)
	n1=$(get_load_cycle)
	# bump timeout by 1 second just to make sure 
	# we can always catch the load cycle window
	TIMEOUT=$((TIMEOUT + 1))

	while [ $i -lt $MAX_ITERATIONS ]
	do
		i=$((i + 1))
		echo "Load Cycle $i of $MAX_ITERATIONS"
		dirty_disk
		drop_caches
		sleep $TIMEOUT
	done

	i=0
	t2=$(get_time_secs)
	n2=$(get_load_cycle)

	t=$((t2 - t1))
	n=$((n2 - n1))

	echo "Managed to force $n Load Cycles in $t seconds."
	life=$((1000000 * $t / $n))
	days=$((life / (3600 * 24)))
	echo "At this rate, the HDD will fail after $days days."
}

find_load_cycle_threshold
if [ $TIMEOUT -lt $MAX_TIMEOUT ]; then
	echo "HDD seems to be spinning down aggressively."
	exercise_load_cycle
        exit 1
else
	echo "Gave up looking for Load Cycle timeout threshold, HDD looks sane."
        exit 0
fi


