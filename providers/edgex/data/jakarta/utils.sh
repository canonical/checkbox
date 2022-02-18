#!/bin/bash -e

# get the directory of this script
# snippet from https://stackoverflow.com/a/246128/10102404
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null && pwd )"

# load the generic utils
# shellcheck source=/dev/null
source "$(dirname "$SCRIPT_DIR")/utils.sh"

# if default is not given, we use beta risk level of this track
TRACK_BETA=2.1/beta
if [ -n "$DEFAULT_TEST_CHANNEL" ]; then
    echo "DEFAULT_TEST_CHANNEL set to $DEFAULT_TEST_CHANNEL"
else
    echo "DEFAULT_TEST_CHANNEL not set. Setting to $TRACK_BETA"
    export DEFAULT_TEST_CHANNEL=$TRACK_BETA
fi

snap_check_svcs()
{
    # group services by status

    declare -a arr_enabled_services=(
        # core services 
        "redis" 
        "core-data"
        "core-command"
        "core-metadata"
        # security services
        "kong-daemon" "postgres" "vault" "consul" 
        # one-shot security services
        "security-proxy-setup"
        "security-secretstore-setup"
        "security-bootstrapper-redis"
        "security-consul-bootstrapper") 

    declare -a arr_active_services=(
        # core services 
        "redis" 
        "core-data"
        "core-command"
        "core-metadata"
        # security services
        "kong-daemon" "postgres" "vault" "consul")

    declare -a arr_disabled_services=(
        # app service, kuiper and device-virtual
        "kuiper" 
        "app-service-configurable"
        "device-virtual"
        # support services, system service
        "support-notifications"
        "support-scheduler"
        "sys-mgmt-agent")

    declare -a arr_inactive_services=(
        # app service, kuiper and device-virtual
        "kuiper" 
        "app-service-configurable"
        "device-virtual"
        # one-shot security services
        "security-proxy-setup"
        "security-secretstore-setup"
        "security-bootstrapper-redis"
        "security-consul-bootstrapper"
        # support services, system service
        "support-notifications"
        "support-scheduler"
        "sys-mgmt-agent")

    check_enabled_services "${arr_enabled_services[@]}"
    check_active_services "${arr_active_services[@]}"
    check_disabled_services "${arr_disabled_services[@]}"
    check_inactive_services "${arr_inactive_services[@]}"
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
        ((i=i+1))
        echo "waiting for all services to come online. Current retry count: $i/300"
        #max retry avoids forever waiting
        if [ "$i" -ge 300 ]; then
            print_error_logs
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
            && snap_wait_port_status 8000 open \
            && snap_wait_port_status 8200 open \
            && snap_wait_port_status 8500 open \
            && snap_wait_port_status 5432 open \
            && snap_wait_port_status 6379 open; then
            all_services_online=true
            echo "all services up"
        else
            sleep 1
        fi
    done
}

