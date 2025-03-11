#!/usr/bin/env bash

set -euxo pipefail

# IMPORTANT NOTE: this is the sharedDevNum we pass into the gpu_plugin.yaml during installation
SLOTS_PER_GPU=10

check_at_least_one_intel_gpu_is_available() {
    # IMPORTANT NOTE: this test also counts NVIDIA GPUs once their plugin is enabled.
    #   The inaccuracy in gpu.intel.com label's value and not controlled by us
    result=$(microk8s.kubectl get node -o json | jq '.items[0].metadata.labels | with_entries(select(.key|match("gpu.intel.com/device-id.*.count";"i")))[] | tonumber' | awk '{cnt+=$1} END{print cnt}')
    if [ "${result}" -ge 1 ]; then
        echo "Test success: Found ${result} GPUs on system."
    else
        >&2 echo "Test failure: expected at least 1 GPU but got ${result}"
        exit 1
    fi
}

check_capacity_slots_for_intel_gpus_match() {
    result=$(microk8s.kubectl get node -o jsonpath='{.items[0].status.capacity.gpu\.intel\.com/i915}')
    if [ "${result}" -ge "${SLOTS_PER_GPU}" ]; then
        echo "Test success: Found ${result} GPU capacity slots on k8s node."
    else
        >&2 echo "Test failure: expected more than ${SLOTS_PER_GPU} GPU capacity slots but got ${result}"
        exit 1
    fi
}

check_allocatable_slots_for_intel_gpus_match() {
    result=$(microk8s.kubectl get node -o jsonpath='{.items[0].status.allocatable.gpu\.intel\.com/i915}')
    if [ "${result}" -ge "${SLOTS_PER_GPU}" ]; then
        echo "Test success: Found ${result} GPU allocatable slots on k8s node."
    else
        >&2 echo "Test failure: expected ${SLOTS_PER_GPU} GPU allocatable slots but got ${result}"
        exit 1
    fi
}

help_function() {
    echo "This script is used for tests related to Intel GPUs"
    echo "Usage: check.sh <test_case>"
    echo
    echo "Test cases currently implemented:"
    echo -e "\t<at_least_one_gpu_is_available>: check_at_least_one_intel_gpu_is_available"
    echo -e "\t<capacity_slots_for_gpus_match>: check_capacity_slots_for_intel_gpus_match"
    echo -e "\t<allocatable_slots_for_gpus_match>: check_allocatable_slots_for_intel_gpus_match"
}

main() {
    case ${1} in
    at_least_one_gpu_is_available) check_at_least_one_intel_gpu_is_available ;;
    capacity_slots_for_gpus_match) check_capacity_slots_for_intel_gpus_match ;;
    allocatable_slots_for_gpus_match) check_allocatable_slots_for_intel_gpus_match ;;
    *) help_function ;;
    esac
}

main "$@"
