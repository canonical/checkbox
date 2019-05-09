#!/bin/bash -e

# get the directory of this script
# snippet from https://stackoverflow.com/a/246128/10102404
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null && pwd )"

# helper function to download the snap, ack the assertion and return the
# name of the file
snap_download_and_ack()
{
    # download the snap and grep the output for the assert file so we can ack 
    # it
    snap_download_output=$(snap download "$1" "$2")
    snap ack "$(echo "$snap_download_output" | grep -Po 'edgexfoundry_[0-9]+\.assert')"
    # return the name of this snap
    echo "$(pwd)"/"$(echo "$snap_download_output" | grep -Po 'edgexfoundry_[0-9]+\.snap')"
}

# if this script was provided with an argument, then assume it's a local snap
# to test and confirm that the file exists
# otherwise if we didn't get any arguments assume to test the snap from beta
if [ -n "$1" ]; then
    if [ -f "$1" ]; then
        REVISION_TO_TEST=$1
        REVISION_TO_TEST_CHANNEL=""
        REVISION_TO_TEST_CONFINEMENT="--devmode"
    else
        echo "local snap to test: \"$1\" does not exist"
        exit 1
    fi
else 
    REVISION_TO_TEST=$(snap_download_and_ack edgexfoundry --beta)
    REVISION_TO_TEST_CHANNEL=""
    REVISION_TO_TEST_CONFINEMENT=""
fi

# export the revision to test env vars
export REVISION_TO_TEST
export REVISION_TO_TEST_CHANNEL
export REVISION_TO_TEST_CONFINEMENT

# download and ack the stable and delhi channels as we have tests to ensure
# there's a smooth upgrade between those channels and this one that is 
# under consideration
EDGEX_STABLE_SNAP_FILE=$(snap_download_and_ack edgexfoundry --stable)
EDGEX_DELHI_SNAP_FILE=$(snap_download_and_ack edgexfoundry --channel=delhi)

# export the names of the stable and delhi snap files
export EDGEX_STABLE_SNAP_FILE
export EDGEX_DELHI_SNAP_FILE

# run all the tests (except this file obviously)
for file in "$SCRIPT_DIR"/test-*.sh; do 
    "$file"
done
