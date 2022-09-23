#!/bin/bash -e

# get the directory of this script
# snippet from https://stackoverflow.com/a/246128/10102404
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null && pwd )"

# load the jakarta release utils
# shellcheck source=/dev/null
source "$SCRIPT_DIR/utils.sh"

START_TIME=$(date +"%Y-%m-%d %H:%M:%S")

# remove the snap if it's already installed

snap_remove

# install the snap version we are testing
if [ -n "$REVISION_TO_TEST" ]; then
    snap_install "$REVISION_TO_TEST" "$REVISION_TO_TEST_CHANNEL" "$REVISION_TO_TEST_CONFINEMENT"
else
    snap_install edgexfoundry "$DEFAULT_TEST_CHANNEL" 
fi

# wait for services to come online
snap_wait_all_services_online

# now install the same snap version we are testing to test the pre-refresh
# and post-refresh logic in this revision
if [ -n "$REVISION_TO_TEST" ]; then
    snap_install "$REVISION_TO_TEST" "$REVISION_TO_TEST_CHANNEL" "$REVISION_TO_TEST_CONFINEMENT"
else
    # if we aren't running locally, then we need to download the revision and
    # install it locally as if it was a different revision
    snap_download_output=$(snap download edgexfoundry --channel="$DEFAULT_TEST_CHANNEL")
    THIS_REVISION_LOCALLY="$(pwd)/$(echo "$snap_download_output" | grep -Po 'edgexfoundry_[0-9]+\.snap')"
    snap_install "$THIS_REVISION_LOCALLY" "" "--devmode"
fi

# wait for services to come online
snap_wait_all_services_online

snap_check_svcs

# ensure the release config item is set to jakarta
snapRelease=$(snap get edgexfoundry release)
if [ "$snapRelease" != "jakarta" ]; then
    print_error_logs
    echo "missing or invalid config item for snap release: \"$snapRelease\""
    snap_remove
    exit 1
fi

snap_remove

