#!/bin/bash

TEMP_DIR='/tmp/optical-test'
ISO_NAME='optical-test.iso'
SAMPLE_FILE_PATH='/usr/share/example-content/'
SAMPLE_FILE='Ubuntu_Free_Culture_Showcase'
MD5SUM_FILE='optical_test.md5'
START_DIR=$PWD

create_working_dirs(){
    # First, create the temp dir and cd there
    echo "Creating Temp directory and moving there ..."
    mkdir -p $TEMP_DIR || return 1
    cd $TEMP_DIR || return 1
    echo "Now working in $PWD ..."
    }

get_sample_data(){
    # Get our sample files
    echo "Getting sample files from $SAMPLE_FILE_PATH ..."
    cp -a $SAMPLE_FILE_PATH/$SAMPLE_FILE $TEMP_DIR
    return $?
}

generate_md5(){
    # Generate the md5sum
    echo "Generating md5sums of sample files ..."
    CUR_DIR=$PWD
    cd $SAMPLE_FILE || return 1
    md5sum -- * > $TEMP_DIR/$MD5SUM_FILE
    # Check the sums for paranoia sake
    check_md5 $TEMP_DIR/$MD5SUM_FILE
    rt=$?
    cd "$CUR_DIR" || exit 1
    return $rt
}

check_md5(){
    echo "Checking md5sums ..."
    md5sum -c "$1"
    return $?
}

generate_iso(){
    # Generate ISO image
    echo "Creating ISO Image ..."
    genisoimage -input-charset UTF-8 -r -J -o $ISO_NAME $SAMPLE_FILE
    return $?
}

burn_iso(){
    # Burn the ISO with the appropriate tool
    echo "Sleeping 10 seconds in case drive is not yet ready ..."
    sleep 10
    echo "Beginning image burn ..."
    if [ "$OPTICAL_TYPE" == 'cd' ]
    then
        wodim -eject dev="$OPTICAL_DRIVE" $ISO_NAME
    elif [ "$OPTICAL_TYPE" == 'dvd' ] || [ "$OPTICAL_TYPE" == 'bd' ]
    then
        growisofs -dvd-compat -Z "$OPTICAL_DRIVE=$ISO_NAME"
    else
        echo "Invalid type specified '$OPTICAL_TYPE'"
        exit 1
    fi
    rt=$?
    return $rt
}

check_disk(){
    TIMEOUT=300
    SLEEP_COUNT=0
    INTERVAL=3

    # Give the tester up to 5 minutes to reload the newly created CD/DVD
    echo "Waiting up to 5 minutes for drive to be mounted ..."
    while true; do
        sleep $INTERVAL
        SLEEP_COUNT=$((SLEEP_COUNT + INTERVAL))

        mount "$OPTICAL_DRIVE" 2>&1 | grep -E -q "already mounted"
        rt=$?
        if [ $rt -eq 0 ]; then
            echo "Drive appears to be mounted now"
            break
        fi

        # If they exceed the timeout limit, make a best effort to load the tray
        # in the next steps
        if [ $SLEEP_COUNT -ge $TIMEOUT ]; then
            echo "WARNING: TIMEOUT Exceeded and no mount detected!"
            break
        fi
    done


    echo "Deleting original data files ..."
    rm -rf $SAMPLE_FILE
    if mount | grep -q "$OPTICAL_DRIVE"; then
        MOUNT_PT=$(mount | grep "$OPTICAL_DRIVE" | awk '{print $3}')
        echo "Disk is mounted to $MOUNT_PT"
    else
        echo "Attempting best effort to mount $OPTICAL_DRIVE on my own"
        MOUNT_PT=$TEMP_DIR/mnt
        echo "Creating temp mount point: $MOUNT_PT ..."
        mkdir $MOUNT_PT
        echo "Mounting disk to mount point ..."
        mount "$OPTICAL_DRIVE" $MOUNT_PT
        rt=$?
        if [ $rt -ne 0 ]; then
            echo "ERROR: Unable to re-mount $OPTICAL_DRIVE!" >&2
            return 1
        fi
    fi
    echo "Copying files from ISO ..."
    cp "$MOUNT_PT"/* $TEMP_DIR
    check_md5 $MD5SUM_FILE
    return $?
}

cleanup(){
    echo "Moving back to original location"
    cd "$START_DIR" || exit 1
    echo "Now residing in $PWD"
    echo "Cleaning up ..."
    umount "$MOUNT_PT"
    rm -fr $TEMP_DIR
    echo "Ejecting spent media ..."
    eject "$OPTICAL_DRIVE"
}

failed(){
    echo "$1"
    echo "Attempting to clean up ..."
    cleanup
    exit 1
}

if [ -e "$1" ]; then
    OPTICAL_DRIVE=$(readlink -f "$1")
else
    OPTICAL_DRIVE='/dev/sr0'
fi

if [ -n "$2" ]; then
    OPTICAL_TYPE=$2
else
    OPTICAL_TYPE='cd'
fi

create_working_dirs || failed "Failed to create working directories"
get_sample_data || failed "Failed to copy sample data"
generate_md5 || failed "Failed to generate initial md5"
generate_iso || failed "Failed to create ISO image"
burn_iso || failed "Failed to burn ISO image"
check_disk || failed "Failed to verify files on optical disk"
cleanup || failed "Failed to clean up"
exit 0
