#!/bin/bash

TIMEOUT=3
TEMPFILE=$(mktemp)

# shellcheck disable=SC2064
trap "rm $TEMPFILE" EXIT

# shellcheck disable=SC2034
for i in $(seq $TIMEOUT); do
    #launch background writer
    dd if=/dev/urandom of="$TEMPFILE" bs=1024 oflag=direct &
    WRITE_PID=$!
    echo "Writing..."
    sleep 1
    kill $WRITE_PID
    sync
    echo "Reading..."
    dd if="$TEMPFILE" of=/dev/null bs=1024 iflag=direct
done

echo "OK, now exiting"
