#!/bin/bash -e

# This test checks if the pre-refresh hook work

# get the directory of this script
# snippet from https://stackoverflow.com/a/246128/10102404
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null && pwd )"

# load the latest release utils
# shellcheck source=/dev/null
source "$SCRIPT_DIR/utils.sh"

START_TIME=$(date +"%Y-%m-%d %H:%M:%S")

snap_remove

if [ -n "$REVISION_TO_TEST" ]; then
    echo "Installing snap from locally cached version"
    snap_install "$REVISION_TO_TEST" "$REVISION_TO_TEST_CHANNEL" "$REVISION_TO_TEST_CONFINEMENT"
else
    echo "Installing snap from channel"
    snap_install edgexfoundry "$DEFAULT_TEST_CHANNEL" 
fi

# wait for services to come online
snap_wait_all_services_online


if [ -n "$REVISION_TO_TEST" ]; then
    echo "Install the same snap version we are testing to test the pre-refresh in this revision"
    snap_install "$REVISION_TO_TEST" "$REVISION_TO_TEST_CHANNEL" "$REVISION_TO_TEST_CONFINEMENT"
else
    echo "Downloading the revision"
    snap_download_output=$(snap download edgexfoundry --channel="$DEFAULT_TEST_CHANNEL")
    THIS_REVISION_LOCALLY="$(pwd)/$(echo "$snap_download_output" | grep -Po 'edgexfoundry_[0-9]+\.snap')"
    echo "Installing the revision locally as if it was a different revision"
    snap_install "$THIS_REVISION_LOCALLY" "" "--devmode"
fi

# wait for services to come online
snap_wait_all_services_online

echo "All done. Cleaning up"
# remove the snap to run the next test
snap_remove

