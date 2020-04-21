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

# set to redis, assume that this change works, it's tested already elsewhere
snap set edgexfoundry dbtype=redis
sleep 15

# set back to mongo now
snap set edgexfoundry dbtype=mongodb
sleep 15

# check that the config files use mongo now
for svc in core-data core-metadata export-client support-notifications support-scheduler; do
    # the type should be mongodb
    if [ "$(toml2json < "/var/snap/edgexfoundry/current/config/$svc/res/configuration.toml" | jq -r '.Databases.Primary.Type')" != "mongodb" ]; then
        echo "incorrect setting for $svc primary database type after changing to mongo"
        exit 1
    fi
    # the port should be 27017
    if [ "$(toml2json < "/var/snap/edgexfoundry/current/config/$svc/res/configuration.toml" | jq -r '.Databases.Primary.Port')" != "27017" ]; then
        echo "incorrect setting for $svc primary database port after changing to mongo"
        exit 1
    fi
done

# ensure mongod is running
if [ -n "$(snap services edgexfoundry.mongod | grep edgexfoundry.mongod | grep inactive)" ]; then
    echo "mongod is not running after changing to mongo"
    exit 1
fi

# ensure mongod is enabled
if [ -z "$(snap services edgexfoundry.mongod | grep edgexfoundry.mongod | grep enabled)" ]; then
    echo "mongod is not enabled after changing to mongo"
    exit 1
fi

# ensure redis is not running
if [ -z "$(snap services edgexfoundry.redis | grep edgexfoundry.redis | grep inactive)" ]; then
    echo "redis is running after changing to mongo"
    exit 1
fi

# ensure redis is disabled
if [ -z "$(snap services edgexfoundry.redis | grep edgexfoundry.redis | grep disabled)" ]; then
    echo "redis is enabled after changing to mongo"
    exit 1
fi

# remove the snap to run again
snap_remove
