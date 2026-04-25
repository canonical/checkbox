#!/bin/bash
#set -x
OUTPUT_FOLDER=/tmp
test_result="PASS"
#readonly function_pass=0
readonly function_failed=1

usage() {
cat << EOF
usage: $(basename "$0") options

A script to check if nvidia driver behave as expected.
Nvidia introduce runtime pm (RTD3) from version 450,
this script is target to check the expected behavior of nviia driver, and gpu manager.

This script will need some environment precondition that DISPLAY environment is assigned,
nvidia-prime and ubuntu-drivers-common are installed. Nvidia drvier newer than version 450.

    -h|--help print this message
    --dry-run dryrun
    --out     The output folder for generated logs. The default one is /tmp/

EOF
}

show_error() {
    >&2 echo "[ERROR] ""$1"
    test_result="FAILED"
    if [ -n "$2" ]; then
        case "$2" in
            exit1 )
                exit 1
                ;;
            exit0 )
                exit 0
                ;;
            usage-exit1 )
                usage
                exit 1
                ;;
            * )
                ;;
        esac
    fi
}

collect_nvidia_debug_info() {
    local logs_folder="$OUTPUT_FOLDER/nvidia-debug-logs"
    mkdir -p "$logs_folder"
    echo "/proc/driver/nvidia/params:" >> "$OUTPUT_FOLDER"/nvidia-debug-log
    if [ -f /proc/driver/nvidia/params ]; then
        cat /proc/driver/nvidia/params >> "$OUTPUT_FOLDER"/nvidia-debug-log
    else
        echo "file is not there" >> "$OUTPUT_FOLDER"/nvidia-debug-log
    fi

    echo "/var/log/gpu-manager.log:" >> "$OUTPUT_FOLDER"/nvidia-debug-log
    if [ -f /var/log/gpu-manager.log ]; then
        cp /var/log/gpu-manager.log "$logs_folder"
        echo "Copied file to $logs_folder" >> "$OUTPUT_FOLDER"/nvidia-debug-log
    else
        echo "file is not there" >> "$OUTPUT_FOLDER"/nvidia-debug-log
    fi

    echo "nvidia-smi:" >> "$OUTPUT_FOLDER"/nvidia-debug-log
    nvidia-smi >> "$OUTPUT_FOLDER"/nvidia-debug-log
}

