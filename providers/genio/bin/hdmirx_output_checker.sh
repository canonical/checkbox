#!/bin/bash
# This file is part of Checkbox.
#
# Copyright 2014 Canonical Ltd.
# Authors:
#   Patrick Chang <patrick.chang@canonical.com>
#   Fernando Bravo <fernando.bravo.hernandez@canonical.com>
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

# This script is used to verify the output of the mtk_hdmirx_tool. 

verify_check_cable_output() {
    # $1 is the log file who records the output of hdmi_rx tool
    # $2 is the expected connection status. Such as "hdmi connected" or "hdmi disconnected"
    echo "Checking the status of HDMI connection ..."
    if ! grep -qw "$2" "$1" ; then
        echo " - FAIL: expect the status of HDMI connection to be '$2'"
        exit 1
    fi
    echo " - PASS: the status of HDMI connection is '$2'"
}

verify_check_video_locked_output() {
    # $1 is the log file who records the output of hdmi_rx tool
    # $2 is the expected lock status of video. Such as "video locked" or "video unlocked"
    if ! grep -qw "$2" "$1" ; then
        echo " - FAIL: expect the status of Video Lock to be '$2'"
        exit 1
    fi
    echo " - PASS: the status of Video Lock is '$2'"
}

verify_get_video_info_output() {
    # $1 is the log file who records the output of hdmi_rx tool
    # $2 is a string contains all expected values of v.hactive, v.vactive and v.frame_rate

    EXIT=0
    candidate_attributes=( "v.hactive" "v.vactive" "v.frame_rate" )
    IFS=' ' read -r -a expected_values <<< "$2"
    for index in "${!candidate_attributes[@]}";
    do
        echo "Checking the value of ${candidate_attributes[$index]} should be ${expected_values[$index]} ..."
        if ! grep -qw "${candidate_attributes[$index]} = ${expected_values[$index]}" "$1" ; then
            echo " - FAIL"
            EXIT=1
        else
            echo " - PASS"
        fi
    done
    exit $EXIT    
}

verify_get_audio_info_output() {
    # $1 is the log file who records the output of hdmi_rx tool
    # $2 is a string contains all expected values of "Bit Depth", "Channel Number" and "Sample Frequency"
    #    - usage example:
    #        expected_values="24 bits, Channel Number [2], 48.0 kHz"
    #        hdmirx_output_checker.sh <path_of_log_file> verify_get_audio_info_output "${expected_values}"
    EXIT=0
    candidate_sections=( "Audio Bits" "Audio Channel Info" "Audio Sample Freq" )
    IFS=',' read -r -a expected_values <<< "$2"
    for index in "${!candidate_sections[@]}";
    do
        echo "Checking the value '${expected_values[$index]}' should exist in ${candidate_sections[$index]} section ..."
        if ! grep -qw "${expected_values[$index]}" "$1" ; then
            echo " - FAIL"
            EXIT=1
        else
            echo " - PASS"
        fi
    done
    exit $EXIT    
}

help_function() {
    echo "This script is used to verify the output of hdmixrx_tool."
    echo
    echo "Usage: hdmirx_output_checker.sh <log_path> <action> <the remaining parameters>"
    echo
    echo "Log Path: A specific log path of stored output of hdmirx_tool"
    echo
    echo "Actions:"
    echo " verify_check_cable_output"
    echo " verify_check_video_locked_output"
    echo " verify_get_video_info_output"
    echo " verify_get_audio_info_output"
}

main(){
    # $1 is the log file who records the output of hdmi_rx tool
    case ${2} in
        verify_check_cable_output) verify_check_cable_output "${1}" "${3}" ;;
        verify_check_video_locked_output) verify_check_video_locked_output "${1}" "${3}" ;;
        verify_get_video_info_output) verify_get_video_info_output "${1}" "${3}" ;;
        verify_get_audio_info_output) verify_get_audio_info_output "${1}" "${3}" ;;
        *) help_function; exit
    esac
}

main "$@"
