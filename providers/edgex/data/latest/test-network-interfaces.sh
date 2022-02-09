#!/bin/bash -e

# get the directory of this script
# snippet from https://stackoverflow.com/a/246128/10102404
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null && pwd )"

# load the latest release utils
# shellcheck source=/dev/null
source "$SCRIPT_DIR/utils.sh"

snap_remove

START_TIME=$(date +"%Y-%m-%d %H:%M:%S")

# install the snap to make sure it installs
if [ -n "$REVISION_TO_TEST" ]; then
    snap_install "$REVISION_TO_TEST" "$REVISION_TO_TEST_CHANNEL" "$REVISION_TO_TEST_CONFINEMENT"
else
    snap_install edgexfoundry "$DEFAULT_TEST_CHANNEL"
fi

# wait for services to come online
snap_wait_all_services_online

# edgex's core-data service listens by default on port 59880. Ensure that
# it's not listening on all interfaces (e.g. *:59880), and can only be
# reached via localhost
core_data_socket=`lsof -nPi :59880`
if echo "$core_data_socket" | grep "TCP \*:59880 (LISTEN)" ; then
    print_error_logs
    echo "fail - listening on 0.0.0.0"
    exit 1
elif echo "$core_data_socket" | grep "TCP 127.0.0.1:59880 (LISTEN)" ; then

    echo "pass - listening on 127.0.0.1"
else
    print_error_logs
    echo "fail - did not find service on port 59880 - is edgexfoundry running?"
    exit 1
fi

# remove the snap to run again
snap_remove

