#!/bin/bash

# Copyright (C) 2012-2022 Canonical Ltd.

# Authors
#  Jeff Lane <jeff@ubuntu.com>
#  Rod Smith <rod.smith@canonical.com>

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3,
# as published by the Free Software Foundation.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

MAAS_FILE="/etc/installed-by-maas"
DATASOURCE_FILE="/var/lib/cloud/instance/datasource"
MAAS_DATASOURCE=""
RETVAL="0"

# Find the MAAS data source, as recorded in cloud installer files
get_maas_datasource() {
    # Is the file there?
    if [ -s $DATASOURCE_FILE ]; then
        MAAS_DATASOURCE=$(cut -d "[" -f 2 $DATASOURCE_FILE | cut -d "]" -f 1)
        echo "MAAS data source is $MAAS_DATASOURCE"
    else
        echo "ERROR: This system does not appear to have been installed by MAAS"
        echo "ERROR: " "$(ls -l $DATASOURCE_FILE 2>&1)"
        RETVAL="1"
    fi
}

# Verify that the $MAAS_DATASOURCE points to a valid IP address.
# Note: Function assumes that $MAAS_DATASOURCE is already set, as is
# done by the get_maas_datasource() function.
verify_maas_ip() {
    if [[ $RETVAL == 0 ]]; then
        MAAS_HOSTNAME=$(echo "$MAAS_DATASOURCE" | cut -d "/" -f 3 | cut -d ":" -f 1)
        HOST_OUTPUT=$(host "$MAAS_HOSTNAME" | grep "has address")
        status=$?
        if [[ $status -eq 0 ]]; then
            MAAS_IP=$(echo "$HOST_OUTPUT" | cut -d " " -f 4)
            echo "MAAS server's IP address is $MAAS_IP"
        else
            echo "ERROR: Unable to determine MAAS server's IP address"
            RETVAL=1
        fi
    fi
}

# Pull the MAAS version information from a file left here by the
# Server Certification pre-seed file
get_maas_version() {
    # Is the file there?
    if [ -s $MAAS_FILE ]; then
        maas_version=$(cat $MAAS_FILE)
        echo "MAAS version is $maas_version"
    else
        echo "ERROR: The MAAS version cannot be determined"
        echo "ERROR: " "$(ls -l $MAAS_FILE 2>&1)"
        RETVAL="1"
    fi
}

get_maas_datasource
verify_maas_ip
get_maas_version

exit $RETVAL
