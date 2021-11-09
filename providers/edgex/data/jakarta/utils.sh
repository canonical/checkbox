#!/bin/bash -e

if [ "$(id -u)" != "0" ]; then
    echo "script must be run as root"
    exit 1
fi

snap_install()
{
    local the_snap=$1
    local the_channel=$2
    local confinement=$3

    if [ "$the_snap" = "edgexfoundry" ]; then
        if [ -n "$confinement" ]; then
            snap install "$the_snap" --channel="$the_channel" "$confinement"
        else
            snap install "$the_snap" --channel="$the_channel"
        fi
    else
        if [ -n "$confinement" ]; then
            snap install "$the_snap" "$confinement"
        else
            snap install "$the_snap"
        fi
    fi
}

snap_refresh()
{
    local the_snap=$1
    local the_channel=$2
    local confinement=$3

    if [ "$the_snap" = "edgexfoundry" ]; then
        if [ -n "$confinement" ]; then
            snap refresh "$the_snap" --channel="$the_channel" "$confinement"
        else
            snap refresh "$the_snap" --channel="$the_channel"
        fi
    else
        # for refreshing a file snap we need to use install
        # but snapd still treats it like a refresh
        if [ -n "$confinement" ]; then
            snap install "$the_snap" "$confinement"
        else
            snap install "$the_snap"
        fi
    fi
}

snap_check_jakarta_svcs()
{
    if [ "$1" = "--notfatal" ]; then
        FATAL=0
    else
        FATAL=1
    fi
    # group services by status

    # enabled services
    # all the core-* services, security-services, consul, and redis
    for svc in consul core-command core-data core-metadata kong-daemon redis postgres security-proxy-setup \
	security-secretstore-setup security-bootstrapper-redis security-consul-bootstrapper vault; do
        svcStatus="$(snap services edgexfoundry.$svc | grep $svc | awk '{print $2}')"
        if [ "enabled" != "$svcStatus" ]; then
            echo "service $svc has status \"$svcStatus\" but should be enabled"
            if [ "$FATAL" = "1" ]; then
                exit 1
            fi
        fi
    done

    # active services
    # same as enabled, but without security-*-setup as those are all oneshot daemons
    for svc in consul core-command core-data core-metadata kong-daemon redis postgres vault; do
        svcStatus="$(snap services edgexfoundry.$svc | grep $svc | awk '{print $3}')"
        if [ "active" != "$svcStatus" ]; then
            echo "service $svc has status \"$svcStatus\" but should be active"
            if [ "$FATAL" = "1" ]; then
                exit 1
            fi
        fi
    done

    # disabled services
    for svc in app-service-configurable device-virtual kuiper support-notifications support-scheduler sys-mgmt-agent; do
        svcStatus="$(snap services edgexfoundry.$svc | grep $svc | awk '{print $2}')"
        if [ "disabled" != "$svcStatus" ]; then
            echo "service $svc has status \"$svcStatus\" but should be disabled"
            if [ "$FATAL" = "1" ]; then
                exit 1
            fi
        fi
    done

    # inactive services
    # all the disabled services + the oneshot daemons

    for svc in app-service-configurable device-virtual kuiper security-bootstrapper-redis \
	security-consul-bootstrapper security-proxy-setup security-secretstore-setup \
        support-notifications support-scheduler sys-mgmt-agent; do
        svcStatus="$(snap services edgexfoundry.$svc | grep $svc | awk '{print $3}')"
        if [ "inactive" != "$svcStatus" ]; then
            echo "service $svc has status \"$svcStatus\" but should be inactive"
            if [ "$FATAL" = "1" ]; then
                exit 1
            fi
        fi
    done
}

get_snap_svc_status()
{
    case "$1" in 
        "status")
            svcStatus="$(snap services edgexfoundry.$1 | grep $1 | awk '{print $3}')"
            ;;
        "")
            ;;
    esac
}

snap_remove()
{
    snap remove edgexfoundry || true
}

