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

snap_check_geneva_svcs()
{
    if [ "$1" = "--notfatal" ]; then
        FATAL=0
    else   
        FATAL=1
    fi
    # group services by status

    # enabled services
    # all the core-* services, security-services, consul, and redis
    for svc in consul core-command core-data core-metadata kong-daemon redis postgres security-proxy-setup security-secrets-setup security-secretstore-setup vault; do
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
    for svc in app-service-configurable device-virtual edgex-mongo support-logging mongod support-notifications support-rulesengine support-scheduler sys-mgmt-agent; do
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

    for svc in app-service-configurable device-virtual edgex-mongo mongod security-proxy-setup security-secrets-setup security-secretstore-setup support-logging \
        support-notifications support-rulesengine support-scheduler sys-mgmt-agent; do
        svcStatus="$(snap services edgexfoundry.$svc | grep $svc | awk '{print $3}')"
        if [ "inactive" != "$svcStatus" ]; then
            echo "service $svc has status \"$svcStatus\" but should be inactive"
            if [ "$FATAL" = "1" ]; then
                exit 1
            fi
        fi
    done
}

snap_check_hanoi_svcs()
{
    if [ "$1" = "--notfatal" ]; then
        FATAL=0
    else   
        FATAL=1
    fi
    # group services by status

    # enabled services
    # all the core-* services, security-services, consul, and redis
    for svc in consul core-command core-data core-metadata kong-daemon redis postgres security-proxy-setup security-secrets-setup security-secretstore-setup vault; do
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
    for svc in app-service-configurable device-virtual support-notifications support-scheduler sys-mgmt-agent; do
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

    for svc in app-service-configurable device-virtual security-proxy-setup security-secrets-setup security-secretstore-setup \
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

snap_check_ireland_svcs()
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

test_db_type()
{
    # check that the settings are for redis currently
    for svc in core-command core-data core-metadata support-notifications support-scheduler; do

        # if service is running check values in consul, else check config files
        status="$(snap services edgexfoundry.$svc | grep -o inactive)"
        if [ "$status" = "inactive" ]; then
            type="$(toml2json < "/var/snap/edgexfoundry/current/config/$svc/res/configuration.toml" | jq -r '.Databases.Primary.Type')"
            port="$(toml2json < "/var/snap/edgexfoundry/current/config/$svc/res/configuration.toml" | jq -r '.Databases.Primary.Port')"
            echo "config: svc: $svc type: $type port: $port"
        else
            type=$(edgexfoundry.curl -s http://localhost:8500/v1/kv/edgex/core/1.0/edgex-"$svc"/Databases/Primary/Type?raw)
            port=$(edgexfoundry.curl -s http://localhost:8500/v1/kv/edgex/core/1.0/edgex-"$svc"/Databases/Primary/Port?raw)
            echo "consul: svc: $svc type: $type port: $port"
        fi

        echo "after checks...: type: $type port: $port"

        if [ "$type" != "$1" ]; then
            echo "incorrect initial setting for $svc primary database type: $type"
            exit 1
        fi

        if [ "$port" != "$2" ]; then
            echo "incorrect initial setting for $svc primary database port: $port"
            exit 1
        fi
    done
}
