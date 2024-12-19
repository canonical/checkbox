#!/bin/bash
# shellcheck disable=SC2317
set -e

oem=""
platform=""
build_no=""
usage() {
cat << EOF
usage: $0 options

    -h|--help print this message
    --oem-codename
    --platform-codename
    --get-platform-id
    --get-build-no
EOF
exit 1
}

prepare() {
    local dcd

    dcd=$(ubuntu-report show | jq -r '.OEM.DCD')
    for project in sutton stella somerville; do
        if [[ "$dcd" == *"$project"* ]]; then
            oem="$project"
            break
        fi
    done

    if [ -z "${oem}" ]; then
        >&2 echo "[ERROR][CODE]got an empty OEM codename in ${FUNCNAME[0]}";
        return 1
    fi

    # Since Ubuntu 22.04, there is no group layer anymore
    # Use 20.04 & 22.04 instead of focal & jammy since we may need to support N+1 in the future.
    release=$(lsb_release -a 2>/dev/null| grep ^Release| awk '{print $2}')
    if [[ "$release" == "20.04" ]]; then
        meta_pattern="oem-$oem.*-meta"
    else # elif [[ "$release" == "22.04" ]]; then
        meta_pattern="oem-$oem*-meta"
    fi

    # Remove the group name
    case "${oem%%.*}" in
        "somerville")
            for pkg in $(dpkg-query -W -f='${Package}\n'  "oem-$oem*-meta"); do
                _code_name=$(echo "${pkg}" | awk -F"-" '{print $3}')
                if [ "$_code_name" == "factory" ] ||
                    [ "$_code_name" == "meta" ]; then
                    continue
                fi
                tmp=${pkg/oem-$oem-/}
                platform=${tmp/-meta/}
            done
            ;;
        "stella")
            for pkg in $(dpkg-query -W -f='${Package}\n' "$meta_pattern"); do
                _code_name=$(echo "${pkg}" | awk -F"-" '{print $3}')
                if [ "$_code_name" == "factory" ] ||
                    [ "$_code_name" == "meta" ]; then
                    continue
                fi
                oem="$(echo "$pkg" | cut -d'-' -f2 )"
                tmp=${pkg/oem-$oem-/}
                platform=${tmp/-meta/}
            done
            ;;
        "sutton")
            for pkg in $(dpkg-query -W -f='${Package}\n' "$meta_pattern"); do
                _code_name=$(echo "${pkg}" | awk -F"-" '{print $3}')
                if [ "$_code_name" == "factory" ] ||
                    [ "$_code_name" == "meta" ]; then
                    continue
                fi
                oem="$(echo "$pkg" | cut -d'-' -f2 )"
                tmp=${pkg/oem-$oem-/}
                platform=${tmp/-meta/}
            done
            ;;
        *)
            >&2 echo "[ERROR][CODE]we should not be here in ${FUNCNAME[0]} : ${LINENO}"
            ;;
    esac
}

get_platform_id() {
    vendor="$(cat < /sys/class/dmi/id/sys_vendor)"

    case "${vendor}" in
        'Dell Inc.'|'HP')
            platform_id="$(lspci -nnv -d ::0x0c05 | grep "Subsystem" | awk -F"[][]" '{print $2}' | cut -d ':' -f2)"
            ;;
       'LENOVO')
            platform_id="$(cat < /sys/class/dmi/id/bios_version | cut -c 1-3)"
            ;;
        *)
            platform_id="Unknown vendor"
            ;;
    esac

    echo "${platform_id}"
}

get_build_no() {
    udc=$(tail -n1 /var/lib/ubuntu_dist_channel)
    if [[ $udc =~ canonical-oem-somerville.* ]]; then
        build_no=${udc#*X}
    elif [ -f /etc/buildstamp ]; then
        image_build=$(tail -n1 /etc/buildstamp)
        build_no=${image_build##*-}
    fi
}

main() {
    while [ $# -gt 0 ]
    do
        case "$1" in
            -h | --help)
                usage 0
                exit 0
                ;;
            --oem-codename)
                [ -n "$oem" ] || prepare
                echo "$oem"
                ;;
            --platform-codename)
                [ -n "$platform" ] || prepare
                echo "$platform"
                ;;
            --get-platform-id)
                get_platform_id
                ;;
            --get-build-no)
                [ -n "$build_no" ] || get_build_no
                echo "$build_no"
                ;;
            *)
            usage
           esac
           shift
    done
}

if [ "${BASH_SOURCE[0]}" = "$0" ]; then
    main "$@"
fi
