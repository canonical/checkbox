#!/bin/bash
# Usage: fastrpc_test.sh <domain>:<unsigned>...
# Run the fastrpc test on the given domains, signed or unsigned.

calculator() {
    cd /home/ubuntu/calculator
    output="$(LD_PRELOAD=./libcalculator.so DSP_LIBRARY_PATH=. ./calculator "${@}" -n 1000)"
    echo "${output}"
    echo "${output}" | grep -q Success
    return "${?}"
}

if [ -x /usr/bin/fastrpc_test ]; then
    cmd=fastrpc_test
else
    cmd=calculator
fi

exit_code=0
while [ "${#}" -ne 0 ]; do
    printf 'Testing: %s -d %s -U %s\n' "${cmd}" "${1%:*}" "${1#*:}"
    "${cmd}" -d "${1%:*}" -U "${1#*:}" || exit_code=1
    shift
done
exit "${exit_code}"
