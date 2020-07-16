#!/bin/bash
#
# This file is part of Checkbox.
#
# Copyright 2014-2020 Canonical Ltd.
#
# Checkbox is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3,
# as published by the Free Software Foundation.

#
# Checkbox is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Checkbox.  If not, see <http://www.gnu.org/licenses/>.
#

MMCLI_PATH=$(command -v mmcli)

if [ -x "$MMCLI_PATH" ]; then
    # Use mmcli to query for modem capabilities
    for i in $(mmcli --simple-status -L 2>/dev/null || mmcli -L | \
               awk '/freedesktop\/ModemManager1\/Modem/ {print $1;}'); do
        mmcli -m "$i" | grep -q "supported: .*gsm-umts.*" && GSM=yes
        mmcli -m "$i" | grep -q "supported: .*cdma.*" && CDMA=yes
    done
    [ "$GSM" = "yes" ] && echo "gsm: supported"
    [ "$CDMA" = "yes" ] && echo "cdma: supported"
fi
exit 0
