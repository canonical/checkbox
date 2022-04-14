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
INSTALL_DATASOURCE=""
SUBIQUITY_LOG_FILE1="/var/log/installer/subiquity-info.log" # Observed on 20.04
SUBIQUITY_LOG_FILE2="/var/log/installer/subiquity-server-info.log" # Observed on 22.04
CONFIRM_INSTALL_TYPE="maas" # or "subiquity", maybe others in future
RETVAL="0"

get_params() {
    # Default to equivalent of --maas; the option is provided for clarity
    # in calling script.
    while [[ $# -gt 0 ]]; do
        case $1 in
            --maas|-m)
                CONFIRM_INSTALL_TYPE="maas" # should already be set
                ;;
            --iso|-i)
                CONFIRM_INSTALL_TYPE="subiquity"
                ;;
            *) echo "Usage: $0 [ -m, --maas ] | [ -i, --iso ]"
                ;;
        esac
        shift
    done
    INSTALL_DATASOURCE_FOUND=0 # Should be found for both MAAS & subiquity
    MAAS_IP_FOUND=0            # Should be found for MAAS but not subiquity
    MAAS_VERSION_FOUND=0       # Should be found for MAAS but not subiquity
    SUBIQUITY_LOG_FOUND=0      # Should be found for subiquity but not MAAS
}

# Context-sensitive echo() function; prints the message only if the program
# is launched to confirm a MAAS installation
conditional_print() {
    if [[ "$CONFIRM_INSTALL_TYPE" == "$2" ]] ; then
        echo "$1"
    fi
}

# Find the installation data source, as recorded in cloud installer files.
# This should be present for both MAAS and subiquity installs.
get_install_datasource() {
    # Is the file there?
    if [ -s $DATASOURCE_FILE ]; then
        INSTALL_DATASOURCE=$(cut -d "[" -f 2 $DATASOURCE_FILE | cut -d "]" -f 1)
        echo "Installation data source is $INSTALL_DATASOURCE"
        INSTALL_DATASOURCE_FOUND=1
    else
        echo "ERROR: The installation data source file ($DATASOURCE_FILE)"
        echo "cannot be found."
    fi
}

# Verify that the $INSTALL_DATASOURCE points to a valid IP address.
# Note: Function assumes that $INSTALL_DATASOURCE is already set, as is
# done by the get_install_datasource() function.
verify_maas_ip() {
    if [[ $INSTALL_DATASOURCE_FOUND == 1 ]]; then
        MAAS_HOSTNAME=$(echo "$INSTALL_DATASOURCE" | cut -d "/" -f 3 | cut -d ":" -f 1)
        HOST_OUTPUT=$(host "$MAAS_HOSTNAME" | grep "has address")
        status=$?
        if [[ $status -eq 0 ]]; then
            MAAS_IP=$(echo "$HOST_OUTPUT" | cut -d " " -f 4)
            conditional_print "MAAS server's IP address is $MAAS_IP" "maas"
            conditional_print "ERROR: MAAS server's IP address is $MAAS_IP" "subiquity"
            MAAS_IP_FOUND=1
        else
            conditional_print "ERROR: Unable to determine MAAS server's IP address" "maas"
        fi
    fi
}

# Pull the MAAS version information from a file left here by the
# Server Certification pre-seed file
get_maas_version() {
    # Is the file there?
    if [ -s $MAAS_FILE ]; then
        maas_version=$(cat $MAAS_FILE)
        conditional_print "MAAS version is $maas_version" "maas"
        conditional_print "ERROR: Server Certification MAAS version file found; MAAS version is $maas_version" "subiquity"
        MAAS_VERSION_FOUND=1
    else
        conditional_print "ERROR: The MAAS version cannot be determined" "maas"
    fi
}

find_subiquity_log() {
    if [[ -f "$SUBIQUITY_LOG_FILE1" || -f "$SUBIQUITY_LOG_FILE2" ]]; then
        conditional_print "ERROR: Subiquity log file found" "maas"
        conditional_print "subiquity log file found" "subiquity"
        SUBIQUITY_LOG_FOUND=1
    else
        conditional_print "ERROR: Subiquity log file not found" "subiquity"
    fi
}

#######################
#
# Main program begins here....
#
#######################

get_params "$@"

# Check for various installation signatures....
get_install_datasource
verify_maas_ip
get_maas_version
find_subiquity_log

MAAS_FOUND=$((INSTALL_DATASOURCE_FOUND && MAAS_IP_FOUND && MAAS_VERSION_FOUND))
SUBIQUITY_FOUND=$((INSTALL_DATASOURCE_FOUND && SUBIQUITY_LOG_FOUND))

if [[ $CONFIRM_INSTALL_TYPE == "maas" ]] ; then
    RETVAL=$((! MAAS_FOUND)) || SUBIQUITY_FOUND
    if [[ $RETVAL == 0 ]] ; then
        echo "PASS: System appears to have been installed by MANIACS-compliant MAAS."
    else
        echo "FAIL: System appears to have not been installed by MANIACS-compliant MAAS."
    fi
elif [[ $CONFIRM_INSTALL_TYPE == "subiquity" ]] ; then
    RETVAL=$((! SUBIQUITY_FOUND)) || MAAS_FOUND
    if [[ $RETVAL == 0 ]] ; then
        echo "PASS: System appears to have been installed by a Subiquity ISO."
    else
        echo "FAIL: System appears to have not been installed by a Subiquity ISO."
    fi
fi

exit $RETVAL
