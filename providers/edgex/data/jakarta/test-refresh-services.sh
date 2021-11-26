#!/bin/bash -e

# get the directory of this script
# snippet from https://stackoverflow.com/a/246128/10102404
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null && pwd )"

# load the jakarta release utils
# shellcheck source=/dev/null
source "$SCRIPT_DIR/utils.sh"

DEFAULT_TEST_CHANNEL=${DEFAULT_TEST_CHANNEL:-beta}

snap_remove

for channel in edge; do 
    # first make sure that the snap installs correctly from the channel
    # use locally cached version of ireland and jakarta
    case "$channel" in 
        jakarta)
            echo "installing jakarta channel snap"
            if [ -n "$EDGEX_JAKARTA_SNAP_FILE" ]; then
                snap_install "$EDGEX_JAKARTA_SNAP_FILE"
            else
                snap_install edgexfoundry jakarta
            fi
            ;;
        ireland)
            echo "installing ireland channel snap"
            if [ -n "$EDGEX_IRELAND_SNAP_FILE" ]; then
                snap_install "$EDGEX_IRELAND_SNAP_FILE"
            else
                snap_install edgexfoundry 2.0
            fi
            ;;
        *)
            echo "installing $channel channel snap"
            snap_install edgexfoundry "$channel"
            ;;
    esac
    # wait for services to come online
    snap_wait_all_services_online

    snap_check_svcs

    # now install the snap version we are testing and check again
    if [ -n "$REVISION_TO_TEST" ]; then
        snap_install "$REVISION_TO_TEST" "$REVISION_TO_TEST_CHANNEL" "$REVISION_TO_TEST_CONFINEMENT"
    else
        snap_refresh edgexfoundry "$DEFAULT_TEST_CHANNEL"  
    fi
    # wait for services to come online
    snap_wait_all_services_online

    snap_check_svcs

    # remove the snap to run the next channel upgrade
    snap_remove
done

