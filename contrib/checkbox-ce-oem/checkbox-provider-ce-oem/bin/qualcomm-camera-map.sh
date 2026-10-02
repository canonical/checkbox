#!/usr/bin/env bash
#
# Map qtiqmmfsrc camera IDs to Qualcomm CamX sensors and CSI PHY indices.
# Discovery is read-only. Runtime capture tests are only run with --test.

set -u

CAM_SERVICE="cam-server.service"
CAM_SERVER_LOG_LINES=20000
TEST_IDS=""
TEST_WIDTH=640
TEST_HEIGHT=480
TEST_FPS=30
TEST_SECONDS=5
RESTART_BETWEEN_TESTS=0

usage() {
    cat <<'EOF'
Usage:
  qualcomm-camera-map.sh
  qualcomm-camera-map.sh --test [CAMERA_IDS] [options]

By default, the script only reads CamX, kernel, sysfs, and Device Tree data.

Options:
  --test [IDS]          Test comma-separated QMMF IDs (default: all discovered)
  --width N             Test width (default: 640)
  --height N            Test height (default: 480)
  --fps N               Test frame rate (default: 30)
  --seconds N           Test duration per camera (default: 5)
  --restart-between     Restart cam-server before each test
  --service NAME        Camera service (default: cam-server.service)
  -h, --help            Show this help

Examples:
  ./qualcomm-camera-map.sh
  ./qualcomm-camera-map.sh --test
  ./qualcomm-camera-map.sh --test 0,1,2 --width 640 --height 480
  ./qualcomm-camera-map.sh --test 0,2 --width 1280 --height 720 \
      --restart-between

The runtime test uses:
  qtiqmmfsrc camera=ID ! video/x-raw,format=NV12,... ! fakesink

It does not write video files. A failed resolution does not prove that the
sensor is broken; retry with a mode supported by that sensor.
EOF
}

die() {
    printf 'error: %s\n' "$*" >&2
    exit 1
}

is_uint() {
    case "${1:-}" in
        ''|*[!0-9]*) return 1 ;;
        *) return 0 ;;
    esac
}

run_privileged() {
    if [ "$(id -u)" -eq 0 ]; then
        "$@"
    elif sudo -n true 2>/dev/null; then
        sudo -n "$@"
    else
        "$@"
    fi
}

read_be32() {
    local path=$1
    [ -r "$path" ] || return 1
    od -An -tu4 --endian=big -N4 "$path" 2>/dev/null |
        tr -d '[:space:]'
}

read_dt_string() {
    local path=$1
    [ -r "$path" ] || return 1
    tr -d '\000' < "$path" 2>/dev/null
}

while [ "$#" -gt 0 ]; do
    case "$1" in
        --test)
            TEST_IDS="__ALL__"
            if [ "$#" -gt 1 ] && [[ $2 != -* ]]; then
                TEST_IDS=$2
                shift
            fi
            ;;
        --width|--height|--fps|--seconds|--service)
            [ "$#" -ge 2 ] || die "$1 requires a value"
            case "$1" in
                --width) TEST_WIDTH=$2 ;;
                --height) TEST_HEIGHT=$2 ;;
                --fps) TEST_FPS=$2 ;;
                --seconds) TEST_SECONDS=$2 ;;
                --service) CAM_SERVICE=$2 ;;
            esac
            shift
            ;;
        --restart-between)
            RESTART_BETWEEN_TESTS=1
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            die "unknown argument: $1"
            ;;
    esac
    shift
done

for value in "$TEST_WIDTH" "$TEST_HEIGHT" "$TEST_FPS" "$TEST_SECONDS"; do
    is_uint "$value" || die "test dimensions, fps, and duration must be integers"
done

TMP_DIR=$(mktemp -d "${TMPDIR:-/tmp}/qualcomm-camera-map.XXXXXX") ||
    die "cannot create temporary directory"
trap 'rm -rf "$TMP_DIR"' EXIT

CAMX_LOG="$TMP_DIR/camx.log"
DMESG_LOG="$TMP_DIR/dmesg.log"
ENUM_FILE="$TMP_DIR/enumeration.tsv"
PROBE_FILE="$TMP_DIR/probes.tsv"
DT_FILE="$TMP_DIR/device-tree.tsv"

if command -v journalctl >/dev/null 2>&1; then
    run_privileged journalctl -u "$CAM_SERVICE" --no-pager \
        -n "$CAM_SERVER_LOG_LINES" > "$CAMX_LOG" 2>/dev/null || :
else
    : > "$CAMX_LOG"
fi

run_privileged dmesg > "$DMESG_LOG" 2>/dev/null || : > "$DMESG_LOG"

