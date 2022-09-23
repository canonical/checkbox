#!/bin/bash -e
#
# This test validates the snap configure hook settings that are supported by
# the edgexfoundry snap.
#
# TODO:
#
# - add negative test (i.e. bad key(s)) -- should be ignored
# - add support for service restart
#   - ensure service has restarted!
#   - when services are restarted, overrides all work!
# - add support for redis options

# get the directory of this script
# snippet from https://stackoverflow.com/a/246128/10102404
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null && pwd )"

START_TIME=$(date +"%Y-%m-%d %H:%M:%S")

declare services
services[0]=core-data
services[1]=core-metadata
services[2]=core-command
services[3]=support-notifications
services[4]=support-scheduler
services[5]=sys-mgmt-agent

# define config to EdgeX environment variable mappings
#
# TODO: add scoping support (i.e. add a csv prefix to the keys
# which scopes the setting to one or more services. No prefix
# means "applies to all".
#
declare -A conf_to_env
conf_to_env[service_health-check-interval]="SERVICE_HEALTHCHECKINTERVAL/'20s'"
conf_to_env[service_host]="SERVICE_HOST/127.0.0.1"
conf_to_env[service_server-bind-addr]="SERVICE_SERVERBINDADDR/'localhost'"
conf_to_env[service_port]="SERVICE_PORT/2112"
conf_to_env[service_max-result-count]="SERVICE_MAXRESULTCOUNT/25000"
conf_to_env[service_max-request-size]="SERVICE_MAXREQUESTSIZE/200"
conf_to_env[service_startup-msg]="SERVICE_STARTUPMSG/'hello,world!'"
conf_to_env[service_request-timeout]="SERVICE_REQUESTTIMEOUT/10000"

# [Clients.Command]
conf_to_env[clients_core-command_port]="CLIENTS_CORECOMMAND_PORT/12"

# [Clients.Coredata]
conf_to_env[clients_core-data_port]="CLIENTS_COREDATA_PORT/12"

# [Clients.Metadata]
conf_to_env[clients_core-metadata_port]="CLIENTS_COREMETADATA_PORT/13"

# [Clients.Notifications]
conf_to_env[clients_support-notifications_port]="CLIENTS_SUPPORTNOTIFICATIONS_PORT/14"

# [Clients.Scheduler] - sys-mgmt-only
conf_to_env[clients_support-scheduler_port]="CLIENTS_SUPPORTSCHEDULER_PORT/14"

# [MessageQueue] -- core-data
conf_to_env[messagequeue_publish-topic-prefix]="MESSAGEQUEUE_PUBLISHTOPICPREFIX/'fubar'"

# load the latest release utils
# shellcheck source=/dev/null
source "$SCRIPT_DIR/utils.sh"

snap_remove

# install the snap to make sure it installs
if [ -n "$REVISION_TO_TEST" ]; then
    snap_install "$REVISION_TO_TEST" "$REVISION_TO_TEST_CHANNEL" "$REVISION_TO_TEST_CONFINEMENT"
else
    snap_install edgexfoundry "$DEFAULT_TEST_CHANNEL"
fi

# wait for services to come online
snap_wait_all_services_online

test_smtp() {
    # [Smtp] support-notifications options
    declare -A smtp_to_env
    smtp_to_env[smtp_host]="SMTP_HOST/127.0.0.1"
    smtp_to_env[smtp_username]="SMTP_USERNAME/'joe'"
    smtp_to_env[smtp_password]="SMTP_PASSWORD/'password!'"
    smtp_to_env[smtp_port]="SMTP_PORT/2112"
    smtp_to_env[smtp_sender]="SMTP_SENDER/'henry'"
    smtp_to_env[smtp_enable-self-signed-cert]="SMTP_ENABLE_SELF_SIGNED_CERT/true"

    for key in "${!smtp_to_env[@]}"; do
        echo "$key" --- ${smtp_to_env[$key]};

        option=${key/_/.}
        echo "$option"
        env=$(echo ${smtp_to_env[$key]} | cut -d / -f 1)
        val=$(echo ${smtp_to_env[$key]} | cut -d / -f 2)
        service_key="env.support-notifications.$option"
        snap set edgexfoundry "$service_key=$val"
    done
}

