#!/usr/bin/env bash
# This file is part of Checkbox.
#
# Copyright 2022 Canonical Ltd.
#
# Authors:
#     Abdullah (@motjuste) <abdullah.abdullah@canonical.com>
#
# Checkbox is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3,
# as published by the Free Software Foundation.
#
# Checkbox is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Checkbox.  If not, see <http://www.gnu.org/licenses/>.
set -eou pipefail

check_nvidia_gpu_rollout() {
    NAMESPACE="gpu-operator-resources"
    sleep 10
    kubectl -n "$NAMESPACE" rollout status ds/gpu-operator-feature-discovery
    sleep 10
    kubectl -n "$NAMESPACE" rollout status ds/nvidia-device-plugin-daemonset
    sleep 10
    kubectl -n "$NAMESPACE" rollout status ds/nvidia-operator-validator
}

check_intel_gpu_rollout() {
    sleep 10
    kubectl -n node-feature-discovery rollout status ds/nfd-worker
    sleep 10
    kubectl -n default rollout status ds/intel-gpu-plugin
}

help_function() {
    echo "This script is used for checking rollout of GPU-related daemonsets"
    echo "Usage: check_gpu_rollout.sh <nvidia | intel>"
    exit 2
}

main() {
    case ${1} in
    nvidia) check_nvidia_gpu_rollout ;;
    intel) check_intel_gpu_rollout ;;
    *) help_function ;;
    esac
}

main "$@"
