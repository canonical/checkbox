#!/bin/bash
# Usage: fastrpc_test.sh <domain>:<unsigned>...
# Run the fastrpc test on the given domains, signed or unsigned.

calculator() {
    cd /home/ubuntu/calculator || return 1
    output="$(LD_PRELOAD=./libcalculator.so DSP_LIBRARY_PATH=. ./calculator "${@}" -n 1000)"
    echo "${output}"
    echo "${output}" | grep -q Success
    return "${?}"
}

if [ -x /usr/bin/fastrpc_test ]; then
    # On resolute, the fastrpc_test binary is available in fastrpc-test deb.
    cmd_name=fastrpc_test
elif command -v fastrpc_test.calculator > /dev/null 2>&1; then
    # Ubuntu Core ships the calculator test in fastrpc_test snap.
    cmd_name=fastrpc_test.calculator
else
    # On noble, calculator bin is used directly.
    cmd_name=calculator
fi

exit_code=0
while [ "${#}" -ne 0 ]; do
    printf 'Testing: %s -d %s -U %s\n' "${cmd_name}" "${1%:*}" "${1#*:}"
    "${cmd_name}" -d "${1%:*}" -U "${1#*:}" || exit_code=1
    shift
done
exit "${exit_code}"
