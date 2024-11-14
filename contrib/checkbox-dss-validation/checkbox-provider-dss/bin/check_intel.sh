#!/usr/bin/env bash

set -euxo pipefail

check_host_has_intel_gpus() {
    result=$(intel_gpu_top -L)
    if [[ ${result} == *"pci:vendor=8086"* ]]; then
        echo "Test success: Intel GPU available on host: ${result}"
    else
        >&2 echo "Test failure: "intel_gpu_top -L" reports no Intel GPUs: ${result}"
        exit 1
    fi
}

check_intel_gpu_plugin_can_be_installed() {
    # Using kubectl directly due to this bug: https://github.com/canonical/microk8s/issues/4453

    # TODO: make version a param
    VERSION=v0.30.0
    # hack as redirecting stdout anywhere but /dev/null throws a permission denied error
    # see: https://forum.snapcraft.io/t/eksctl-cannot-write-to-stdout/17254/4
    kubectl kustomize https://github.com/intel/intel-device-plugins-for-kubernetes/deployments/nfd?ref=${VERSION} | tee /tmp/node_feature_discovery.yaml >/dev/null
    kubectl kustomize https://github.com/intel/intel-device-plugins-for-kubernetes/deployments/nfd/overlays/node-feature-rules?ref=${VERSION} | tee /tmp/node_feature_rules.yaml >/dev/null
    kubectl kustomize https://github.com/intel/intel-device-plugins-for-kubernetes/deployments/gpu_plugin/overlays/nfd_labeled_nodes?ref=${VERSION} | tee /tmp/gpu_plugin.yaml >/dev/null
    sed -i 's/enable-monitoring/enable-monitoring\n        - -shared-dev-num=10/' /tmp/gpu_plugin.yaml
    kubectl apply -f /tmp/node_feature_discovery.yaml
    kubectl apply -f /tmp/node_feature_rules.yaml
    kubectl apply -f /tmp/gpu_plugin.yaml
    SLEEP_SECS=15
    echo "[INFO]: sleeping for ${SLEEP_SECS} seconds before checking rollout status."
    sleep ${SLEEP_SECS}
    kubectl -n node-feature-discovery rollout status ds/nfd-worker
    kubectl -n default rollout status ds/intel-gpu-plugin
    echo "[INFO]: sleeping for ${SLEEP_SECS} seconds to allow pod status to update for subsequent tests."
    sleep ${SLEEP_SECS}
    echo "Test success: Intel K8s GPU Device Plugin deployed."
}

check_intel_gpu_plugin_daemonset_is_deployed() {
    result=$(microk8s.kubectl get daemonset.apps -o jsonpath='{.items[0].metadata.name}')
    if [ "${result}" = "intel-gpu-plugin" ]; then
        echo "Test success: 'intel-gpu-plugin' daemonset is deployed!"
    else
        >&2 echo "Test failure: expected daemonset name 'intel-gpu-plugin' but got ${result}"
        exit 1
    fi
}

check_one_intel_gpu_plugin_daemonset_is_available() {
    result=$(microk8s.kubectl get daemonset.apps -o jsonpath='{.items[0].status.numberAvailable}')
    if [ "${result}" = "1" ]; then
        echo "Test success: 1 daemonset in numberAvailable status."
    else
        >&2 echo "Test failure: expected numberAvailable to be 1 but got ${result}"
        exit 1
    fi
}

check_one_intel_gpu_plugin_daemonset_is_ready() {
    result=$(microk8s.kubectl get daemonset.apps -o jsonpath='{.items[0].status.numberReady}')
    if [ "${result}" = "1" ]; then
        echo "Test success: 1 daemonset in numberReady status."
    else
        >&2 echo "Test failure: expected numberReady to be 1 but got ${result}"
        exit 1
    fi
}

check_intel_gpu_node_label_is_attached() {
    result=$(microk8s.kubectl get node -o jsonpath='{.items[0].metadata.labels.intel\.feature\.node\.kubernetes\.io/gpu}')
    if [ "${result}" = "true" ]; then
        echo "Test success: found expected label: 'intel.feature.node.kubernetes.io/gpu': 'true'"
    else
        >&2 echo "Test failure: expected 'true' but got ${result}"
        exit 1
    fi
}

