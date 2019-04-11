#!/bin/bash -e

snap_install()
{
    local the_snap=$1
    local the_channel=$2
    local confinement=$3

    if [ "$the_snap" = "edgexfoundry" ]; then
        snap install "$the_snap" --channel="$the_channel" "$confinement"
    else
        snap install "$the_snap" "$confinement"
    fi
}

snap_refresh()
{
    local the_snap=$1
    local the_channel=$2
    local confinement=$3

    if [ "$the_snap" = "edgexfoundry" ]; then
        snap refresh "$the_snap" --channel="$the_channel" "$confinement"
    else
        # for refreshing a file snap we need to use install
        # but snapd still treats it like a refresh
        snap install "$the_snap" "$confinement"
    fi
}

snap_check_svcs() 
{
    # group services by status

    # enabled services
    # all the core-* services, security-services, consul, and all the mongo* services
    for svc in core-command core-data core-metadata security-services mongod mongo-worker core-config-seed consul; do 
        svcStatus="$(snap services edgexfoundry.$svc | grep $svc | awk '{print $2}')"
        if [ "enabled" != "$svcStatus" ]; then
            echo "service $svc has status \"$svcStatus\" but should be enabled"
            exit 1
        fi
    done

    # active services
    # same as enabled, but without core-config-seed and without mongo-worker as 
    # those are both oneshot daemons
    for svc in core-command core-data core-metadata security-services mongod consul ; do 
        svcStatus="$(snap services edgexfoundry.$svc | grep $svc | awk '{print $3}')"
        if [ "active" != "$svcStatus" ]; then
            echo "service $svc has status \"$svcStatus\" but should be active"
            exit 1
        fi
    done

    # disabled services
    for svc in export-distro export-client support-notifications support-scheduler support-rulesengine support-logging device-virtual device-modbus device-mqtt device-random; do 
        svcStatus="$(snap services edgexfoundry.$svc | grep $svc | awk '{print $2}')"
        if [ "disabled" != "$svcStatus" ]; then
            echo "service $svc has status \"$svcStatus\" but should be disabled"
            exit 1
        fi
    done

    # inactive services
    # all the disabled services + core-config-seed + mongo-worker
    for svc in export-distro export-client support-notifications support-scheduler support-rulesengine support-logging device-virtual device-modbus device-mqtt device-random core-config-seed; do 
        svcStatus="$(snap services edgexfoundry.$svc | grep $svc | awk '{print $3}')"
        if [ "inactive" != "$svcStatus" ]; then
            echo "service $svc has status \"$svcStatus\" but should be inactive"
            exit 1
        fi
    done
}

snap_remove()
{
    snap remove edgexfoundry || true
}
