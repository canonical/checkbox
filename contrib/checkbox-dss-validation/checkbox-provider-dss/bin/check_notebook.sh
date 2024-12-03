#!/usr/bin/env bash

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)

pytorch_can_use_cpu_script="import torch; print(torch.__version__)"
tensorflow_can_use_cpu_script="import tensorflow as tf; print(tf.config.experimental.list_physical_devices())"
pytorch_can_use_xpu_script="$(cat "$SCRIPT_DIR/pytorch_can_use_xpu.py")"
tensorflow_can_use_xpu_script="$(cat "$SCRIPT_DIR/tensorflow_can_use_xpu.py")"
pytorch_can_use_cuda_script="import torch; assert torch.cuda.is_available(), 'CUDA is not available'"
tensorflow_can_use_cuda_script="$(cat "$SCRIPT_DIR/tensorflow_can_use_cuda.py")"

check_notebook_can_run_python_script_in_pod() {
    if microk8s.kubectl -n dss exec "$1" -- python -c "$2"; then
        echo "Test success: in pod $1"
    else
        err_code=$?
        >&2 echo "Test failed: in pod $1 with error code ${err_code}"
        exit $err_code
    fi
}

help_function() {
    echo "This script is used for tests related to running things in notebooks' pods"
    echo "Usage: check_notebook.sh <notebook_name> <test_case> [args]..."
    echo
    echo "Test cases currently implemented:"
    echo -e "\t<can_run_python_script_in_pod>: check_notebook_can_run_python_script_in_pod <pod_name_for_notebook> <script>"
    echo -e "\t\t<pod_name_for_notebook>: determined by grep-ing <notebook_name> for running pods in dss namespace"
    echo -e "\t\t<script>: one of:"
    echo -e "\t\t\t- verifying_pytorch_can_use_cpu"
    echo -e "\t\t\t- verifying_tensorflow_can_use_cpu"
    echo -e "\t\t\t- verifying_pytorch_can_use_xpu"
    echo -e "\t\t\t- verifying_tensorflow_can_use_xpu"
    echo -e "\t\t\t- verifying_pytorch_can_use_cuda"
    echo -e "\t\t\t- verifying_tensorflow_can_use_cuda"
}

main() {
    running_pods=$(microk8s.kubectl get pods -n dss --field-selector=status.phase==Running -o=jsonpath='{.items..metadata.name}')
    pod=$(echo "${running_pods}" | grep -o "${1}\S*")
    echo "Found ${1} pod: ${pod}"

    case ${3} in
    verifying_pytorch_can_use_cpu) script="$pytorch_can_use_cpu_script" ;;
    verifying_tensorflow_can_use_cpu) script="$tensorflow_can_use_cpu_script" ;;
    verifying_pytorch_can_use_xpu) script="$pytorch_can_use_xpu_script" ;;
    verifying_tensorflow_can_use_xpu) script="$tensorflow_can_use_xpu_script" ;;
    verifying_pytorch_can_use_cuda) script="$pytorch_can_use_cuda_script" ;;
    verifying_tensorflow_can_use_cuda) script="$tensorflow_can_use_cuda_script" ;;
    *) help_function ;;
    esac

    case ${2} in
    can_run_python_script_in_pod) check_notebook_can_run_python_script_in_pod "$pod" "$script" ;;
    *) help_function ;;
    esac
}

main "$@"
