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

snap_check_delhi_svcs() 
{
    if [ "$1" = "--notfatal" ]; then
        FATAL=0
    else   
        FATAL=1
    fi
    # group services by status

    # enabled services
    # all the core-* services, security-services, consul, and all the mongo* services
    for svc in core-command core-data core-metadata security-services mongod mongo-worker core-config-seed consul; do 
        svcStatus="$(snap services edgexfoundry.$svc | grep $svc | awk '{print $2}')"
        if [ "enabled" != "$svcStatus" ]; then
            echo "service $svc has status \"$svcStatus\" but should be enabled"
            if [ "$FATAL" = "1" ]; then
                exit 1
            fi
        fi
    done

    # active services
    # same as enabled, but without core-config-seed and without mongo-worker as 
    # those are both oneshot daemons
    for svc in core-command core-data core-metadata security-services mongod consul ; do 
        svcStatus="$(snap services edgexfoundry.$svc | grep $svc | awk '{print $3}')"
        if [ "active" != "$svcStatus" ]; then
            echo "service $svc has status \"$svcStatus\" but should be active"
            if [ "$FATAL" = "1" ]; then
                exit 1
            fi
        fi
    done

    # disabled services
    for svc in export-distro export-client support-notifications support-scheduler support-rulesengine support-logging device-virtual device-mqtt device-modbus device-random; do 
        svcStatus="$(snap services edgexfoundry.$svc | grep $svc | awk '{print $2}')"
        if [ "disabled" != "$svcStatus" ]; then
            echo "service $svc has status \"$svcStatus\" but should be disabled"
            if [ "$FATAL" = "1" ]; then
                exit 1
            fi
        fi
    done

    # inactive services
    # all the disabled services + core-config-seed + mongo-worker
    for svc in export-distro export-client support-notifications support-scheduler support-rulesengine support-logging device-virtual device-modbus device-mqtt device-random core-config-seed; do 
        svcStatus="$(snap services edgexfoundry.$svc | grep $svc | awk '{print $3}')"
        if [ "inactive" != "$svcStatus" ]; then
            echo "service $svc has status \"$svcStatus\" but should be inactive"
            if [ "$FATAL" = "1" ]; then
                exit 1
            fi
        fi
    done
}

snap_check_edinburgh_svcs() 
{
    if [ "$1" = "--notfatal" ]; then
        FATAL=0
    else   
        FATAL=1
    fi
    # group services by status

    # enabled services
    # all the core-* services, security-services, consul, and all the mongo* services
    for svc in cassandra consul core-command core-config-seed core-data core-metadata edgexproxy kong-daemon mongo-worker mongod pkisetup sys-mgmt-agent vault vault-worker; do 
        svcStatus="$(snap services edgexfoundry.$svc | grep $svc | awk '{print $2}')"
        if [ "enabled" != "$svcStatus" ]; then
            echo "service $svc has status \"$svcStatus\" but should be enabled"
            if [ "$FATAL" = "1" ]; then
                exit 1
            fi
        fi
    done

    # active services
    # same as enabled, but without core-config-seed, mongo-worker, edgexproxy, pkisetup or vault-worker as 
    # those are all oneshot daemons
    for svc in cassandra consul core-command core-data core-metadata kong-daemon mongod sys-mgmt-agent vault; do 
        svcStatus="$(snap services edgexfoundry.$svc | grep $svc | awk '{print $3}')"
        if [ "active" != "$svcStatus" ]; then
            echo "service $svc has status \"$svcStatus\" but should be active"
            if [ "$FATAL" = "1" ]; then
                exit 1
            fi
        fi
    done

    # disabled services
    for svc in device-random export-client export-distro support-logging support-notifications support-rulesengine support-scheduler; do 
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
    for svc in core-config-seed device-random edgexproxy export-client export-distro mongo-worker pkisetup support-logging support-notifications support-rulesengine support-scheduler vault-worker; do 
        svcStatus="$(snap services edgexfoundry.$svc | grep $svc | awk '{print $3}')"
        if [ "inactive" != "$svcStatus" ]; then
            echo "service $svc has status \"$svcStatus\" but should be inactive"
            if [ "$FATAL" = "1" ]; then
                exit 1
            fi
        fi
    done
}

snap_check_fuji_svcs()
{
    if [ "$1" = "--notfatal" ]; then
        FATAL=0
    else   
        FATAL=1
    fi
    # group services by status

    # enabled services
    # all the core-* services, security-services, consul, and all the *mongo* services
    for svc in consul core-command core-config-seed core-data core-metadata edgex-mongo kong-daemon mongod postgres security-proxy-setup security-secrets-setup security-secretstore-setup sys-mgmt-agent vault; do
        svcStatus="$(snap services edgexfoundry.$svc | grep $svc | awk '{print $2}')"
        if [ "enabled" != "$svcStatus" ]; then
            echo "service $svc has status \"$svcStatus\" but should be enabled"
            if [ "$FATAL" = "1" ]; then
                exit 1
            fi
        fi
    done

    # active services
    # same as enabled, but without core-config-seed, edgex-mongo, security-*-setup as those are all oneshot daemons
    for svc in consul core-command core-data core-metadata kong-daemon mongod postgres sys-mgmt-agent vault; do
        svcStatus="$(snap services edgexfoundry.$svc | grep $svc | awk '{print $3}')"
        if [ "active" != "$svcStatus" ]; then
            echo "service $svc has status \"$svcStatus\" but should be active"
            if [ "$FATAL" = "1" ]; then
                exit 1
            fi
        fi
    done

    # disabled services
    for svc in app-service-configurable device-random device-virtual export-client export-distro support-logging redis support-notifications support-rulesengine support-scheduler; do
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
    for svc in app-service-configurable core-config-seed device-random device-virtual edgex-mongo export-client export-distro redis security-proxy-setup security-secrets-setup security-secretstore-setup support-logging support-notifications support-rulesengine support-scheduler; do
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
