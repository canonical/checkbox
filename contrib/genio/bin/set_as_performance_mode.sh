#!/bin/bash
set -e

STORE_HOUSE=/var/tmp/performance-setting

if [ -d "${PLAINBOX_SESSION_SHARE}" ]; then
    STORE_HOUSE="${PLAINBOX_SESSION_SHARE}"/performance-setting
fi

if ! [ -d "$STORE_HOUSE" ]; then
    mkdir "$STORE_HOUSE"
fi

MALI_SOC="13000000.mali"

get_current_setting() {
# $1 is the specific device platform. e.g. G1200-evk
    echo "===== Current Configuration ====="
    if [ "${1}" == "G1200-evk" ]; then
        for i in 0 4
        do
            echo "- /sys/devices/system/cpu/cpufreq/policy$i/scaling_governor:"
            cat /sys/devices/system/cpu/cpufreq/policy$i/scaling_governor
        done
    elif [ "${1}" == "G700" ]; then
        for i in 0 6
        do
            echo "- /sys/devices/system/cpu/cpufreq/policy$i/scaling_governor:"
            cat /sys/devices/system/cpu/cpufreq/policy$i/scaling_governor
        done
        for i in {0..2}
        do
            # shellcheck disable=SC2027
            echo "- /sys/class/thermal/thermal_zone0/trip_point_""$i""_temp"
            cat /sys/class/thermal/thermal_zone0/trip_point_"$i"_temp
        done
    elif [ "${1}" == "G350" ]; then
        for i in {0..3}
        do
            echo "- /sys/devices/system/cpu/cpu$i/cpufreq/scaling_governor"
            cat /sys/devices/system/cpu/cpu"$i"/cpufreq/scaling_governor
        done
    fi
    echo "- /sys/devices/platform/soc/$MALI_SOC/devfreq/$MALI_SOC/governor:"
    cat /sys/devices/platform/soc/"$MALI_SOC"/devfreq/"$MALI_SOC"/governor
    echo "- /sys/class/thermal/thermal_zone0/mode:"
    cat /sys/class/thermal/thermal_zone0/mode
    echo
}

store_setting() {
# $1 is the specific device platform. e.g. G1200-evk
    echo "===== Store current config into ${STORE_HOUSE} directory ====="
    if [ "${1}" == "G1200-evk" ]; then
        for i in 0 4
        do
            cat /sys/devices/system/cpu/cpufreq/policy$i/scaling_governor > "$STORE_HOUSE"/p"$i"_sg
        done
    elif [ "${1}" == "G700" ]; then
        for i in 0 6
        do
            cat /sys/devices/system/cpu/cpufreq/policy$i/scaling_governor > "$STORE_HOUSE"/p"$i"_sg
        done
        for i in {0..2}
        do
            cat /sys/class/thermal/thermal_zone0/trip_point_"$i"_temp > "$STORE_HOUSE"/"$i"_temp
        done
    elif [ "${1}" == "G350" ]; then
        cat /sys/devices/system/cpu/cpufreq/policy0/scaling_governor > "$STORE_HOUSE"/p0_sg
    fi
    cat /sys/devices/platform/soc/"$MALI_SOC"/devfreq/"$MALI_SOC"/governor > "$STORE_HOUSE"/mali_g
    echo "Store Done"
    echo
}

