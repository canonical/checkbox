#!/usr/bin/env bash

set -euxo pipefail

DSS_REPO_CLONE_PATH="$HOME/data-science-stack"
DSS_REPO_REV="main"

_ensure_microk8s_config_is_in_place() {
    sudo microk8s.kubectl config view --raw | sudo tee "${SNAP_REAL_HOME}/.kube/config" >/dev/null
}

_ensure_dss_repo_is_checked_out() {
    if [ ! -d "$DSS_REPO_CLONE_PATH" ]; then
        git clone https://github.com/canonical/data-science-stack.git "$DSS_REPO_CLONE_PATH"
    fi
    git -C "$DSS_REPO_CLONE_PATH" checkout "$DSS_REPO_REV"
    echo "Current git branch for DSS repo: $(git branch --show-current)"
    echo "Latest commit:"
    git -C "$DSS_REPO_CLONE_PATH" log --name-status HEAD^..HEAD
}
_ensure_dss_python_env_is_setup() {
    pushd "$DSS_REPO_CLONE_PATH"
    if [ ! -d ".venv" ]; then
        python3 -m venv .venv
    fi
    .venv/bin/pip install tox
    popd
}

check_dss_integration_tests_pass() {
    pushd "$DSS_REPO_CLONE_PATH"
    echo "starting DSS integration tests: $1"
    .venv/bin/tox -e "$1" -- -vv -s
    echo "Tests passed: DSS integration tests '$1'"
    popd
}

help_function() {
    echo "This script is used for running integration tests from DSS"
    echo "Usage: check_dss_integration_tests <test_case>"
    echo
    echo "Test cases currently implemented:"
    echo -e "\t<pass_on_cpu>"
    echo -e "\t<pass_on_nvidia_gpu>"
}

main() {
    _ensure_microk8s_config_is_in_place
    _ensure_dss_repo_is_checked_out
    _ensure_dss_python_env_is_setup

    case ${1} in
    pass_on_cpu) check_dss_integration_tests_pass "integration" ;;
    pass_on_nvidia_gpu)  check_dss_integration_tests_pass "integration-gpu" ;;
    *) help_function ;;
    esac
}

main "$@"
