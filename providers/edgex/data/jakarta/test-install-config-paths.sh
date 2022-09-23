#!/bin/bash -e

# get the directory of this script
# snippet from https://stackoverflow.com/a/246128/10102404
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null && pwd )"

# load the jakarta release utils
# shellcheck source=/dev/null
source "$SCRIPT_DIR/utils.sh"

START_TIME=$(date +"%Y-%m-%d %H:%M:%S")

snap_remove

# now install the snap version we are testing and check again
if [ -n "$REVISION_TO_TEST" ]; then
    snap_install "$REVISION_TO_TEST" "$REVISION_TO_TEST_CHANNEL" "$REVISION_TO_TEST_CONFINEMENT"
else
    snap_install edgexfoundry "$DEFAULT_TEST_CHANNEL"  
fi

# get the revision number for this channel
SNAP_REVISION=$(snap run --shell edgexfoundry.consul -c "echo \$SNAP_REVISION")

# wait for services to come online
snap_wait_all_services_online

echo "checking for files with snap revision $SNAP_REVISION"

# check that all files in $SNAP_DATA don't reference the previous revision
# except for binary files and an errant comment I put in the vault hcl file 
# which the install hook from previous revisions also ends up putting the path
# including the old revision number inside
cd /var/snap/edgexfoundry/current
set +e
notUpgradedFiles=$(grep -R "edgexfoundry/$SNAP_REVISION" | \
    grep -v "Binary file" | \
    grep -v "postmaster" | \
    grep -v "lua" | \
    grep -v "and the location of the files uses reference")
if [ -n "$notUpgradedFiles" ]; then
    print_error_logs
    echo "files not upgraded to use \"current\" symlink in config files:"
    echo "$notUpgradedFiles"
    exit 1
fi
set -e

snap_remove

