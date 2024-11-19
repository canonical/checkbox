#!/usr/bin/env bash

set -euxo pipefail

check_pytorch_can_use_cpu() {
    echo "Starting PyTorch CPU test"
    pod=$(microk8s.kubectl get pods -n dss --field-selector=status.phase==Running -o=jsonpath='{.items..metadata.name}' | grep -o 'pytorch-cpu\S*')
    echo "Found PyTorch CPU pod: ${pod}"
    script="import torch; print(torch.__version__)"
    if microk8s.kubectl -n dss exec "$pod" -- python3 -c "$script"; then
        echo "PASS: PyTorch can use CPU"
        exit 0
    else
        >&2 echo "FAIL: PyTorch can't use CPU"
        exit 1
    fi
}

check_tensorflow_can_use_cpu() {
    echo "Starting Tensorflow CPU test"
    pod=$(microk8s.kubectl get pods -n dss --field-selector=status.phase==Running -o=jsonpath='{.items..metadata.name}' | grep -o 'tensorflow-cpu\S*')
    echo "Found Tensorflow CPU pod: ${pod}"
    script="import tensorflow as tf; print(tf.config.experimental.list_physical_devices())"
    if microk8s.kubectl -n dss exec "$pod" -- python3 -c "$script"; then
        echo "PASS: Tensorflow can use CPU"
        exit 0
    else
        >&2 echo "FAIL: Tensorflow can't use CPU"
        exit 1
    fi
}

help_function() {
    echo "This script is used for tests related to CUDA"
    echo "Usage: check_dss.sh <test_case>"
    echo
    echo "Test cases currently implemented:"
    echo -e "\t<pytorch_can_use_cpu>: check_pytorch_can_use_cpu"
    echo -e "\t<tensorflow_can_use_cpu>: check_tensorflow_can_use_cpu"
}

main() {
    case ${1} in
    pytorch_can_use_cpu) check_pytorch_can_use_cpu ;;
    tensorflow_can_use_cpu) check_tensorflow_can_use_cpu ;;
    *) help_function ;;
    esac
}

main "$@"
