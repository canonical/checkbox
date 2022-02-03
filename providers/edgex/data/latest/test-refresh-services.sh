#!/bin/bash -e

# This test validates a smooth upgrade between 2.0/stable channel and latest/beta channel

# get the directory of this script
# snippet from https://stackoverflow.com/a/246128/10102404
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null && pwd )"

# load the latest release utils
# shellcheck source=/dev/null
source "$SCRIPT_DIR/utils.sh"

START_TIME=$(date +"%Y-%m-%d %H:%M:%S")
DEFAULT_TEST_CHANNEL=${DEFAULT_TEST_CHANNEL:-beta}
EDGEX_STABLE_CHANNEL="2.0/stable"

snap_remove

if [ -n "$EDGEX_PREV_STABLE_SNAP_FILE" ]; then
    echo "Installing snap from locally cached version"
    snap_install "$EDGEX_PREV_STABLE_SNAP_FILE"
else
    echo "Installing snap from channel"
    snap_install edgexfoundry $EDGEX_STABLE_CHANNEL
fi 
ORIGINAL_VERSION=$(print_snap_version edgexfoundry)
echo "Installed $ORIGINAL_VERSION"

# wait for services to come online
snap_wait_all_services_online

# now upgrade the snap from stable to latest
if [ -n "$REVISION_TO_TEST" ]; then
    snap_install "$REVISION_TO_TEST" "$REVISION_TO_TEST_CHANNEL" "$REVISION_TO_TEST_CONFINEMENT"
else
    snap_refresh edgexfoundry "$DEFAULT_TEST_CHANNEL"
fi
UPGRADED_VERSION=$(print_snap_version edgexfoundry)

# wait for services to come online
snap_wait_all_services_online

echo "Successfully upgraded from $ORIGINAL_VERSION to $UPGRADED_VERSION"

echo "All done. Cleaning up"
# remove the snap to run the next test
snap_remove

