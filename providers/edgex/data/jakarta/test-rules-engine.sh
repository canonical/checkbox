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

# enable kuiper/rules engine, as it's disabled by default
snap set edgexfoundry kuiper=on
sleep 15

# make sure that app-service-configurable is started
if [ -n "$(snap services edgexfoundry.app-service-configurable | grep edgexfoundry.app-service-configurable | grep inactive)" ]; then
    echo "app-service-configurable is not running"
    snap_remove
    exit 1
fi

# disable the kuiper for app-service-configurable
snap set edgexfoundry kuiper=off
sleep 15

# check that app-service-configurable is no longer running either
if [ -z "$(snap services edgexfoundry.app-service-configurable | grep edgexfoundry.app-service-configurable | grep inactive)" ]; then
    echo "kuiper failed to stop app-service-configurable"
    snap_remove
    exit 1
fi

# remove the snap to run the next test
snap_remove
