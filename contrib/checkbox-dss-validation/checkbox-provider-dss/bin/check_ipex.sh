#!/usr/bin/env bash

set -euxo pipefail

check_ipex_can_be_imported() {
    echo "Starting ipex import test"
    script="import intel_extension_for_pytorch as ipex; import torch; import jupyter"
    if microk8s.kubectl -n dss exec "$1" -- python3 -c "$script"; then
        echo "PASS: Found module"
        exit 0
    else
        >&2 echo "FAIL: Did not find IPEX python module"
        exit 1
    fi
}

check_pytorch_can_use_xpu() {
    echo "Starting ipex GPU check test"
    script="$(cat pytorch_can_use_xpu.py)"
    gpu_grep_out=$(microk8s.kubectl -n dss exec "$1" -- python3 -c "$script" | grep "dev_type=.gpu" 2>&1)
    if [[ -z ${gpu_grep_out} ]]; then
        >&2 echo "FAIL: No GPU found"
        exit 1
    else
        echo "PASS: GPU found"
        exit 0
    fi
}

help_function() {
    echo "This script is used for tests related to IPEX"
    echo "Usage: check_dss.sh <test_case>"
    echo
    echo "Test cases currently implemented:"
    echo -e "\t<can_be_imported>: check_itex_can_be_imported"
    echo -e "\t<pytorch_can_use_xpu>: check_pytorch_can_use_xpu"
}

main() {
    pod=$(microk8s.kubectl get pods -n dss --field-selector=status.phase==Running -o=jsonpath='{.items..metadata.name}' | grep -o 'ipex-2120-notebook.*')
    echo "Found PyTorch pod: ${pod}"
    case ${1} in
    can_be_imported) check_ipex_can_be_imported pod ;;
    pytorch_can_use_xpu) check_pytorch_can_use_xpu pod ;;
    *) help_function ;;
    esac
}

main "$@"
