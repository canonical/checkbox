#!/bin/sh

set -e

# Script to verify that all network interfaces have predictable names
#
# Copyright (c) 2018 Canonical Ltd.
#
# Authors
#   dann frazier <dann.frazier@canonical.com>
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
# The purpose of this script is to identify any network interfaces
# that do not have a predictable name. See:
#   https://www.freedesktop.org/wiki/Software/systemd/PredictableNetworkInterfaceNames/
#
# Usage:
#   network_predictable_names.sh
#
# Parameters:
#   None

failed=0

for iface in /sys/class/net/*; do
    iface=${iface##*/}

    if [ "${iface}" != "${iface#eth}" ]; then
	echo "** Error: Network interface $iface is not a predictable name"
	failed=1
    fi
done

exit $failed
