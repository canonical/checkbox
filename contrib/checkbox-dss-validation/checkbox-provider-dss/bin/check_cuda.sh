#!/usr/bin/env bash

set -euxo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)

check_host_has_nvidia_gpus() {
    result="$(lspci | grep -ci 'nvidia')"
    if [[ "$result" -ge 1 ]]; then
        echo "Test success; NVIDIA GPU available on host: count = ${result}"
    else
        >&2 echo "Test failed: 'lspci' does not report any NVIDIA GPUs"
        exit 1
    fi
}

check_nvidia_gpu_addon_can_be_enabled() {
    # TODO: enable changing GPU_OPERATOR_VERSION
    GPU_OPERATOR_VERSION=24.6.2
    echo "[INFO]: enabling the NVIDIA GPU addon"
    sudo microk8s enable gpu --driver=operator --version="$GPU_OPERATOR_VERSION"
    SLEEP_SECS=15
    echo "[INFO]: sleeping for ${SLEEP_SECS} seconds before checking rollout status."
    sleep ${SLEEP_SECS}
    microk8s.kubectl -n gpu-operator-resources rollout status ds/nvidia-device-plugin-daemonset
    echo "Test success: NVIDIA GPU addon enabled."
}


check_nvidia_gpu_validations_succeed() {
    SLEEP_SECS=60
    echo "[INFO]: sleeping for ${SLEEP_SECS} seconds before checking GPU validations were successful."
    sleep ${SLEEP_SECS}
    result=$(microk8s.kubectl logs -n gpu-operator-resources -lapp=nvidia-operator-validator -c nvidia-operator-validator)
    if [ "${result}" = "all validations are successful" ]; then
        echo "Test success: NVIDIA GPU validations were successful!"
    else
        SLEEP_SECS=60
        echo "[INFO]: sleeping for ${SLEEP_SECS} seconds before checking GPU validations again."
        sleep ${SLEEP_SECS}
        result=$(microk8s.kubectl logs -n gpu-operator-resources -lapp=nvidia-operator-validator -c nvidia-operator-validator)
        if [ "${result}" = "all validations are successful" ]; then
            echo "Test success: NVIDIA GPU validations were successful!"
        else
            >&2 echo "Test failure: NVIDIA GPU validations were not successful, got ${result}"
            exit 1
        fi
    fi
}

check_pytorch_can_use_cuda() {
    echo "Starting PyTorch CUDA test"
    pod=$(microk8s.kubectl get pods -n dss --field-selector=status.phase==Running -o=jsonpath='{.items..metadata.name}' | grep -o 'pytorch-cuda\S*')
    echo "Found PyTorch CUDA pod: ${pod}"
    script="import torch; assert torch.cuda.is_available(), 'CUDA is not available'"
    if microk8s.kubectl -n dss exec "$pod" -- python3 -c "$script"; then
        echo "PASS: PyTorch can use CUDA"
        exit 0
    else
        >&2 echo "FAIL: PyTorch can't use CUDA"
        exit 1
    fi
}

check_tensorflow_can_use_cuda() {
    echo "Starting Tensorflow CUDA test"
    pod=$(microk8s.kubectl get pods -n dss --field-selector=status.phase==Running -o=jsonpath='{.items..metadata.name}' | grep -o 'tensorflow-cuda\S*')
    echo "Found Tensorflow CUDA pod: ${pod}"
    script="$(cat "$SCRIPT_DIR/tensorflow_can_use_cuda.py")"
    if microk8s.kubectl -n dss exec "$pod" -- python3 -c "$script"; then
        echo "PASS: Tensorflow can use CUDA"
        exit 0
    else
        >&2 echo "FAIL: Tensorflow can't use CUDA"
        exit 1
    fi
}

help_function() {
    echo "This script is used for tests related to CUDA"
    echo "Usage: check_dss.sh <test_case>"
    echo
    echo "Test cases currently implemented:"
    echo -e "\t<gpu_addon_can_be_enabled>: check_nvidia_gpu_addon_can_be_enabled"
    echo -e "\t<gpu_validations_succeed>: check_nvidia_gpu_validations_succeed"
    echo -e "\t<pytorch_can_use_cuda>: check_pytorch_can_use_cuda"
    echo -e "\t<tensorflow_can_use_cuda>: check_tensorflow_can_use_cuda"
}

main() {
    case ${1} in
    host_has_nvidia_gpus) check_host_has_nvidia_gpus ;;
    gpu_addon_can_be_enabled) check_nvidia_gpu_addon_can_be_enabled ;;
    gpu_validations_succeed) check_nvidia_gpu_validations_succeed ;;
    pytorch_can_use_cuda) check_pytorch_can_use_cuda ;;
    tensorflow_can_use_cuda) check_tensorflow_can_use_cuda ;;
    *) help_function ;;
    esac
}

main "$@"
