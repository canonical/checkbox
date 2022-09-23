#!/bin/bash -e

# get the directory of this script
# snippet from https://stackoverflow.com/a/246128/10102404
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null && pwd )"

# load the utils
# shellcheck source=/dev/null
source "$SCRIPT_DIR/utils.sh"

snap_remove

DEFAULT_TEST_CHANNEL=${DEFAULT_TEST_CHANNEL:-beta}

# install the snap to make sure it installs
if [ -n "$REVISION_TO_TEST" ]; then
    snap_install "$REVISION_TO_TEST" "$REVISION_TO_TEST_CHANNEL" "$REVISION_TO_TEST_CONFINEMENT"
else
    snap_install edgexfoundry "$DEFAULT_TEST_CHANNEL"
fi


if lsof -i -P -n | grep "TCP \*:48080 (LISTEN)" ; then
    echo "fail - listening on 0.0.0.0"
    exit 1
elif lsof -i -P -n | grep "TCP 127.0.0.1:48080 (LISTEN)" ; then
    echo "pass - listening on 127.0.0.1"
else
    echo "fail - did not find service on port 48080 - is edgexfoundry running?"
    exit 1
fi


# remove the snap to run again
snap_remove
