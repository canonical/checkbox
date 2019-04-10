#!/bin/bash -e

# get the directory of this script
# snippet from https://stackoverflow.com/a/246128/10102404
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null && pwd )"

# load the utils
# shellcheck source=/dev/null
source "$SCRIPT_DIR/utils.sh"

# install the snap to make sure it installs
snap_install edgexfoundry beta 

# wait for services to come online
# NOTE: this may have to be significantly increased on arm64 or low RAM platforms
# to accomodate time for everything to come online
sleep 120

# check services by status

# enabled services
for svc in core-command core-data core-metadata security-services mongod mongo-worker core-config-seed consul; do 
    # make sure it's enabled
    if [ "enabled" != "$(snap services edgexfoundry.$svc | grep $svc | awk '{print $2}')" ]; then
        echo "service $svc isn't enabled but should be"
        exit 1
    fi
done

# active services
# same as enabled, but without core-config-seed and without mongo-worker as 
# those are both oneshot daemons
for svc in core-command core-data core-metadata security-services mongod consul ; do 
    # make sure it's enabled
    if [ "active" != "$(snap services edgexfoundry.$svc | grep $svc | awk '{print $3}')" ]; then
        echo "service $svc isn't enabled but should be"
        exit 1
    fi
done

# disabled services
for svc in export-distro export-client support-notifications support-scheduler support-rulesengine support-logging device-virtual device-modbus device-mqtt device-random; do 
    # make sure it's enabled
    if [ "disabled" != "$(snap services edgexfoundry.$svc | grep $svc | awk '{print $2}')" ]; then
        echo "service $svc isn't enabled but should be"
        exit 1
    fi
done


# inactive services
# all the disabled services + core-config-seed + mongo-worker
for svc in export-distro export-client support-notifications support-scheduler support-rulesengine support-logging device-virtual device-modbus device-mqtt device-random core-config-seed; do 
    # make sure it's enabled
    if [ "inactive" != "$(snap services edgexfoundry.$svc | grep $svc | awk '{print $3}')" ]; then
        echo "service $svc is active but shouldn't be"
        exit 1
    fi
done

# remove the snap to run the next test
snap_remove
