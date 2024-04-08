#!/bin/bash
# This file is part of Checkbox.
#
# Copyright 2014 Canonical Ltd.
# Authors:
#   Patrick Chang <patrick.chang@canonical.com>
#   Fernando Bravo <daniel.manrique@canonical.com>
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

# This script is used to interact with the mtk_hdmirx_tool. You can find the source
# code of mtk_hdmi_rx from the following link:
#   - https://gitlab.com/mediatek/aiot/bsp/mtk-hdmirx-tool
#
# The following output is the first glance of hdmi-rx-tool
# User can choose any action to manipulate with it.
#
#   root@mtk-genio:/home/ubuntu# genio-test-tool.hdmi-rx-tool
#   hdmirx tool version:   1.0.0
#   hdmirx driver version: 1.0.0
#
#   1) enable hdmi      2) disable hdmi
#   3) get device info  4) check cable
#   5) get video info   6) check video locked
#   7) get audio info   8) check audio locked
#   a) start observing  b) stop observing
#   h) help             q) quit
#


run_expect() {
# $1 is the timeout value, once it occurs, the process of expect will be closed automatically
# $2 is the available action options provided by hdmi-rx-tool
    expect -c "
    # Initialization
    set timeout $1
    log_file $LOG_PATH
    spawn genio-test-tool.hdmi-rx-tool
    sleep 0.5
    send \"\r\"
    expect getchar=

    # Send command with specific action
    send \"$2\r\"

    # Block until timeout
    expect pending
    "
}

enable_hdmi() {
    # Timeout 1 second and perform number 1 action
    run_expect 1 1
}

disable_hdmi() {
    # Timeout 1 second and perform number 2 action
    run_expect 1 2
}

get_device_info() {
    # Timeout 1 second and perform number 3 action
    run_expect 1 3
}

check_cable() {
    # Timeout 1 second and perform number 4 action
    run_expect 1 4
}

get_video_info() {
    # Timeout 1 second and perform number 5 action
    run_expect 1 5
}

check_video_locked() {
    # Timeout 1 second and perform number 6 action
    run_expect 1 6
}

get_audio_info() {
    # Timeout 1 second and perform number 7 action
    run_expect 1 7
}

check_audio_locked() {
    # Timeout 1 second and perform number 8 action
    run_expect 1 8
}

start_observing() {
    # Timeout 15 seconds and perform number a action
    # It will monitor the event while plugging/unplugging HDMI cable to HDMI RX port on DUT
    run_expect 15 a
}

help_function() {
    echo "This script is used to interact with genio-test-tool.hdmi-rx-tool"
    echo
    echo "Usage: hdmirx_tool_runner.sh <log_path> <action>"
    echo
    echo "Log Path: A specific path for storing the output of hdmi-rx-tool"
    echo
    echo "Actions:"
    echo " enable_hdmi"
    echo " disable_hdmi"
    echo " get_device_info"
    echo " check_cable"
    echo " get_video_info"
    echo " check_video_locked"
    echo " get_audio_info"
    echo " check_audio_locked"
    echo " start_observing"
}

main(){
    LOG_PATH=${1}
    case ${2} in
        enable_hdmi) enable_hdmi ;;
        disable_hdmi) disable_hdmi ;;
        get_device_info) get_device_info ;;
        check_cable) check_cable ;;
        get_video_info) get_video_info ;;
        check_video_locked) check_video_locked ;;
        get_audio_info) get_audio_info ;;
        check_audio_locked) check_audio_locked ;;
        start_observing) start_observing ;;
        *) help_function; exit
    esac
}

main "$@"