# CamX enumeration lines normally contain all fields on one line:
# frameworkId, cameraId, sensorId, sensorName, and logicalCamId.
awk '
    /frameworkId/ && /cameraId/ && /sensorName/ {
        line=$0
        framework=""; camera=""; sensor_id=""; sensor=""; logical=""
        if (match(line, /frameworkId[ =:]+[0-9]+/))
            framework=substr(line, RSTART, RLENGTH)
        if (match(line, /cameraId[ =:]+[0-9]+/))
            camera=substr(line, RSTART, RLENGTH)
        if (match(line, /sensorId[ =:]+[0-9]+/))
            sensor_id=substr(line, RSTART, RLENGTH)
        if (match(line, /sensorName[ =:]+[^, )]+/))
            sensor=substr(line, RSTART, RLENGTH)
        if (match(line, /logicalCamId[ =:]+[0-9]+/))
            logical=substr(line, RSTART, RLENGTH)
        gsub(/[^0-9]/, "", framework)
        gsub(/[^0-9]/, "", camera)
        gsub(/[^0-9]/, "", sensor_id)
        sub(/^sensorName[ =:]+/, "", sensor)
        gsub(/[^0-9]/, "", logical)
        if (camera != "" && sensor != "")
            print camera "\t" framework "\t" logical "\t" sensor_id "\t" sensor
    }
' "$CAMX_LOG" | sort -t $'\t' -k1,1n -u > "$ENUM_FILE"

# Kernel probe lines tie a sensor name and chip ID to its static slot.
awk '
    /Probe success for/ {
        line=$0
        sensor=""; slot=""; chip=""
        if (match(line, /Probe success for [^ ,]+/))
            sensor=substr(line, RSTART+18, RLENGTH-18)
        if (match(line, /slot:[0-9]+/))
            slot=substr(line, RSTART+5, RLENGTH-5)
        if (match(line, /sensor_id:0x[0-9A-Fa-f]+/))
            chip=substr(line, RSTART+10, RLENGTH-10)
        if (sensor != "")
            print sensor "\t" slot "\t" chip
    }
' "$DMESG_LOG" | sort -u > "$PROBE_FILE"

# Device Tree supplies the static sensor slot, CSI PHY index, and CCI master.
DT_ROOT=/sys/firmware/devicetree/base
if [ -d "$DT_ROOT" ]; then
    while IFS= read -r -d '' node; do
        slot=$(read_be32 "$node/cell-index" 2>/dev/null || :)
        phy=$(read_be32 "$node/csiphy-sd-index" 2>/dev/null || :)
        [ -n "$phy" ] ||
            phy=$(read_be32 "$node/qcom,csiphy-sd-index" 2>/dev/null || :)
        cci=$(read_be32 "$node/cci-master" 2>/dev/null || :)
        [ -n "$cci" ] ||
            cci=$(read_be32 "$node/qcom,cci-master" 2>/dev/null || :)
        name=$(read_dt_string "$node/sensor-name" 2>/dev/null || :)
        [ -n "$name" ] ||
            name=$(read_dt_string "$node/qcom,sensor-name" 2>/dev/null || :)
        if [ -n "$slot" ] || [ -n "$phy" ]; then
            printf '%s\t%s\t%s\t%s\t%s\n' \
                "${slot:--}" "${phy:--}" "${cci:--}" "${name:--}" "$node"
        fi
    done < <(
        find "$DT_ROOT" -type d \
            \( -name 'qcom,cam-sensor*' -o -name 'cam-sensor*' \) \
            -print0 2>/dev/null
    ) | sort -t $'\t' -k1,1n -u > "$DT_FILE"
else
    : > "$DT_FILE"
fi

printf 'Qualcomm camera mapping\n'
printf '=======================\n'
printf 'Camera service: %s\n\n' "$CAM_SERVICE"

if [ ! -s "$ENUM_FILE" ]; then
    printf 'No CamX camera enumeration was found in %s logs.\n' "$CAM_SERVICE"
    printf 'Try restarting the service, then rerun this script:\n'
    printf '  sudo systemctl restart %s\n\n' "$CAM_SERVICE"
else
    printf '%-8s %-12s %-10s %-20s %-8s %-9s %-8s\n' \
        'QMMF ID' 'CamX sensor' 'slot' 'sensor chip ID' 'CSI PHY' 'CCI' 'source'
    printf '%-8s %-12s %-10s %-20s %-8s %-9s %-8s\n' \
        '-------' '-----------' '----' '--------------' '-------' '---' '------'

    while IFS=$'\t' read -r camera framework logical sensor_id sensor; do
        slot=""
        chip=""
        phy=""
        cci=""
        source="CamX"

        probe=$(awk -F '\t' -v sensor="$sensor" '$1 == sensor {print; exit}' \
            "$PROBE_FILE")
        if [ -n "$probe" ]; then
            IFS=$'\t' read -r _ slot chip <<< "$probe"
            source="CamX+klog"
        elif [ -n "$sensor_id" ]; then
            slot=$sensor_id
        fi

        if [ -n "$slot" ]; then
            dt=$(awk -F '\t' -v slot="$slot" '$1 == slot {print; exit}' \
                "$DT_FILE")
            if [ -n "$dt" ]; then
                IFS=$'\t' read -r _ phy cci _ _ <<< "$dt"
                source="${source}+DT"
            fi
        fi

        printf '%-8s %-12s %-10s %-20s %-8s %-9s %-8s\n' \
            "$camera" "$sensor" "${slot:--}" "${chip:--}" \
            "${phy:--}" "${cci:--}" "$source"
    done < "$ENUM_FILE"
