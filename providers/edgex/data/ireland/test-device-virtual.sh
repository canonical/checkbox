#!/bin/bash -e

# get the directory of this script
# snippet from https://stackoverflow.com/a/246128/10102404
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null && pwd )"

# load the utils
# shellcheck source=/dev/null
source "$SCRIPT_DIR/utils.sh"

DEFAULT_TEST_CHANNEL=${DEFAULT_TEST_CHANNEL:-beta}

snap_remove

# install the snap to make sure it installs
if [ -n "$REVISION_TO_TEST" ]; then
    snap_install "$REVISION_TO_TEST" "$REVISION_TO_TEST_CHANNEL" "$REVISION_TO_TEST_CONFINEMENT"
else
    snap_install edgexfoundry "$DEFAULT_TEST_CHANNEL"  
fi

# wait for services to come online
# NOTE: this may have to be significantly increased on arm64 or low RAM platforms
# to accomodate time for everything to come online
sleep 120

# start device-virtual
snap start edgexfoundry.device-virtual

# wait 120 seconds as device-virtual takes close to ~2:30 before devices are created
sleep 120

# ensure device-virtual is running
if [ "$(snap services edgexfoundry.device-virtual | grep -o inactive)" = "inactive" ]; then
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
    if ! (edgexfoundry.curl -s localhost:59881/api/v2/device | $JQ '.'); then
        # not json - something's wrong
        echo "invalid JSON response from core-metadata"
        exit 1
    elif [ "$(edgexfoundry.curl -s localhost:59881/api/v2/device | $JQ 'map(select(.name == "Random-Boolean-Device")) | length')" -lt 1 ]; then
        # increment number of tries
        num_tries=$((num_tries+1))
        if (( num_tries > MAX_READING_TRIES )); then
            echo "max tries attempting to get device-virtual readings"
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

if ! (edgexfoundry.curl -s localhost:59880/api/v2/reading/device/Random-Boolean-Device/10 | $JQ '.'); then
    # not json - something's wrong
    echo "invalid JSON response from core-data"
    exit 1
fi

# check to see if we can get a reading from the Random-Boolean-Device
while true; do
    retval="$(edgexfoundry.curl -s localhost:59880/api/v2/reading/device/Random-Boolean-Device/10 | $JQ 'length')"
    echo "retval: $retval"

    if [ "$retval" -le 1 ]; then
        # increment number of tries
        num_tries=$((num_tries+1))
        if (( num_tries > MAX_READING_TRIES )); then
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
