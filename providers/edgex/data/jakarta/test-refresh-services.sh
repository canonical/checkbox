#!/bin/bash -e

# This test validates a smooth upgrade between 2.1/stable channel and 2.1/beta channel

# get the directory of this script
# snippet from https://stackoverflow.com/a/246128/10102404
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null && pwd )"

# load the jakarta release utils
# shellcheck source=/dev/null
source "$SCRIPT_DIR/utils.sh"

START_TIME=$(date +"%Y-%m-%d %H:%M:%S")
EDGEX_STABLE_CHANNEL="2.1/stable"

snap_remove

if [ -n "$EDGEX_PREV_STABLE_SNAP_FILE" ]; then
    echo "Installing snap from locally cached version"
    snap_install "$EDGEX_PREV_STABLE_SNAP_FILE"
else
    echo "Installing snap from channel"
    snap_install edgexfoundry $EDGEX_STABLE_CHANNEL
fi 
ORIGINAL_VERSION=$(list_snap edgexfoundry)
echo "Installed $ORIGINAL_VERSION"

# wait for services to come online
snap_wait_all_services_online

# now upgrade the snap from 2.1/stable to 2.1/beta
if [ -n "$REVISION_TO_TEST" ]; then
    snap_install "$REVISION_TO_TEST" "$REVISION_TO_TEST_CHANNEL" "$REVISION_TO_TEST_CONFINEMENT"
else
    snap_refresh edgexfoundry "$DEFAULT_TEST_CHANNEL"
fi
UPGRADED_VERSION=$(list_snap edgexfoundry)

# wait for services to come online
snap_wait_all_services_online

echo -e "Successfully upgraded:\n\tfrom: $ORIGINAL_VERSION\n\tto:   $UPGRADED_VERSION"

echo "All done. Cleaning up"
# remove the snap to run the next test
snap_remove

