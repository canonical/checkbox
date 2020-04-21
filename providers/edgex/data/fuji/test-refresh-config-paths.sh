#!/bin/bash -e

# get the directory of this script
# snippet from https://stackoverflow.com/a/246128/10102404
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null && pwd )"

# load the utils
# shellcheck source=/dev/null
source "$SCRIPT_DIR/utils.sh"

DEFAULT_TEST_CHANNEL=${DEFAULT_TEST_CHANNEL:-beta}

snap_remove

echo "skipping test until snap with epoch 1 is released to edge"
exit 0

for channel in edge; do 
    # first make sure that the snap installs correctly from the channel
    case "$channel" in 
        delhi)
            echo "installing delhi channel snap"
            if [ -n "$EDGEX_EDINBURGH_SNAP_FILE" ]; then
                snap_install "$EDGEX_EDINBURGH_SNAP_FILE"
            else
                snap_install edgexfoundry edinburgh
            fi
            ;;
        stable)
            echo "installing stable channel snap"
            if [ -n "$EDGEX_STABLE_SNAP_FILE" ]; then
                snap_install "$EDGEX_STABLE_SNAP_FILE"
            else
                snap_install edgexfoundry stable
            fi
            ;;
        *)
            echo "installing $channel channel snap"
            snap_install edgexfoundry "$channel"
            ;;
    esac

    # get the revision number for this channel
    SNAP_REVISION=$(snap run --shell edgexfoundry.consul -c "echo \$SNAP_REVISION")
    
    # wait for services to come online
    # NOTE: this may have to be significantly increased on arm64 or low RAM platforms
    # to accomodate time for everything to come online
    sleep 120

    # now install the snap version we are testing and check again
    if [ -n "$REVISION_TO_TEST" ]; then
        snap_install "$REVISION_TO_TEST" "$REVISION_TO_TEST_CHANNEL" "$REVISION_TO_TEST_CONFINEMENT"
    else
        snap_refresh edgexfoundry "$DEFAULT_TEST_CHANNEL"  
    fi

    # wait for services to come online
    # NOTE: this may have to be significantly increased on arm64 or low RAM platforms
    # to accomodate time for everything to come online
    sleep 120

    echo "checking for files with previous snap revision $SNAP_REVISION"

    # check that all files in $SNAP_DATA don't reference the previous revision
    # except for binary files, cassandra log files, and an errant comment I 
    # put in the vault hcl file which the install hook from previous revisions
    # also ends up putting the path including the old revision number inside
    pushd /var/snap/edgexfoundry/current > /dev/null
    set +e
    notUpgradedFiles=$(grep -R "edgexfoundry/$SNAP_REVISION" | \
        grep -v "Binary file" | \
        grep -v "cassandra/logs" | \
        grep -v "and the location of the files uses reference")
    popd > /dev/null
    if [ -n "$notUpgradedFiles" ]; then
        echo "files not upgraded to use \"current\" symlink in config files:"
        echo "$notUpgradedFiles"
        exit 1
    fi
    set -e

    echo "removing $channel snap"

    # remove the snap to run the next channel upgrade
    snap_remove
done
