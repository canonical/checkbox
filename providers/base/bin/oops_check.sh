#!/usr/bin/env bash

retcode=0

## check for Oopses
grep -e 'kernel: \[\s*[0-9]\{2,\}\.[0-9]\{2,\}\] [Oo]ops:' /var/log/syslog
if [ $? -eq 0 ]; then
    retcode=1
fi

exit $retcode

