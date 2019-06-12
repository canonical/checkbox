#!/bin/bash -e

# get the directory of this script
# snippet from https://stackoverflow.com/a/246128/10102404
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null && pwd )"

# load the utils
# shellcheck source=/dev/null
source "$SCRIPT_DIR/utils.sh"

snap_remove

# install the snap to make sure it installs
if [ -n "$REVISION_TO_TEST" ]; then
    snap_install "$REVISION_TO_TEST" "$REVISION_TO_TEST_CHANNEL" "$REVISION_TO_TEST_CONFINEMENT"
else
    snap_install edgexfoundry beta 
fi

# wait for services to come online
# NOTE: this may have to be significantly increased on arm64 or low RAM platforms
# to accomodate time for everything to come online
sleep 240

# copy the root certificate to confirm that can be used to authenticate the
# kong server
cp /var/snap/edgexfoundry/current/vault/pki/EdgeXFoundryCA/EdgeXFoundryCA.pem /tmp/EdgeXFoundryCA.pem

# make the CA world-readable
chmod +r /tmp/EdgeXFoundryCA.pem

# use curl to talk to the kong admin endpoint with the cert
edgexfoundry.curl --cacert /tmp/EdgeXFoundryCA.pem https://localhost:8443/command > /dev/null

# restart all of EdgeX (including the security-services) and make sure the 
# same certificate still works
snap restart edgexfoundry > /dev/null

sleep 240
edgexfoundry.curl --cacert /tmp/EdgeXFoundryCA.pem https://localhost:8443/command > /dev/null

# remove the snap to run the next test
snap_remove
