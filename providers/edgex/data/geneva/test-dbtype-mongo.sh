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

echo -n "finding jq... "

set +e
if command -v edgexfoundry.jq > /dev/null; then
    JQ=$(command -v edgexfoundry.jq)
elif command -v jq > /dev/null; then
    JQ=$(command -v jq)
else
    echo "NOT FOUND"
    echo "install with snap install jq"
    exit 1
fi

echo "found at $JQ"

echo -n "finding toml2json... "

set +e
if ! command -v toml2json > /dev/null; then
    echo "NOT FOUND"
    echo "install with \`snap install remarshal\`"
    exit 1
fi

echo "found at $(command -v toml2json)"

# wait for services to start up
sleep 120

# check that the settings are for redis currently
test_db_type "redisdb" "6379"

# ensure redis is running
if [ "$(snap services edgexfoundry.redis | grep -o inactive)" = "inactive" ]; then
    echo "redis is not running initially"
    exit 1
fi

# ensure redis is enabled
if [ "$(snap services edgexfoundry.redis | grep -o disabled)" = "disabled" ]; then
    echo "redis is not enabled initially"
    exit 1
fi

# ensure mongod is not running
if [ "$(snap services edgexfoundry.mongod | grep -o inactive)" != "inactive" ]; then
    echo "mongod is running initially"
    exit 1
fi

# ensure mongod is disabled
if [ "$(snap services edgexfoundry.mongod | grep -o disabled)" != "disabled" ]; then
    echo "mongod is enabled intially"
    exit 1
fi

# set the dbtype
snap set edgexfoundry dbtype=mongodb

# wait for services to start/restart
sleep 15

# ensure redis isn't running
if [ "$(snap services edgexfoundry.redis | grep -o inactive)" != "inactive" ]; then
    echo "redis is still running after changing to mongodb"
    exit 1
fi

# ensure redis is disabled
if [ "$(snap services edgexfoundry.redis | grep -o disabled)" != "disabled" ]; then
    echo "redis is still enabled after changing to mongodb"
    exit 1
fi

# ensure mongod is now running
if [ "$(snap services edgexfoundry.mongod | grep -o inactive)" = "inactive" ]; then
    echo "mongod is not running after changing to mongodb"
    exit 1
fi

# ensure mongod is enabled
if [ "$(snap services edgexfoundry.mongod | grep disabled)" = "disabled" ]; then
    echo "mongod is not enabled after changing to mongodb"
    exit 1
fi

# check that the consul settings are for mongodb currently
test_db_type "mongodb" "27017"

# remove the snap to run again
snap_remove
