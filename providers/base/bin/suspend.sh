#!/bin/bash
# FWTS s3 only support x86_64 and i386 cpu
# ref: https://github.com/ColinIanKing/fwts/blob/master/src/acpi/s3/s3.c#L24
# So we need to seperate two kind of situation (FWTS_S3 supported or not)

architecture=$(uname -m)
if [ "$architecture" = "x86_64" ] || [ "$architecture" = "i386" ]; then
    export LD_LIBRARY_PATH="$LD_LIBRARY_PATH:$SNAP/usr/lib/fwts"
    set -o pipefail
    checkbox-support-fwts_test -f none -s s3 --s3-device-check --s3-device-check-delay="${STRESS_S3_WAIT_DELAY:-45}" --s3-sleep-delay="${STRESS_S3_SLEEP_DELAY:-30}"
else
    rtcwake -v -m mem -s "${STRESS_S3_SLEEP_DELAY:-30}"
fi