set_to_performance_mode() {
# $1 is the specific device platform. e.g. g1200-evk
    echo "===== Set to performance mode ====="
    if [ "${1}" == "G1200-evk" ]; then
        for i in 0 4
        do
            echo "performance" > /sys/devices/system/cpu/cpufreq/policy$i/scaling_governor
        done
        # disable cpuidle
        toggle_cpuidle_state_disable 2 7 set_1
        echo disabled > /sys/class/thermal/thermal_zone0/mode
    elif [ "${1}" == "G700" ]; then
        for i in 0 6
        do
            echo "performance" > /sys/devices/system/cpu/cpufreq/policy$i/scaling_governor
        done
        # disable cpuidle
        toggle_cpuidle_state_disable 2 7 set_1
        for i in {0..2}
        do
            echo "115000" > /sys/class/thermal/thermal_zone0/trip_point_"$i"_temp
        done
    elif [ "${1}" == "G350" ]; then
        echo "performance" > /sys/devices/system/cpu/cpufreq/policy0/scaling_governor
        echo disabled > /sys/class/thermal/thermal_zone0/mode
    fi
    echo "performance" > /sys/devices/platform/soc/"$MALI_SOC"/devfreq/"$MALI_SOC"/governor
    echo "Setting Done"
    echo
}

back_to_original_mode_from_performance() {
# $1 is the specific device platform. e.g. g1200-evk
    echo "===== Set back to original mode ====="
    if [ "${1}" == "G1200-evk" ]; then
        for i in 0 4
        do
            cat "$STORE_HOUSE"/p"$i"_sg > /sys/devices/system/cpu/cpufreq/policy$i/scaling_governor
        done
        # enable cpuidle
        toggle_cpuidle_state_disable 2 7 set_0
        echo enabled > /sys/class/thermal/thermal_zone0/mode
    elif [ "${1}" == "G700" ]; then
        for i in 0 6
        do
            cat "$STORE_HOUSE"/p"$i"_sg > /sys/devices/system/cpu/cpufreq/policy$i/scaling_governor
        done  
        # enable cpuidle
        toggle_cpuidle_state_disable 2 7 set_0
        for i in {0..2}
        do
            cat "$STORE_HOUSE"/"$i"_temp > /sys/class/thermal/thermal_zone0/trip_point_"$i"_temp
        done
    elif [ "${1}" == "G350" ]; then
        cat "$STORE_HOUSE"/p0_sg > /sys/devices/system/cpu/cpufreq/policy0/scaling_governor
        echo enabled > /sys/class/thermal/thermal_zone0/mode
    fi
    cat "$STORE_HOUSE"/mali_g > /sys/devices/platform/soc/"$MALI_SOC"/devfreq/"$MALI_SOC"/governor
    echo "Setting Done"
    echo
}

toggle_cpuidle_state_disable() {
# $1 is the count of /sys/devices/system/cpu/cpuX/cpuidle/state"$1"
# $2 is the count of /sys/devices/system/cpu/cpu"$2"
# $3 is the action to enable, diable the value of disable attribute for each cpu cpuidle state. {set_1 | set_0}, default: set_0
for (( j=0;j<=${1};j++ ))
do
    for (( i=0;i<=${2};i++ ))
    do
        value_to_be_set=0
        if [ "${3}" == "set_1" ]; then
            value_to_be_set=1
        fi
        echo $value_to_be_set > /sys/devices/system/cpu/cpu"$i"/cpuidle/state"$j"/disable
    done
done
}


main() {
# $1 is the specific device platform. e.g. G1200-evk
# $2 is the action.  {set-to-performance | reset}
    SUPPORTED_DEVICES=("G1200-evk" "G700" "G350")
    FIND_DEIVCE=0
    for device in "${SUPPORTED_DEVICES[@]}"; do
        if [ "${1}" == "$device" ]; then
            export FIND_DEIVCE=1
        fi
    done

    if [ $FIND_DEIVCE -eq 0 ]; then
        echo "Device: ${1} is not supported."
        exit 1
    fi

    if [ "${1}" == "G350" ]; then
        MALI_SOC="13040000.mali"
    fi

    case ${2} in
        set-to-performance)
            get_current_setting "${1}"
            store_setting "${1}"
            set_to_performance_mode "${1}"
            get_current_setting "${1}"
        ;;
        reset)
            get_current_setting "${1}"
            back_to_original_mode_from_performance "${1}"
            get_current_setting "${1}"
        ;;
        *) echo "Action is not supported. Available options: { set-to-performance | reset | show }"
    esac
}

main "$@"
