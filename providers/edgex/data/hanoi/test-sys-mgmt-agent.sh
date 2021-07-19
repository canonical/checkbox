#!/bin/bash -e

# get the directory of this script
# snippet from https://stackoverflow.com/a/246128/10102404
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null && pwd )"

# load the utils
# shellcheck source=/dev/null
source "$SCRIPT_DIR/utils.sh"

DEFAULT_TEST_CHANNEL=${DEFAULT_TEST_CHANNEL:-beta}

snap_remove

# now install the snap version we are testing and check again
if [ -n "$REVISION_TO_TEST" ]; then
    snap_install "$REVISION_TO_TEST" "$REVISION_TO_TEST_CHANNEL" "$REVISION_TO_TEST_CONFINEMENT"
else
    snap_install edgexfoundry "$DEFAULT_TEST_CHANNEL"  
fi

# wait for services to come online
# NOTE: this may have to be significantly increased on arm64 or low RAM platforms
# to accomodate time for everything to come online
sleep 120

# enable sys-mgmt-agent, as it's disabled by default in Geneva
snap set edgexfoundry sys-mgmt-agent=on
sleep 15

# make sure that core-data is running
if [ -n "$(snap services edgexfoundry.core-data | grep edgexfoundry.core-data | grep inactive)" ]; then
    echo "core-data is not running"
    snap_remove
    exit 1
fi

# issue a stop command to the SMA for core-data
edgexfoundry.curl \
    --fail \
    --header "Content-Type: application/json" \
    --request POST \
    --data '{"action":"stop","services":["edgex-core-data"]}' \
    localhost:48090/api/v1/operation

# check that core-data is no longer running
if [ -z "$(snap services edgexfoundry.core-data | grep edgexfoundry.core-data | grep inactive)" ]; then
    echo "SMA failed to stop core-data"
    snap_remove
    exit 1
fi

# TODO: enable these other tests for Edinburgh where they will actually work
# for delhi, only stopping services works with the SMA

# issue a start command to the SMA for core-data
edgexfoundry.curl \
    --fail \
    --header "Content-Type: application/json" \
    --request POST \
    --data '{"action":"start","services":["edgex-core-data"]}' \
    localhost:48090/api/v1/operation

# check that core-data is now running
if [ -n "$(snap services edgexfoundry.core-data | grep edgexfoundry.core-data | grep inactive)" ]; then
    echo "SMA failed to stop core-data"
    snap_remove
    exit 1
fi

# issue a bogus start command to the SMA to check that it returns an error message
set +e
fail_response=$(edgexfoundry.curl \
    --fail \
    --header "Content-Type: application/json" \
    --request POST \
    --data '{"action":"start","services":["NOT-A-REAL-SERVICE"]}' \
    localhost:48090/api/v1/operation | edgexfoundry.jq '.[0].Success')

echo "fail_response=$fail_response"

if [ "$fail_response" == "true" ]; then
    echo
    echo "SMA erronously reports starting a non-existent service"
    snap_remove
    exit 1
fi
set -e

snap_remove
