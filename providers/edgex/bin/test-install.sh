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

# remove the snap to run again
snap_remove