fi

printf '\nKernel sensor probes\n'
printf '%s\n' '--------------------'
if [ -s "$PROBE_FILE" ]; then
    while IFS=$'\t' read -r sensor slot chip; do
        printf 'sensor=%-12s slot=%-3s sensor_id=%s\n' \
            "$sensor" "${slot:--}" "${chip:--}"
    done < "$PROBE_FILE"
else
    printf 'No "Probe success for ..." records found in dmesg.\n'
fi

printf '\nDevice Tree camera wiring\n'
printf '%s\n' '-------------------------'
if [ -s "$DT_FILE" ]; then
    while IFS=$'\t' read -r slot phy cci name node; do
        printf 'slot=%-3s csiphy=%-3s cci-master=%-3s sensor=%-12s node=%s\n' \
            "${slot:--}" "${phy:--}" "${cci:--}" "${name:--}" "$node"
    done < "$DT_FILE"
else
    printf 'No camera sensor nodes with CSI PHY metadata found.\n'
fi

if [ -z "$TEST_IDS" ]; then
    exit 0
fi

command -v gst-launch-1.0 >/dev/null 2>&1 ||
    die "gst-launch-1.0 is required for --test"
gst-inspect-1.0 qtiqmmfsrc >/dev/null 2>&1 ||
    die "qtiqmmfsrc is not available"

if [ "$TEST_IDS" = "__ALL__" ]; then
    TEST_IDS=$(cut -f1 "$ENUM_FILE" | paste -sd, -)
fi
[ -n "$TEST_IDS" ] || die "no camera IDs were discovered; pass IDs explicitly"

printf '\nRuntime tests (%sx%s@%s, %ss each)\n' \
    "$TEST_WIDTH" "$TEST_HEIGHT" "$TEST_FPS" "$TEST_SECONDS"
printf '%s\n' '----------------------------------------'

IFS=',' read -r -a camera_ids <<< "$TEST_IDS"
for camera in "${camera_ids[@]}"; do
    is_uint "$camera" || die "invalid camera ID: $camera"

    if [ "$RESTART_BETWEEN_TESTS" -eq 1 ]; then
        printf 'camera=%s: restarting %s ... ' "$camera" "$CAM_SERVICE"
        if run_privileged systemctl restart "$CAM_SERVICE" >/dev/null 2>&1; then
            sleep 3
            printf 'done\n'
        else
            printf 'failed\n'
        fi
    fi

    start_marker=$(date '+%Y-%m-%d %H:%M:%S')
    output="$TMP_DIR/camera-${camera}.log"
    printf 'camera=%s: ' "$camera"

    timeout --signal=INT --kill-after=5 "$TEST_SECONDS" \
        gst-launch-1.0 -e \
        qtiqmmfsrc camera="$camera" \
        \! "video/x-raw,format=NV12,width=$TEST_WIDTH,height=$TEST_HEIGHT,framerate=$TEST_FPS/1" \
        \! fakesink sync=false > "$output" 2>&1
    rc=$?

    if grep -q 'Got EOS\|EOS received' "$output"; then
        result=PASS
    elif grep -q 'StartVideoTracks Failed\|Failed to start stream' "$output"; then
        result=FAIL-STREAM-CONFIG
    elif grep -q 'Failed to Open Camera\|Recorder Connect failed' "$output"; then
        result=FAIL-CAMERA-SERVICE
    elif [ "$rc" -eq 124 ] || [ "$rc" -eq 130 ]; then
        result=TIMEOUT
    elif [ "$rc" -eq 0 ]; then
        result=PASS
    else
        result=FAIL
    fi

    sensor=$(run_privileged journalctl -u "$CAM_SERVICE" --since "$start_marker" \
        --no-pager 2>/dev/null |
        sed -n 's/.*SensorName:\([^ ]*\).*/\1/p' | tail -1)
    [ -n "$sensor" ] ||
        sensor=$(run_privileged dmesg 2>/dev/null |
            sed -n 's/.*CAM_START_DEV Success for \([^ ]*\).*/\1/p' | tail -1)
    phy=$(run_privileged dmesg 2>/dev/null |
        sed -n 's/.*CAM_START_PHYDEV: \([0-9][0-9]*\).*/\1/p' | tail -1)

    printf '%s (rc=%s, sensor=%s, csiphy=%s)\n' \
        "$result" "$rc" "${sensor:--}" "${phy:--}"

    if [ "$result" != PASS ]; then
        grep -E 'ERROR:|Failed|Invalid stream|maximum|max Res|requested Res' \
            "$output" | tail -8 | sed 's/^/  /' || :
    fi
done

printf '\nNotes\n'
printf '%s\n' '-----'
printf '%s\n' \
    '* QMMF camera ID comes from CamX frameworkId/cameraId enumeration.' \
    '* Sensor slot comes from the kernel probe and Device Tree cell-index.' \
    '* CSI PHY comes from Device Tree csiphy-sd-index and CAM_START_PHYDEV.' \
    '* Do not use runtime CSID as physical wiring; it may be dynamically allocated.'
