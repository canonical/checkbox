#!/bin/bash -e

: '
This test verifies the correct migration of postgres from v10 to v12

1)  A kong.sql file and a key pair have been manually generated and included in
    the test-files directory. For reference, that was done using:

        # install Ireland version
        sudo snap remove --purge edgexfoundry
        sudo snap install edgexfoundry --channel=2.0/stable

        # create keys
        openssl ecparam -genkey -name prime256v1 -noout -out private.pem
        openssl ec -in private.pem -pubout -out public.pem

        # set up Kong user
        PUBLIC_KEY=$(< public.pem)
        sudo snap set edgexfoundry env.security-proxy.user=user01,USER_ID,ES256
        sudo snap set edgexfoundry env.security-proxy.public-key="$PUBLIC_KEY"

        # create JWT token for user
        edgexfoundry.secrets-config proxy jwt --algorithm ES256 --private_key private.pem --id USER_ID --expiration=1h > token.jwt

        # create kong.sql file
        sudo mkdir /var/snap/edgexfoundry/common/refresh
        sudo chown -R snap_daemon:snap_daemon /var/snap/edgexfoundry/common/refresh
        sudo snap run --shell edgexfoundry.psql
            export PGPASSWORD=`cat /var/snap/edgexfoundry/current/config/postgres/kongpw`
            pg_dump -Ukong kong -f$SNAP_COMMON/refresh/kong.sql
            exit
        cp /var/snap/edgexfoundry/common/refresh/kong.sql ./test-files

2) To run this test, you need to change snapcraft.yaml to epoch:5, rebuild and run this test manually with the modified snap
    cd data/latest
    sudo ./run-all-tests-locally.sh -t manual-test-refresh-core-18-20.sh -s edgexfoundry_2.2.0-dev.13_amd64.snap

'

# get the directory of this script
# snippet from https://stackoverflow.com/a/246128/10102404
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null && pwd )"

# load the latest release utils
# shellcheck source=/dev/null
source "$SCRIPT_DIR/utils.sh"

START_TIME=$(date +"%Y-%m-%d %H:%M:%S")
 
# install EdgeXFoundry 2.0
sudo snap remove --purge edgexfoundry
sudo snap install edgexfoundry --channel=2.0/stable

# 2.0 doesn't contain the pre-refresh hook, so create the file that would have been output
REFRESH_DIR="/var/snap/edgexfoundry/common/refresh"
sudo mkdir $REFRESH_DIR
tar -C $REFRESH_DIR -xzvf $SCRIPT_DIR/test-files/postgres-refresh/kong.tgz
sudo chown -R snap_daemon:snap_daemon /var/snap/edgexfoundry/common/refresh

# Due to confinement issues when running this test, we write the private key to SNAP_DATA
EDGEXFOUNDRY_SNAP_DATA="/var/snap/edgexfoundry/current/checkbox"
mkdir -p $EDGEXFOUNDRY_SNAP_DATA
sudo cp $SCRIPT_DIR/test-files/postgres-refresh/*.pem $EDGEXFOUNDRY_SNAP_DATA

# install the new version, which will then pick up the kong.sql file
if [ -n "$REVISION_TO_TEST" ]; then
    echo "Installing snap from locally cached version"
    snap_install "$REVISION_TO_TEST" "$REVISION_TO_TEST_CHANNEL" "$REVISION_TO_TEST_CONFINEMENT"
else
    echo "Installing snap from channel $DEFAULT_TEST_CHANNEL"
    snap_refresh edgexfoundry "$DEFAULT_TEST_CHANNEL"
fi
 
# confirm that we can log in using the public key 
TOKEN=$(edgexfoundry.secrets-config proxy jwt --algorithm ES256 --private_key $EDGEXFOUNDRY_SNAP_DATA/private.pem --id USER_ID --expiration=1h)

# note: we need to use "edgexfoundry.curl", not "curl" to correctly support TLS 1.2

echo "Verifying self-signed TLS certificate"
code=$(edgexfoundry.curl --insecure --show-error --silent --include \
    --output /dev/null --write-out "%{http_code}" \
    -X GET 'https://localhost:8443/core-data/api/v2/ping?' \
    -H "Authorization: Bearer $TOKEN") 
if [[ $code != 200 ]]; then
    print_error_logs
    >&2 echo "self-signed Kong TLS verification test failed with $code"
    snap_remove
    exit 1
else
    echo "Self-signed TLS verification test succeeded"
fi
  