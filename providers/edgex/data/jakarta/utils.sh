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

# wait for services to come online
# NOTE: this may have to be significantly increased on arm64 or low RAM platforms
# to accomodate time for everything to come online
snap_wait_all_services_online()
{
    http_error_code_regex="4[0-9][0-9]|5[0-9][0-9]"
    all_services_online=false
    i=0

    while [ "$all_services_online" = "false" ];
    do
        echo "waiting for all services to come online. Current retry count: $i/300"
        #max retry avoids forever waiting
        ((i=i+1))
        if [ "$i" -ge 300 ]; then
            echo "services timed out, reached max retry count of 300"
            exit 1
        fi

        #dial services
        core_data_status_code=$(curl --insecure --silent --include \
            --connect-timeout 2 --max-time 5 \
            --output /dev/null --write-out "%{http_code}" \
            -X GET 'http://localhost:59880/api/v2/ping') || true
        core_metadata_status_code=$(curl --insecure --silent --include \
            --connect-timeout 2 --max-time 5 \
            --output /dev/null --write-out "%{http_code}" \
            -X GET 'http://localhost:59881/api/v2/ping') || true
        core_command_status_code=$(curl --insecure --silent --include \
            --connect-timeout 2 --max-time 5 \
            --output /dev/null --write-out "%{http_code}" \
            -X GET 'http://localhost:59882/api/v2/ping') || true

        #error status 4xx/5xx will fail the test immediately
        if [[ $core_data_status_code =~ $http_error_code_regex ]] \
            || [[ $core_metadata_status_code =~ $http_error_code_regex ]] \
            || [[ $core_command_status_code =~ $http_error_code_regex ]]; then
            echo "core service(s) received status code 4xx or 5xx"
            exit 1
        fi

        if [[ "$core_data_status_code" == 200 ]] \
            && [[ "$core_metadata_status_code" == 200 ]] \
            && [[ "$core_command_status_code" == 200 ]] \
            && [ -n "$(lsof -i -P -n -S 2 | grep 8000)" ] \
            && [ -n "$(lsof -i -P -n -S 2 | grep 8200)" ] \
            && [ -n "$(lsof -i -P -n -S 2 | grep 8500)" ] \
            && [ -n "$(lsof -i -P -n -S 2 | grep 5432)" ] \
            && [ -n "$(lsof -i -P -n -S 2 | grep 6379)" ]; then
            all_services_online=true
            echo "all services up"
        else
            sleep 1
        fi
    done
}

snap_wait_port_status()
{
    local port=$1
    local port_status=$2
    i=0

    if [ "$port_status" == "open" ]; then
            while [ -z "$(lsof -i -P -n -S 2 | grep "$port")" ];
            do
                #max retry avoids forever waiting
                ((i=i+1))
                if [ "$i" -ge 300 ]; then
                    echo "services timed out, reached max retry count of 300"
                    exit 1
                else
                    sleep 1
                fi
            done
    else
        if [ "$port_status" == "close" ]; then
            while [ -n "$(lsof -i -P -n -S 2 | grep "$port")" ];
            do
                #max retry avoids forever waiting
                ((i=i+1))
                if [ "$i" -ge 300 ]; then
                    echo "services timed out, reached max retry count of 300"
                    exit 1
                else
                    sleep 1
                fi
            done
        fi
    fi
}

