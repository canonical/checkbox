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

NAMESPACE="${1:-"gpu-operator-resources"}"
sleep 10
kubectl -n "$NAMESPACE" rollout status ds/gpu-operator-node-feature-discovery-worker
sleep 10
kubectl -n "$NAMESPACE" rollout status ds/nvidia-device-plugin-daemonset
sleep 10
kubectl -n "$NAMESPACE" rollout status ds/nvidia-operator-validator