check_at_least_one_intel_gpu_is_available() {
    result=$(microk8s.kubectl get node -o json | jq '.items[0].metadata.labels | with_entries(select(.key|match("gpu.intel.com/device-id.*.count";"i")))[] | tonumber' | awk '{cnt+=$1} END{print cnt}')
    if [ "${result}" -ge 1 ]; then
        echo "Test success: Found ${result} GPUs on system."
    else
        >&2 echo "Test failure: expected at least 1 GPU but got ${result}"
        exit 1
    fi
}

check_capacity_slots_for_intel_gpus_match() {
    num_gpus=$(microk8s.kubectl get node -o json | jq '.items[0].metadata.labels | with_entries(select(.key|match("gpu.intel.com/device-id.*.count";"i")))[] | tonumber' | awk '{cnt+=$1} END{print cnt}')
    result=$(microk8s.kubectl get node -o jsonpath='{.items[0].status.capacity.gpu\.intel\.com/i915}')
    # IMPORTANT NOTE: this is the sharedDevNum we pass into the gpu_plugin.yaml during installation
    SLOTS_PER_GPU=10
    total_slots=$((num_gpus * SLOTS_PER_GPU))
    if [ "${total_slots}" -eq "${result}" ]; then
        echo "Test success: Found ${result} GPU capacity slots on k8s node."
    else
        >&2 echo "Test failure: expected ${total_slots} GPU capacity slots but got ${result}"
        exit 1
    fi
}

check_allocatable_slots_for_intel_gpus_match() {
    num_gpus=$(microk8s.kubectl get node -o json | jq '.items[0].metadata.labels | with_entries(select(.key|match("gpu.intel.com/device-id.*.count";"i")))[] | tonumber' | awk '{cnt+=$1} END{print cnt}')
    result=$(microk8s.kubectl get node -o jsonpath='{.items[0].status.allocatable.gpu\.intel\.com/i915}')
    # IMPORTANT NOTE: this is the sharedDevNum we pass into the gpu_plugin.yaml during installation
    SLOTS_PER_GPU=10
    total_slots=$((num_gpus * SLOTS_PER_GPU))
    if [ "${total_slots}" -eq "${result}" ]; then
        echo "Test success: Found ${result} GPU allocatable slots on k8s node."
    else
        >&2 echo "Test failure: expected ${total_slots} GPU allocatable slots but got ${result}"
        exit 1
    fi
}

help_function() {
    echo "This script is used for tests related to Intel GPUs"
    echo "Usage: check.sh <test_case>"
    echo
    echo "Test cases currently implemented:"
    echo -e "\t<host_has_intel_gpus>: check_host_has_intel_gpus"
    echo -e "\t<gpu_plugin_can_be_installed>: check_intel_gpu_plugin_can_be_installed"
    echo -e "\t<gpu_plugin_daemonset_is_deployed>: check_intel_gpu_plugin_daemonset_is_deployed"
    echo -e "\t<one_daemonset_is_available>: check_one_intel_gpu_plugin_daemonset_is_available"
    echo -e "\t<one_daemonset_is_ready>: check_one_intel_gpu_plugin_daemonset_is_ready"
    echo -e "\t<gpu_node_label_is_attached>: check_intel_gpu_node_label_is_attached"
    echo -e "\t<at_least_one_gpu_is_available>: check_at_least_one_intel_gpu_is_available"
    echo -e "\t<capacity_slots_for_gpus_match>: check_capacity_slots_for_intel_gpus_match"
    echo -e "\t<allocatable_slots_for_gpus_match>: check_allocatable_slots_for_intel_gpus_match"
}

main() {
    case ${1} in
    host_has_intel_gpus) check_host_has_intel_gpus ;;
    gpu_plugin_can_be_installed) check_intel_gpu_plugin_can_be_installed ;;
    gpu_plugin_daemonset_is_deployed) check_intel_gpu_plugin_daemonset_is_deployed ;;
    one_daemonset_is_available) check_one_intel_gpu_plugin_daemonset_is_available ;;
    one_daemonset_is_ready) check_one_intel_gpu_plugin_daemonset_is_ready ;;
    gpu_node_label_is_attached) check_intel_gpu_node_label_is_attached ;;
    at_least_one_gpu_is_available) check_at_least_one_intel_gpu_is_available ;;
    capacity_slots_for_gpus_match) check_capacity_slots_for_intel_gpus_match ;;
    allocatable_slots_for_gpus_match) check_allocatable_slots_for_intel_gpus_match ;;
    *) help_function ;;
    esac
}

main "$@"
