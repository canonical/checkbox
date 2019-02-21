#!/bin/bash -e

# get the directory of this script
# snippet from https://stackoverflow.com/a/246128/10102404
if [ ! -z "${BASH_SOURCE}" ]; then
    SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null && pwd )"
else
    SCRIPT_DIR=$PWD
fi

# load the utils
source "$SCRIPT_DIR/utils.sh"

# install the snap to make sure it installs
install_snap edgexfoundry stable 

# wait for services to come online
# NOTE: this may have to be significantly increased on arm64 or low RAM platforms
# to accomodate time for everything to come online
sleep 120

# copy the root certificate to confirm that can be used to authenticate the
# kong server
cp /var/snap/edgexfoundry/current/vault/pki/EdgeXFoundryCA/EdgeXFoundryCA.pem /tmp/EdgeXFoundryCA.pem

# use curl to talk to the kong admin endpoint with the cert
curl --cacert https://localhost:8443/command

# restart the security-services and make sure the same certificate still works
snap restart edgexfoundry.security-services

sleep 120
curl --cacert https://localhost:8443/command


# remove the snap to run the next test
snap_remove
