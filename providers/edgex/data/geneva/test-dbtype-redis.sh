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

# set the dbtype to mongodb
snap set edgexfoundry dbtype=mongodb
sleep 15

# set the dbtype back to redis
snap set edgexfoundry dbtype=redis
sleep 15

test_db_type "redisdb" "6379"

# ensure redis is running
if [ -n "$(snap services edgexfoundry.redis | grep edgexfoundry.redis | grep inactive)" ]; then
    echo "redis is not running initially"
    exit 1
fi

# ensure redis is enabled
if [ -z "$(snap services edgexfoundry.redis | grep edgexfoundry.redis | grep enabled)" ]; then
    echo "redis is not enabled initially"
    exit 1
fi

# ensure mongo is not running
if [ -z "$(snap services edgexfoundry.mongod | grep edgexfoundry.mongod | grep inactive)" ]; then
    echo "mongod is running initially"
    exit 1
fi

# ensure mongo is disabled
if [ -z "$(snap services edgexfoundry.mongod | grep edgexfoundry.mongod | grep disabled)" ]; then
    echo "mongod is enabled intially"
    exit 1
fi

# remove the snap to run again
snap_remove
