#!/usr/bin/env bash

set -euxo pipefail

#  IMPORTANT: for any test using the dss command:
#
# - Clear PYTHON shell vars to prevent conflicts between dss
#   and checkbox python environments
# - Run from ${HOME} as dss writes logs to its working directory,
#   and as a snap does not have permissions to write to the default
#   working directory for checkbox tests
export -n PYTHONHOME PYTHONPATH PYTHONUSERBASE

check_dss_can_be_initialized() {
    # TODO: we actually seem to initialize dss here; maybe split it out
    dss initialize --kubeconfig="$(sudo microk8s config)"
    echo "Test success: dss initialized."
}

check_dss_namespace_is_deployed() {
    if microk8s.kubectl get ns | grep -q dss; then
        echo "Test success: 'dss' namespace is deployed!"
    else
        >&2 echo "Test failure: no namespace named 'dss' deployed."
        exit 1
    fi
}

check_dss_status_contains() {
    result=$(dss status) # save result to shell var to avoid broken pipe error
    if echo "${result}" | grep -q "${1}"; then
        echo "Test success: 'dss status' shows '$1'."
    else
        >&2 echo "Test failure: 'dss status' does not show '$1'."
        exit 1
    fi
}

check_dss_can_create_notebook() {
    if dss create "${@}"; then
        echo "Test success: successfully created notebook with '$*'."
    else
        >&2 echo "Test failure: failed to create notebook with '$*'."
        exit 1
    fi
}

check_dss_can_remove_notebook() {
    if dss remove "$@"; then
        echo "Test success: successfully removed notebook with '$*'."
    else
        >&2 echo "Test failure: failed to remove notebook with '$*'."
        exit 1
    fi
}

help_function() {
    echo "This script is used for generic tests related to DSS"
    echo "Usage: check_dss.sh <test_case> [args]..."
    echo
    echo "Test cases currently implemented:"
    echo -e "\t<can_be_initialized>: check_dss_can_be_initialized"
    echo -e "\t<namespace_is_deployed>: check_dss_namespace_is_deployed"
    echo -e "\t<mlflow_status_is_ready>: check_mlflow_status_is_ready"
    echo -e "\t<intel_gpu_acceleration_is_enabled>: check_dss_has_intel_gpu_acceleration_enabled"
    echo -e "\t<nvidia_gpu_acceleration_is_enabled>: check_dss_has_nvidia_gpu_acceleration_enabled"
    echo -e "\t<can_create_notebook>: check_dss_can_create_notebook <notebook_name> [args]"
    echo -e "\t<can_remove_notebook>: check_dss_can_remove_notebook <notebook_name>"
}

main() {
    pushd "${HOME}"
    case ${1} in
    can_be_initialized) check_dss_can_be_initialized ;;
    namespace_is_deployed) check_dss_namespace_is_deployed ;;
    mlflow_status_is_ready) check_dss_status_contains "MLflow deployment: Ready" ;;
    intel_gpu_acceleration_is_enabled) check_dss_status_contains "Intel GPU acceleration: Enabled.*" ;;
    nvidia_gpu_acceleration_is_enabled) check_dss_status_contains "NVIDIA GPU acceleration: Enabled.*" ;;
    can_create_notebook) check_dss_can_create_notebook "${@:2}" ;;
    can_remove_notebook) check_dss_can_remove_notebook "${@:2}" ;;
    *) help_function ;;
    esac
    popd
}

main "$@"
