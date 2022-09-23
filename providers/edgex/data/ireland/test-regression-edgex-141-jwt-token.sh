#!/bin/bash -e

# get the directory of this script
# snippet from https://stackoverflow.com/a/246128/10102404
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null && pwd )"

# load the utils
# shellcheck source=/dev/null
source "$SCRIPT_DIR/utils.sh"

snap_remove

DEFAULT_TEST_CHANNEL=${DEFAULT_TEST_CHANNEL:-beta}

# install the snap to make sure it installs
if [ -n "$REVISION_TO_TEST" ]; then
    snap_install "$REVISION_TO_TEST" "$REVISION_TO_TEST_CHANNEL" "$REVISION_TO_TEST_CONFINEMENT"
else
    snap_install edgexfoundry "$DEFAULT_TEST_CHANNEL"
fi

# wait for services to come online
# NOTE: this may have to be significantly increased on arm64 or low RAM platforms
# to accomodate time for everything to come online
sleep 20

cd /var/snap/edgexfoundry/current

echo "TEST 01: using secrets-config with EC key"

echo "creating ES256 private key"
openssl ecparam -genkey -name prime256v1 -noout -out private.pem

echo "creating public key"
openssl ec -in private.pem -pubout -out public.pem

echo "use Kong admin JWT token"
JWT_FILE=/var/snap/edgexfoundry/current/secrets/security-proxy-setup/kong-admin-jwt
JWT=`sudo cat ${JWT_FILE}`

echo "add Kong user"
edgexfoundry.secrets-config proxy adduser --token-type jwt --user user01 --algorithm ES256 --public_key public.pem --id USER_ID --jwt ${JWT} 

echo "get new Kong JWT"
TOKEN=`edgexfoundry.secrets-config proxy jwt --algorithm ES256 --private_key private.pem --id USER_ID --expiration=1h`
 
echo "try to connect using new Kong JWT"
if curl -k -s X GET https://localhost:8443/core-data/api/v2/ping? -H "Authorization: Bearer $TOKEN" | grep -q "apiVersion"
then
    echo "got expected reply 1"
else
    echo "FAIL authenticating in ping"
    exit 1
fi

echo "TEST 02: using secrets-config with RSA key"

echo "creating RS256 private key"
openssl genrsa -out private-rsa.pem 2048

echo "creating public key"
openssl rsa -in private-rsa.pem -pubout -out public-rsa.pem

echo "use Kong admin JWT token"
JWT_FILE=/var/snap/edgexfoundry/current/secrets/security-proxy-setup/kong-admin-jwt
JWT=`sudo cat ${JWT_FILE}`

echo "add Kong user"
edgexfoundry.secrets-config proxy adduser --token-type jwt --user userrsa --algorithm RS256 --public_key public-rsa.pem --id RSA_USER_ID --jwt ${JWT} 

echo "get new Kong JWT"
RSA_TOKEN=`edgexfoundry.secrets-config proxy jwt --algorithm RS256 --private_key private-rsa.pem --id RSA_USER_ID --expiration=1h`

echo "try to connect using new Kong JWT"
if curl -k -s X GET https://localhost:8443/core-data/api/v2/ping? -H "Authorization: Bearer $RSA_TOKEN" | grep -q "apiVersion"
then
    echo "got expected reply 1"
else
    echo "FAIL authenticating in ping"
    exit 1
fi

echo "TEST 03: using snap set/get"

echo "creating private key"
openssl ecparam -genkey -name prime256v1 -noout -out private2.pem

echo "creating public key"
openssl ec -in private2.pem -pubout -out public2.pem

#set user=username,user id,algorithm (ES256 or RS256)
echo "add Kong user using configure hook"
sudo snap set edgexfoundry env.security-proxy.user=user02,USER_ID_2,ES256

#set public-key to the contents of a PEM-encoded public key file
echo "set public key for new Kong user using configure hook"
sudo snap set edgexfoundry env.security-proxy.public-key="$(cat public2.pem)"

TOKEN=`edgexfoundry.secrets-config proxy jwt --algorithm ES256 --private_key private2.pem --id USER_ID_2 --expiration=1h`

echo "try to connect using new Kong JWT"
if curl -k -s X GET https://localhost:8443/core-data/api/v2/ping? -H "Authorization: Bearer $TOKEN" | grep -q "apiVersion"
then
    echo "got expected reply 2"
else
    echo "FAIL authenticating in ping"
    exit 1
fi

echo "try to connect using new Kong JWT"
if curl -k -s X GET https://localhost:8443/core-data/api/v2/ping | grep -q "apiVersion"
then
    echo "FAIL authenticating in ping"
    exit 1
else
    echo "got expected reply 3"
fi
 

# remove the snap to run again
snap_remove
