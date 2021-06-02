#!/bin/bash

usage() {
    cat <<EOU

${0} - check short idle residency

 Usage: ${0} [ -s <interval> ]

    -s <interval> -- specify a idle time interval in seconds

EOU
}

re='^[0-9]+$'
sleep_time=20

while [ $# -gt 0 ]
do
    case "$1" in
        -s)
            if ! [[ $2 =~ $re ]]; then
                usage
                exit 1
            fi
            sleep_time=${2}
            break
            ;;
        --help)
            usage
            exit 1
            ;;
        *)
            usage
            exit 1
            ;;
    esac
    shift
done

msr_support=$(find /dev/cpu -name msr)
if [ -z "$msr_support" ]; then
    echo "Attempting to load Intel MSR kernel module..."
    modprobe msr
fi

cstate_pkg_list=$(ls /sys/bus/event_source/devices/cstate_pkg/events/)
msr_pc2=0
msr_pc3=0
msr_pc6=0
msr_pc7=0
msr_pc8=0
msr_pc9=0
msr_pc10=0

for event in $cstate_pkg_list;
do
    case "$event" in
    "c2-residency")
                    msr_pc2=1
                    ;;
    "c3-residency")
                    msr_pc3=1
                    ;;
    "c6-residency")
                    msr_pc6=1
                    ;;
    "c7-residency")
                    msr_pc7=1
                    ;;
    "c8-residency")
                    msr_pc8=1
                    ;;
    "c9-residency")
                    msr_pc9=1
                    ;;
    "c10-residency")
                    msr_pc10=1
                    ;;
    esac
done

# Find the platform's cstate accroding to
# registered event node
# https://elixir.bootlin.com/linux/latest/source/arch/x86/events/intel/cstate.c#L504
#
# Find the MSR register in
# https://elixir.bootlin.com/linux/latest/source/arch/x86/include/asm/msr-index.h#L285
# NHM support
if [ $((msr_pc2+msr_pc8+msr_pc9+msr_pc10)) -eq 0 ] && [ $msr_pc3 -eq 1 ] && [ $msr_pc6 -eq 1 ] && [ $msr_pc7 -eq 1 ]; then
    echo "Identified device as supporting Intel Nehalem C-states"
    counter_pc7=$(rdmsr -p 0 -o 0x3fa)
    sleep "$sleep_time"
    new_counter_pc7=$(rdmsr -p 0 -o 0x3fa)
    delt_pc7=$((new_counter_pc7-counter_pc7))
    echo "Target MSR PC7 residency delta before/after idle is $delt_pc7"
    if [ $delt_pc7 -gt 0 ]; then
        echo "PASS: Time spent in PC7 state"
        exit 0
    else
        exit 1
    fi
fi

# SNB support
if [ $((msr_pc8+msr_pc9+msr_pc10)) -eq 0 ] && [ $msr_pc2 -eq 1 ] && [ $msr_pc3 -eq 1 ] && [ $msr_pc6 -eq 1 ] && [ $msr_pc7 -eq 1 ]; then
    echo "Identified device as supporting Intel Sandybridge C-states"
    counter_pc7=$(rdmsr -p 0 -o 0x3fa)
    sleep "$sleep_time"
    new_counter_pc7=$(rdmsr -p 0 -o 0x3fa)
    delt_pc7=$((new_counter_pc7-counter_pc7))
    echo "Target MSR PC7 residency delta before/after idle is $delt_pc7"
    if [ $delt_pc7 -gt 0 ]; then
        echo "PASS: Time spent in PC7 state"
        exit 0
    else
        exit 1
    fi
fi

# SLM support with SLM_PKG_C6_USE_C7_MSR
if [ $((msr_pc2+msr_pc3+msr_pc7+msr_pc8+msr_pc9+msr_pc10)) -eq 0 ] && [ $msr_pc6 -eq 1 ]; then
    echo "Identified device as supporting Intel Silvermont C-states"
    counter_pc6=$(rdmsr -p 0 -o 0x3fa)
    sleep "$sleep_time"
    new_counter_pc6=$(rdmsr -p 0 -o 0x3fa)
    delt_pc6=$((new_counter_pc6-counter_pc6))
    echo "Target MSR PC6 residency delta before/after idle is $delt_pc6"
    if [ $delt_pc6 -gt 0 ]; then
        echo "PASS: Time spent in PC6 state"
        exit 0
    else
        exit 1
    fi
fi

# KNL support
if [ $((msr_pc7+msr_pc8+msr_pc9+msr_pc10)) -eq 0 ] && [ $msr_pc2 -eq 1 ] && [ $msr_pc3 -eq 1 ] && [ $msr_pc6 -eq 1 ]; then
    echo "Identified device as supporting Intel Knights Landing C-states"
    counter_pc6=$(rdmsr -p 0 -o 0x3f9)
    sleep "$sleep_time"
    new_counter_pc6=$(rdmsr -p 0 -o 0x3f9)
    delt_pc6=$((new_counter_pc6-counter_pc6))
    echo "Target MSR PC6 residency delta before/after idle is $delt_pc6"
    if [ $delt_pc6 -gt 0 ]; then
        echo "PASS: Time spent in PC6 state"
        exit 0
    else
        exit 1
    fi
fi

# GLM support
if [ $((msr_pc7+msr_pc8+msr_pc9)) -eq 0 ] && [ $msr_pc2 -eq 1 ] && [ $msr_pc3 -eq 1 ] && [ $msr_pc6 -eq 1 ] && [ $msr_pc10 -eq 1 ]; then
    echo "Identified device as supporting Intel Goldmont C-states"
    counter_pc6=$(rdmsr -p 0 -o 0x3f9)
    counter_pc10=$(rdmsr -p 0 -o 0x632)
    sleep "$sleep_time"
    new_counter_pc6=$(rdmsr -p 0 -o 0x3f9)
    new_counter_pc10=$(rdmsr -p 0 -o 0x632)
    delt_pc6=$((new_counter_pc6-counter_pc6))
    delt_pc10=$((new_counter_pc10-counter_pc10))
    echo "Target MSR PC6 residency delta before/after idle is $delt_pc6"
    if [ $((delt_pc6+delt_pc10)) -gt 0 ]; then
        echo "PASS: Time spent in at least one of PC6 or PC10 state"
        exit 0
    else
        exit 1
    fi
fi

# ADL/ICL/CNL/HSWULT
echo "Assuming device supports one of Alderlake/Icelake/Cannonlake/Haswell C-states"
counter_pc8=$(rdmsr -p 0 -o 0x630)
counter_pc9=$(rdmsr -p 0 -o 0x631)
counter_pc10=$(rdmsr -p 0 -o 0x632)
sleep "$sleep_time"
new_counter_pc8=$(rdmsr -p 0 -o 0x630)
new_counter_pc9=$(rdmsr -p 0 -o 0x631)
new_counter_pc10=$(rdmsr -p 0 -o 0x632)
delt_pc8=$((new_counter_pc8-counter_pc8))
delt_pc9=$((new_counter_pc9-counter_pc9))
delt_pc10=$((new_counter_pc10-counter_pc10))
echo "PC8 MSR residency delta before/after idle is $delt_pc8"
echo "PC9 MSR residency delta before/after idle is $delt_pc9"
echo "PC10 MSR residency delta before/after idle is $delt_pc10"

if [ $((delt_pc8+delt_pc9+delt_pc10)) -gt 0 ]; then
    echo "PASS: Time spent in at least one of PC8, PC9 or PC10 states"
    exit 0
fi

exit 1
