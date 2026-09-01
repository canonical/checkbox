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
    use_fastrpc_test=true
    cmd_name=fastrpc_test
else
    use_fastrpc_test=false
    cmd_name=calculator
fi

exit_code=0
while [ "${#}" -ne 0 ]; do
    printf 'Testing: %s -d %s -U %s\n' "${cmd_name}" "${1%:*}" "${1#*:}"
    if "${use_fastrpc_test}"; then
        fastrpc_test -d "${1%:*}" -U "${1#*:}" || exit_code=1
    else
        calculator -d "${1%:*}" -U "${1#*:}" || exit_code=1
    fi
    shift
done
exit "${exit_code}"
