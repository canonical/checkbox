#!/bin/bash -e

# get the directory of this script
# snippet from https://stackoverflow.com/a/246128/10102404
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null && pwd )"

# load the jakarta release utils
# shellcheck source=/dev/null
source "$SCRIPT_DIR/utils.sh"

START_TIME=$(date +"%Y-%m-%d %H:%M:%S")

snap_remove

# install the snap to make sure it installs
if [ -n "$REVISION_TO_TEST" ]; then
    snap_install "$REVISION_TO_TEST" "$REVISION_TO_TEST_CHANNEL" "$REVISION_TO_TEST_CONFINEMENT"
else
    snap_install edgexfoundry "$DEFAULT_TEST_CHANNEL"  
fi

# wait for services to come online
snap_wait_all_services_online

# start device-virtual
snap start edgexfoundry.device-virtual

# wait for service to come online
snap_wait_port_status 59900 open

# ensure device-virtual is running
if [ "$(snap services edgexfoundry.device-virtual | grep -o inactive)" = "inactive" ]; then
    print_error_logs
    echo "failed to start device-virtual"
    exit 1
fi

echo -n "finding jq... "

set +e
if command -v edgexfoundry.jq > /dev/null; then
    JQ=$(command -v edgexfoundry.jq)
elif command -v jq > /dev/null; then
    JQ=$(command -v jq)
else
    echo "NOT FOUND"
    echo "install with \`snap install jq\`"
    exit 1
fi

echo "found at $JQ"

# a new try every other second, at max 30 tries is 1 minute for device-virtual
# to start
MAX_READING_TRIES=30
num_tries=0

# check to see if we can find the device created by device-virtual
while true; do
    FIND_DEVICE=$(edgexfoundry.curl -s localhost:59881/api/v2/device/all | $JQ '[.devices[] | select(.name == "Random-Boolean-Device")] | length')
    EXIT_CODE=$?
    if [ "$EXIT_CODE" -ne 0 ] ; then
        print_error_logs
        echo "Error finding the device created by device-virtual"
        exit 1
    fi
    
    if [ "$FIND_DEVICE" -lt 1 ]; then
        # increment number of tries
        num_tries=$((num_tries+1))
        if (( num_tries > MAX_READING_TRIES )); then
            print_error_logs
            echo "max tries attempting to get device-virtual devices"
            exit 1
        fi
        # no readings yet, keep waiting
        sleep 2
    else
        # got the device, break out
        break
    fi
done

# reset the number of tries
num_tries=0

# check to see if we can get a reading from the Random-Boolean-Device
while true; do
    FIND_READING=$(edgexfoundry.curl -s localhost:59880/api/v2/reading/device/name/Random-Boolean-Device | $JQ 'length')
    EXIT_CODE=$?
    if [ "$EXIT_CODE" -ne 0 ] ; then
        print_error_logs
        echo "Error getting a reading produced by device-virtual"
        exit 1
    fi

    if [ "$FIND_READING" -le 1 ]; then
        EXIT_CODE=$?
        # increment number of tries
        num_tries=$((num_tries+1))
        if (( num_tries > MAX_READING_TRIES )); then
            print_error_logs
            echo "max tries attempting to get device-virtual readings"
            exit 1
        fi
        # no readings yet, keep waiting
        sleep 2
    else
        # got at least one reading, break out
        break
    fi
done
set -e

# remove the snap to run the next test
snap_remove