is_nv_bootvga() {
    local _nv_bootvga=0
    # head -n 1 because of nv-link or any multiple nvidia cards case
    while IFS= read -r line; do
        if [ "$line" == "1" ]; then
            _nv_bootvga=1
            break
        fi
    done < <(cat /sys/module/nvidia/drivers/pci:nvidia/*/boot_vga)
    echo "$_nv_bootvga"
}
get_nvidia_runtime_status() {
    local status
    status=$(cat /sys/module/nvidia/drivers/pci:nvidia/*/power/runtime_status)
    echo "$status"
}
check_nvidia_sleep() {
    local status
    # 60 seconds was test on G9~G10 HP mobile workstations.
    # Some nvidia gpu needs 30+ seconds to determine goes sleep or not.
    echo "[INFO] Wait 60 seconds for nvidia gpu goes to sleep."
    sleep 60
    status=$(get_nvidia_runtime_status)
    if [ "$status" != "suspended" ]; then
       show_error "nvidia graphic is still active but expects to suspended."
       if uname -r | grep -q "5.10"; then
        echo "[INFO] There's a know issue LP: #1904762 that Nvidia driver not sleep with kernel 5.10"
       fi
       return $function_failed
    fi
}
check_environment() {
    [ -n "$DISPLAY" ] || show_error "Please assign DISPLAY enviornment." usage-exit1
    glxinfo > /dev/null || show_error "Failed to execute glxinfo" usage-exit1
    dpkg --compare-versions "$(modinfo nvidia -F version)" "gt" "450" || show_error "[ERROR] $(basename "$0") only support nvidia driver >= 450." usage-exit1
    command -v prime-select || show_error "nvidia-prime is not installed."  usage-exit1
    command -v gpu-manager || show_error "ubuntu-drivers-common is not installed." usage-exit1
}
check_renderer() {
    local renderer
    local _nv_bootvga
    # head -n 1 because of nv-link or any multiple nvidia cards case
    _nv_bootvga="$(is_nv_bootvga)"
    case $1 in
        on-demand-default )
            renderer="$(__NV_PRIME_RENDER_OFFLOAD=0 __GLX_VENDOR_LIBRARY_NAME="" glxinfo | grep "OpenGL vendor string")"
            # if nvidia is not bootvga, then the render should not be nvidia but
            # i915, amdgpu, radeon
            if [ "$_nv_bootvga" == 0 ]; then
                echo "$renderer"| grep -iq 'nvidia' && show_error "The default renderer should NOT be NVIDIA in on-demand." exit1
            else
                echo "$renderer"| grep -iq 'nvidia' || show_error "The default renderer should be NVIDIA in on-demand." exit1
            fi
            ;;
        on-demand-nvidia )
            renderer="$(__NV_PRIME_RENDER_OFFLOAD=1 __GLX_VENDOR_LIBRARY_NAME=nvidia glxinfo | grep "OpenGL renderer string")"
            [ -n "${renderer##*Intel*}" ] || show_error "renderer is Intel in on-demand with Nvidia runtime parameters." exit1
            [ -n "${renderer##*LLVM*}" ] || show_error "renderer is  LLVM in nvidia mode (performance)." exit1
            ;;
        nvidia )
            local renderer
            renderer="$(glxinfo | grep "OpenGL renderer string")"
            [ -n "${renderer##*Intel*}" ] || show_error "renderer is Intel in nvidia mode (performance)." exit1
            [ -n "${renderer##*LLVM*}" ] || show_error "renderer is  LLVM in nvidia mode (performance)." exit1
            ;;
        intel )
            renderer="$(glxinfo | grep "OpenGL renderer string")"
            [ -z "${renderer##*Intel*}" ] || show_error "renderer is NOT Intel in intel mode(powersaving)." exit1
            ;;
        * )
            show_error "[ERROR][CODE] Not assigned which mode to check." usage-exit1
            ;;
    esac
    return 0
}
check_ondemand_mode() {
    local _gpu_mgr_nv_rtd3_sprt
    local _nv_bootvga
    # head -n 1 because of nv-link or any multiple nvidia cards case
    _nv_bootvga="$(is_nv_bootvga)"
    # will empty if bootvga is nvidia
    _gpu_mgr_nv_rtd3_sprt="$(grep 'Is nvidia runtime pm supported for' /var/log/gpu-manager.log| awk -F '?' '{print $2}'| sed 's/ //g')"
    # The test case should test what ubuntu offers which relys on gpu-manager.
    # Although after Ampere, the rtd3 will auto enable but which is depending on
    # GPU. It's a black-box and we don't need to care.
    if [ "$_nv_bootvga" == 0 ] &&
       [ "$_gpu_mgr_nv_rtd3_sprt" == "yes" ]; then
        check_nvidia_sleep ondemand_
    fi
    check_renderer on-demand-default
    check_renderer on-demand-nvidia
}
check_nvidia_mode() {
    check_renderer nvidia
}
check_intel_mode() {
    check_renderer intel
    check_nvidia_sleep intel_
}
check_behavior_of_current_mode() {
    local NV_MODE
    NV_MODE="$(prime-select query)"
    case "$NV_MODE" in
        on-demand)
            echo "[INFO] current mode is on-demand mode."
            check_ondemand_mode
            ;;
        nvidia)
            echo "[INFO] current mode is nvidia mode."
            check_nvidia_mode
            ;;
        intel)
            echo "[INFO] current mode is intel mode."
            check_intel_mode
            ;;
        *)
            show_error "Unsupported mode: $NV_MODE" usage-exit1
            ;;
    esac
}

main() {
    while [ $# -gt 0 ]
    do
        case "$1" in
            -h | --help)
                usage 0
                exit 0
                ;;
            --out)
                shift;
                OUTPUT_FOLDER=$1;
                ;;
            *)
            show_error "[ERROR] not support parameger $1" usage-exit1
            usage
           esac
           shift
    done

    check_environment
    check_behavior_of_current_mode
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
    main "$@"
    if [ "$test_result" = "PASS" ]; then
        echo "[INFO] passed"
    else
        collect_nvidia_debug_info
        echo "[ERROR] $(basename "$0") testing failed."
        exit "$function_failed"
    fi
fi

