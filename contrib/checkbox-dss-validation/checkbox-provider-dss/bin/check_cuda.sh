#!/usr/bin/env bash

set -euxo pipefail

check_nvidia_gpu_validations_succeed() {
    SLEEP_SECS=5
    echo "[INFO]: sleeping for ${SLEEP_SECS} seconds before checking if GPU validations were successful."
    sleep ${SLEEP_SECS}
    result=$(microk8s.kubectl logs -n gpu-operator-resources -lapp=nvidia-operator-validator -c nvidia-operator-validator)
    if [ "${result}" = "all validations are successful" ]; then
        echo "Test success: NVIDIA GPU validations were successful!"
    else
        >&2 echo "Test failure: NVIDIA GPU validations were not successful, got ${result}"
        exit 1
    fi
}

help_function() {
    echo "This script is used for tests related to CUDA"
    echo "Usage: check_dss.sh <test_case>"
    echo
    echo "Test cases currently implemented:"
    echo -e "\t<gpu_validations_succeed>: check_nvidia_gpu_validations_succeed"
}

main() {
    case ${1} in
    gpu_validations_succeed) check_nvidia_gpu_validations_succeed ;;
    *) help_function ;;
    esac
}

main "$@"
