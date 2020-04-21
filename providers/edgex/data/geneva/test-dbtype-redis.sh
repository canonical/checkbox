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

# check that the config files use mongo currently
for svc in core-data core-metadata export-client support-notifications support-scheduler; do
    # the type should be mongodb
    if [ "$(toml2json < "/var/snap/edgexfoundry/current/config/$svc/res/configuration.toml" | jq -r '.Databases.Primary.Type')" != "mongodb" ]; then
        echo "incorrect initial setting for $svc primary database type"
        exit 1
    fi
    # the port should be 27017
    if [ "$(toml2json < "/var/snap/edgexfoundry/current/config/$svc/res/configuration.toml" | jq -r '.Databases.Primary.Port')" != "27017" ]; then
        echo "incorrect initial setting for $svc primary database port"
        exit 1
    fi
done

# ensure mongod is running
if [ -n "$(snap services edgexfoundry.mongod | grep edgexfoundry.mongod | grep inactive)" ]; then
    echo "mongod is not running initially"
    exit 1
fi

# ensure mongod is enabled
if [ -z "$(snap services edgexfoundry.mongod | grep edgexfoundry.mongod | grep enabled)" ]; then
    echo "mongod is not enabled initially"
    exit 1
fi

# ensure redis is not running
if [ -z "$(snap services edgexfoundry.redis | grep edgexfoundry.redis | grep inactive)" ]; then
    echo "redis is running initially"
    exit 1
fi

# ensure redis is disabled
if [ -z "$(snap services edgexfoundry.redis | grep edgexfoundry.redis | grep disabled)" ]; then
    echo "redis is enabled intially"
    exit 1
fi

# set the dbtype
snap set edgexfoundry dbtype=redis

# wait for services to start/restart
sleep 15

# ensure mongod isn't running
if [ -z "$(snap services edgexfoundry.mongod | grep edgexfoundry.mongod | grep inactive)" ]; then
    echo "mongod is still running after changing to redis"
    exit 1
fi

# ensure mongod is disabled
if [ -z "$(snap services edgexfoundry.mongod | grep edgexfoundry.mongod | grep disabled)" ]; then
    echo "mongod is still enabled after changing to redis"
    exit 1
fi

# ensure redis is now running
if [ -n "$(snap services edgexfoundry.redis | grep edgexfoundry.redis | grep inactive)" ]; then
    echo "redis is not running after changing to redis"
    exit 1
fi

# ensure redis is enabled
if [ -z "$(snap services edgexfoundry.redis | grep edgexfoundry.redis | grep enabled)" ]; then
    echo "redis is not enabled after changing to redis"
    exit 1
fi

# check that the config files now use redis currently
for svc in core-data core-metadata export-client support-notifications support-scheduler; do
    # the type should be redisdb
    if [ "$(toml2json < "/var/snap/edgexfoundry/current/config/$svc/res/configuration.toml" | jq -r '.Databases.Primary.Type')" != "redisdb" ]; then
        echo "incorrect changed setting for $svc primary database type"
        exit 1
    fi
    # the port should be 6379
    if [ "$(toml2json < "/var/snap/edgexfoundry/current/config/$svc/res/configuration.toml" | jq -r '.Databases.Primary.Port')" != "6379" ]; then
        echo "incorrect changed setting for $svc primary database port"
        exit 1
    fi
done

# support-logging should now have file persistence
if [ "$(toml2json < "/var/snap/edgexfoundry/current/config/support-logging/res/configuration.toml" | jq -r '.Writable.Persistence')" != "file" ]; then
    echo "incorrect initial setting for support-logging persistence mechanism"
    exit 1
fi

# remove the snap to run again
snap_remove
