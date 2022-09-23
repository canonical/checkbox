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
    # use locally cached version of stable and delhi
    case "$channel" in 
        delhi)
            if [ -n "$EDGEX_EDINBURGH_SNAP_FILE" ]; then
                snap_install "$EDGEX_EDINBURGH_SNAP_FILE"
            else
                snap_install edgexfoundry edinburgh
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
    # wait for services to come online
    # NOTE: this may have to be significantly increased on arm64 or low RAM platforms
    # to accomodate time for everything to come online
    sleep 120
    snap_check_ireland_svcs

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

    snap_check_ireland_svcs --notfatal

    # remove the snap to run the next channel upgrade
    snap_remove
done
