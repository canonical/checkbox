#!/usr/bin/env bash

set -euxo pipefail

check_itex_can_be_imported() {
    echo "Starting itex import test"
    script="import intel_extension_for_tensorflow as itex; import tensorflow; import jupyter"
    if microk8s.kubectl -n dss exec "$1" -- python3 -c "$script"; then
        echo "PASS: Found module"
        exit 0
    else
        >&2 echo "FAIL: Did not find ITEX python module"
        exit 1
    fi
}

check_tensorflow_can_use_xpu() {
    echo "Starting itex GPU check test"
    script="$(cat tensorflow_can_use_xpu.py)"
    if microk8s.kubectl -n dss exec "$1" -- python3 -c "$script"; then
        echo "PASS: XPU found"
        exit 0
    else
        >&2 echo "FAIL: No XPU found"
        exit 1
    fi
}

help_function() {
    echo "This script is used for tests related to ITEX"
    echo "Usage: check_dss.sh <test_case>"
    echo
    echo "Test cases currently implemented:"
    echo -e "\t<can_be_imported>: check_itex_can_be_imported"
    echo -e "\t<tensorflow_can_use_xpu>: check_tensorflow_can_use_xpu"
}

main() {
    pod=$(microk8s.kubectl get pods -n dss --field-selector=status.phase==Running -o=jsonpath='{.items..metadata.name}' | grep -o 'itex-215-notebook\S*')
    echo "Found Tensorflow pod: ${pod}"
    case ${1} in
    can_be_imported) check_itex_can_be_imported "$pod" ;;
    tensorflow_can_use_xpu) check_tensorflow_can_use_xpu "$pod" ;;
    *) help_function ;;
    esac
}

main "$@"