# test config hook service-specific config options
#
# Note, this test iterates through all of the possible configuration options.
# It currently only validates that the service.env for each service is created.
#
test_options()
{
    service="$1"
    for key in "${!conf_to_env[@]}"; do
        echo "$key" --- ${conf_to_env[$key]};

        if [ "$key" == "service_read-max-limit" ] &&
	   [ "$service" != "app-service-configurable" ]; then
	    continue
	fi

        if [ "$key" == "messagequeue_topic" ] &&
	   [ "$service" != "core-data" ]; then
	    continue
	fi

	# handle mismatched client keys due device-sdk-go bug
        if [ "$key" == "clients_coredata_port" ]; then
	    continue
	fi

	if [ "$key" == "clients_data_port" ]; then
            continue
	fi

        option=${key//_/.}
        echo "$option"
        env=$(echo ${conf_to_env[$key]} | cut -d / -f 1)
        val=$(echo ${conf_to_env[$key]} | cut -d / -f 2)
        service_key="env.$service.$option"
        snap set edgexfoundry "$service_key=$val"
        echo "$env=$val"
    done

    if [ "$service" == "support-notifications" ]; then
	test_smtp
    fi
}

validate_service_env()
{
    service="$1"
    snapFilePath="/var/snap/edgexfoundry/current/config/$service/res/$service.env"
    snapFile=$(cat "$snapFilePath" | sort)
    if [ -n "$SNAP" ]; then
        testFilePath="$SNAP/providers/checkbox-provider-edgex/data/latest/test-files/$service.env"
    else
        testFilePath="./test-files/$service.env"
    fi
    testFile=$(cat "$testFilePath" | sort)

    if [ "$snapFile" != "$testFile" ]; then
        snap_remove
        echo "$service.env file doesn't match test file."
        diff "$snapFilePath" "$testFilePath"
        exit 1
    fi
}

test_base_services()
{
	for key in "${!services[@]}"; do
            service=${services[key]}
            echo "*****${service}*******"
            test_options "$service"
	    validate_service_env "$service"
        done
}

# test-proxy
#
# ADD_PROXY_ROUTE is a csv list of URLs to be added to the
# API Gateway (aka Kong). For references:
#
# https://docs.edgexfoundry.org/2.1/security/Ch-APIGateway/
#
# NOTE - this setting is not a configuration override, it's a top-level
# environment variable used by the security-proxy-setup.
#
# KONGAUTH_NAME can be "jwt" (default) or "acl"
test_proxy()
{
    snap set edgexfoundry "env.security-proxy.add-proxy-route=myservice.http://localhost:2112"
    set +e
    match=$(grep "export ADD_PROXY_ROUTE=myservice.http://localhost:2112" \
	 /var/snap/edgexfoundry/current/config/security-proxy-setup/res/security-proxy-setup.env)
    set -e

    if [ -z "$match" ]; then
	snap_remove
	echo "security-proxy-setup.env file missing correct ADD_PROXY_ROUTE env export."
	exit 1
    fi

    snap set edgexfoundry "env.security-proxy.kongauth.name=jwt"
    set +e
    match=$(grep "export KONGAUTH_NAME=jwt" \
	 /var/snap/edgexfoundry/current/config/security-proxy-setup/res/security-proxy-setup.env)
    set -e

    if [ -z "$match" ]; then
	snap_remove
	echo "security-proxy-setup.env file missing correct KONGAUTH_NAME env export."
	exit 1
    fi

    snap set edgexfoundry "env.security-proxy.kongauth.name=acl"
    set +e
    match=$(grep "export KONGAUTH_NAME=acl" \
     /var/snap/edgexfoundry/current/config/security-proxy-setup/res/security-proxy-setup.env)
    set -e

    if [ -z "$match" ]; then
    snap_remove
    echo "security-proxy-setup.env file missing correct KONGAUTH_NAME env export."
    exit 1
    fi
}

# security-secret-store
#
# ADD_SECRETSTORE_TOKENS is a csv list of service keys to be added to the
# list of Vault tokens that security-file-token-provider (launched by
# security-secretstore-setup) creates.
#
# NOTE - this setting is not a configuration override, it's a top-level
# environment variable used by the security-secretstore-setup.
#
test_secret-store()
{
    snap set edgexfoundry "env.security-secret-store.add-secretstore-tokens=myservice,yourservice"

    set +e
    match=$(grep "export ADD_SECRETSTORE_TOKENS=myservice,yourservice" \
	 /var/snap/edgexfoundry/current/config/security-secretstore-setup/res/security-secretstore-setup.env)
    set -e

    if [ -z "$match" ]; then
	snap_remove
	echo "security-secretstore-setup.env file missing correct env export."
	exit 1
    fi
}

test_base_services
test_proxy
test_secret-store

# remove the snap to run the next test
snap_remove

