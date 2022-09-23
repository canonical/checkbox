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
    echo "Installing $the_snap with channel $the_channel"

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
    echo "Refreshing $the_snap with channel $the_channel"

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

check_enabled_services()
{
    for svc in $1; do
        svcStatus="$(snap services edgexfoundry.$svc | grep $svc | awk '{print $2}')"
        if [ "enabled" != "$svcStatus" ]; then
            print_error_logs
            echo "service $svc has status \"$svcStatus\" but should be enabled"
            exit 1
        fi
    done
}

check_active_services()
{
    for svc in $1; do
        svcStatus="$(snap services edgexfoundry.$svc | grep $svc | awk '{print $3}')"
        if [ "active" != "$svcStatus" ]; then
            print_error_logs
            echo "service $svc has status \"$svcStatus\" but should be active"
            exit 1
        fi
    done
}

check_disabled_services()
{
    for svc in $1; do
        svcStatus="$(snap services edgexfoundry.$svc | grep $svc | awk '{print $2}')"
        if [ "disabled" != "$svcStatus" ]; then
            print_error_logs
            echo "service $svc has status \"$svcStatus\" but should be disabled"
            exit 1
        fi
    done
}

check_inactive_services()
{
    for svc in $1; do
        svcStatus="$(snap services edgexfoundry.$svc | grep $svc | awk '{print $3}')"
        if [ "inactive" != "$svcStatus" ]; then
            print_error_logs
            echo "service $svc has status \"$svcStatus\" but should be inactive"
            exit 1
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
                echo "check port "$1" status "$2" services timed out, current retry count: $i/300"

                if [ "$i" -ge 300 ]; then
                    print_error_logs
                    echo "check port "$1" status "$2" services timed out, reached maximum retry count of 300"
                    print_error_logs
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
                echo "check port "$1" status "$2" services timed out, current retry count: $i/300"

                if [ "$i" -ge 300 ]; then
                    print_error_logs
                    echo "check port "$1" status "$2" services timed out, reached maximum retry count of 300"
                    print_error_logs
                    exit 1
                else
                    sleep 1
                fi
            done
        fi
    fi
}

list_snap()
{
    local snap_name=$1
    snap list $snap_name | sed -n 2p
}

print_error_logs()
{
    echo "==========="
    echo "Error logs:"
    journalctl --since "$START_TIME" --no-pager | grep "edgexfoundry" | grep --ignore-case "error" | grep --invert-match "error=-1"
    echo "==========="
}


openssl_generate_certificate()
{
    SERVER_CERT_FILE=$1
    SERVER_KEY_FILE=$2
    SERVER_CSR_FILE=$3
    CA_CERT_FILE=$4
    CA_KEY_FILE=$5

    # Generate the Certificate Authority (CA) Private Key
    openssl ecparam -name prime256v1 -genkey -noout -out $CA_KEY_FILE
    # Generate the Certificate Authority Certificate
    openssl req -new -x509 -sha256 -key $CA_KEY_FILE -out $CA_CERT_FILE -subj "/CN=checkbox-test-ca"
    # Generate the Server Certificate Private Key
    openssl ecparam -name prime256v1 -genkey -noout -out $SERVER_KEY_FILE
    # Generate the Server Certificate Signing Request
    openssl req -new -sha256 -key $SERVER_KEY_FILE -out $SERVER_CSR_FILE -subj "/CN=localhost"
    # Generate the Server Certificate
    openssl x509 -req -in $SERVER_CSR_FILE -CA $CA_CERT_FILE -CAkey $CA_KEY_FILE -CAcreateserial -out $SERVER_CERT_FILE -days 1000 -sha256
}
