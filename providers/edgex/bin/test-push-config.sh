#!/bin/bash -e

# get the directory of this script
# snippet from https://stackoverflow.com/a/246128/10102404
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null && pwd )"

# load the utils
# shellcheck source=/dev/null
source "$SCRIPT_DIR/utils.sh"

SNAP_DATA=/var/snap/edgexfoundry/current

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

echo -n "finding json2toml... "

set +e
if ! command -v json2toml > /dev/null; then
    echo "NOT FOUND"
    echo "install with \`snap install remarshal\`"
    exit 1
fi

echo "found at $(command -v json2toml)"

# wait for services to start up
sleep 120

# make sure the key we check is what we expect it to be
if [ "$(curl -s http://localhost:8500/v1/kv/edgex/core/1.0/edgex-core-data/Service/StartupMsg | $JQ -r '.[0].Value' | base64 --decode)" != "This is the Core Data Microservice" ]; then
    echo "unknown default value for core-data Service.StartUpMsg"
    exit 1
fi

# change the StartUpMsg to something else in the configuration.toml file
toml2json < $SNAP_DATA/config/core-data/res/configuration.toml | \
    jq -r '.Service.StartupMsg = "hello"' | \
    json2toml --preserve-key-order > \
    "$SNAP_DATA/config/core-data/res/configuration.toml.tmp"
mv "$SNAP_DATA/config/core-data/res/configuration.toml.tmp" \
    "$SNAP_DATA/config/core-data/res/configuration.toml"

# restart config-seed to confirm that the value doesn't change until we use 
# the push-config app
snap restart edgexfoundry.core-config-seed
sleep 15

if [ "$(curl -s http://localhost:8500/v1/kv/edgex/core/1.0/edgex-core-data/Service/StartupMsg | $JQ -r '.[0].Value' | base64 --decode)" != "This is the Core Data Microservice" ]; then
    echo "value for core-data Service.StartUpMsg changed unexpectedly"
    exit 1
fi

# now run the push-config app to run config-seed with -overwrite
edgexfoundry.push-config
sleep 15

# check that the value is now "hello"
if [ "$(curl -s http://localhost:8500/v1/kv/edgex/core/1.0/edgex-core-data/Service/StartupMsg | $JQ -r '.[0].Value' | base64 --decode)" != "hello" ]; then
    echo "value for core-data Service.StartUpMsg was not successfully changed"
    exit 1
fi

# remove the snap to run again
snap_remove
