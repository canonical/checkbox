#!/usr/bin/env bash
#
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
#
set -eo pipefail

# This follows the how-to from the DSS team, see:
# <https://github.com/canonical/data-science-stack/blob/e495bacef97a1b6bf8bdb63dca29912be317be8c/docs/how-to/enable-gpus/enable-intel-gpu.rst>

VERSION="${1:-"v0.30.0"}"

# IMPORTANT: this is the sharedDevNum we pass into the gpu_plugin.yaml during installation
SLOTS_PER_GPU="${2:-"10"}"

# hack with tee as redirecting stdout anywhere but /dev/null throws a permission denied error
# see: https://forum.snapcraft.io/t/eksctl-cannot-write-to-stdout/17254/4
kubectl kustomize "https://github.com/intel/intel-device-plugins-for-kubernetes/deployments/nfd?ref=${VERSION}" | tee /tmp/node_feature_discovery.yaml >/dev/null
kubectl kustomize "https://github.com/intel/intel-device-plugins-for-kubernetes/deployments/nfd/overlays/node-feature-rules?ref=${VERSION}" | tee /tmp/node_feature_rules.yaml >/dev/null
kubectl kustomize "https://github.com/intel/intel-device-plugins-for-kubernetes/deployments/gpu_plugin/overlays/nfd_labeled_nodes?ref=${VERSION}" | tee /tmp/gpu_plugin.yaml >/dev/null

sed -i "s/enable-monitoring/enable-monitoring\n        - -shared-dev-num=${SLOTS_PER_GPU}/" /tmp/gpu_plugin.yaml

kubectl apply -f /tmp/node_feature_discovery.yaml
kubectl apply -f /tmp/node_feature_rules.yaml
kubectl apply -f /tmp/gpu_plugin.yaml
