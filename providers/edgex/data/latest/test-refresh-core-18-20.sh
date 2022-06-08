#!/bin/bash -e

# This test validates that Kong configuration is correctly migrated from
# postgres 10 to postgres 12.

# get the directory of this script
# snippet from https://stackoverflow.com/a/246128/10102404
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null && pwd )"

# load the latest release utils
# shellcheck source=/dev/null
source "$SCRIPT_DIR/utils.sh"

START_TIME=$(date +"%Y-%m-%d %H:%M:%S")

# remove the current snap
snap_remove

# install previous stable
EDGEX_PREV_STABLE_CHANNEL="latest/stable"
snap_install edgexfoundry $EDGEX_PREV_STABLE_CHANNEL

# wait for services to come online
snap_wait_all_services_online

# generate a user and the JWT token

# Due to confinement issues when running this test, we write the private key to SNAP_DATA
EDGEXFOUNDRY_SNAP_DATA="/var/snap/edgexfoundry/current/checkbox"
mkdir -p $EDGEXFOUNDRY_SNAP_DATA

echo "Generating private key"
openssl ecparam -genkey -name prime256v1 -noout -out $EDGEXFOUNDRY_SNAP_DATA/private.pem
echo "Generating public key"
openssl ec -in $EDGEXFOUNDRY_SNAP_DATA/private.pem -pubout -out $EDGEXFOUNDRY_SNAP_DATA/public.pem
PUBLIC_KEY=$(< $EDGEXFOUNDRY_SNAP_DATA/public.pem)
 
echo "Setting security-proxy user"
snap set edgexfoundry env.security-proxy.user=user01,USER_ID,ES256
echo "Setting security-proxy public key"
snap set edgexfoundry env.security-proxy.public-key="$PUBLIC_KEY"

echo "Generating JWT"
# this command doesn't write errors to stderr. Check the exit code before using the output:
if ! OUT=$(edgexfoundry.secrets-config proxy jwt --algorithm ES256 --private_key $EDGEXFOUNDRY_SNAP_DATA/private.pem --id USER_ID --expiration=1h)
then
    print_error_logs
    >&2 echo $OUT
    exit 1
fi
TOKEN=$OUT

echo "Got Token: $TOKEN"

# note: we need to use "edgexfoundry.curl", not "curl" to correctly support TLS 1.2
echo "Verifying JWT token using edgexfoundry $EDGEX_PREV_STABLE_CHANNEL"
code=$(edgexfoundry.curl --insecure --show-error --silent --include \
    --output /dev/null --write-out "%{http_code}" \
    -X GET 'https://localhost:8443/core-data/api/v2/ping?' \
    -H "Authorization: Bearer $TOKEN") 
if [[ $code != 200 ]]; then
    print_error_logs
    >&2 echo "JWT authentication failed with $code"
    snap_remove
    exit 1
else
    echo "JWT authentication succeeded"
fi

# now install the snap version we are testing and check again

if [ -n "$REVISION_TO_TEST" ]; then
    echo "Installing $REVISION_TO_TEST"
    snap_install "$REVISION_TO_TEST" "$REVISION_TO_TEST_CHANNEL" "$REVISION_TO_TEST_CONFINEMENT"
else
    echo "Installing edgexfoundry --channel=$DEFAULT_TEST_CHANNEL"
    snap_refresh edgexfoundry "$DEFAULT_TEST_CHANNEL"
fi

# wait for services to come online
# NOTE: this may have to be significantly increased on arm64 or low RAM platforms
# to accomodate time for everything to come online
snap_wait_all_services_online
 

# recheck
code=$(edgexfoundry.curl --insecure --show-error --silent --include \
    --output /dev/null --write-out "%{http_code}" \
    -X GET 'https://localhost:8443/core-data/api/v2/ping?' \
    -H "Authorization: Bearer $TOKEN")
if [[ $code != 200 ]]; then
    print_error_logs
    >&2 echo "JWT authentication failed with $code"
    snap_remove
    exit 1
else
    echo "JWT authentication succeeded"
fi
 
echo "All done. Cleaning up"
# remove the snap to run the next test
snap_remove
 

