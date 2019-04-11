#!/bin/bash -e

# get the directory of this script
# snippet from https://stackoverflow.com/a/246128/10102404
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null && pwd )"

# load the utils
# shellcheck source=/dev/null
source "$SCRIPT_DIR/utils.sh"

# remove the snap if it's already installed
snap_remove

for channel in delhi stable; do 
    # first make sure that the snap installs correctly from the channel
    case "$channel" in 
        delhi)
            if [ -n "$EDGEX_DELHI_SNAP_FILE" ]; then
                snap_install "$EDGEX_DELHI_SNAP_FILE"
            else
                snap_install edgexfoundry delhi
            fi
            ;;
        stable)
            if [ -n "$EDGEX_STABLE_SNAP_FILE" ]; then
                snap_install "$EDGEX_STABLE_SNAP_FILE"
            else
                snap_install edgexfoundry stable
            fi
            ;;
        *)
            snap_install edgexfoundry "$channel"
            ;;
    esac

    # get the revision number for this channel
    SNAP_REVISION=$(snap run --shell edgexfoundry -c "echo \$SNAP_REVISION")

    # wait for services to come online
    # NOTE: this may have to be significantly increased on arm64 or low RAM platforms
    # to accomodate time for everything to come online
    sleep 120

    # now install the snap version we are testing and check again
    if [ -n "$REVISION_TO_TEST" ]; then
        snap_install "$REVISION_TO_TEST" "$REVISION_TO_TEST_CHANNEL" "$REVISION_TO_TEST_CONFINEMENT"
    else
        snap_install edgexfoundry beta 
    fi

    # wait for services to come online
    # NOTE: this may have to be significantly increased on arm64 or low RAM platforms
    # to accomodate time for everything to come online
    sleep 120

    # check that all files in $SNAP_DATA don't reference the previous revision
    # except for binary files, cassandra log files, and an errant comment I 
    # put in the vault hcl file which the install hook from previous revisions
    # also ends up putting the path including the old revision number inside
    # note we have to run the initial grep as sudo so that it can access all 
    # of the files, some of which are 0600 root owned
    cd /var/snap/edgexfoundry/current
    notUpgradedFiles=$(sudo grep -R "edgexfoundry/$SNAP_REVISION" | \
        grep -v "Binary file" | \
        grep -v "cassandra/logs | \
        grep -v "and the location of the files uses reference"")
    if [ -z "$notUpgradedFiles" ]; then
        echo "files not upgraded to use \"current\" symlink in config files:"
        echo "$notUpgradedFiles"
        exit 1
    fi

    # also check that the vault-config.hcl file exists - it used to be called
    # vault-config.json but it's not really a json file so we renamed it to an
    # hcl file
    if [ ! -f /var/snap/edgexfoundry/current/config/security-secret-store/vault-config.hcl ]; then
        echo "vault-config.hcl file is missing"
        exit 1
    fi

    # remove the snap to run the next channel upgrade
    snap_remove
done
