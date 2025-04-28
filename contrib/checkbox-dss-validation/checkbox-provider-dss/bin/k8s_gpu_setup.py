#!/usr/bin/env python3
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
"""Setup K8s to use GPU from NVIDIA or Intel"""

import argparse
import subprocess
import time
import typing as t


def main(args: t.List[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Setup K8s to use GPU from NVIDIA or Intel",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("vendor", choices=["nvidia", "intel"])
    parser.add_argument(
        "version",
        type=str,
        help="Version of NVIDIA GPU Operator or Intel GPU Plugin, resp.",
    )
    given = parser.parse_args(args)

    if given.vendor == "nvidia":
        install_nvidia_gpu_operator(given.version)
    else:
        install_intel_gpu_plugin(given.version)


def install_nvidia_gpu_operator(operator_version: str) -> None:
    subprocess.check_call(
        "helm repo add nvidia https://helm.ngc.nvidia.com/nvidia".split()
    )
    subprocess.check_call("helm repo update".split())

    k8s_ns = "gpu-operator-resources"
    cmd = "helm install --wait --generate-name --create-namespace"
    cmd = f"{cmd} -n {k8s_ns} nvidia/gpu-operator --version={operator_version}"
    cmd = f"{cmd} --kubeconfig ~/.kube/config"
    subprocess.check_call(cmd.split())

    time.sleep(30)  # node feature discovery will need some time
    cmd = f"kubectl -n {k8s_ns} rollout status ds/nvidia-operator-validator"
    subprocess.check_call(cmd.split())


def install_intel_gpu_plugin(plugin_version: str) -> None:
    repo_url = (
        "https://github.com/intel/"
        "intel-device-plugins-for-kubernetes/deployments"
    )
    subprocess.check_call(
        f"kubectl apply -k {repo_url}/nfd?ref={plugin_version}".split()
    )
    subprocess.check_call(
        (
            f"kubectl apply -k {repo_url}/nfd/"
            f"overlays/node-feature-rules?ref={plugin_version}"
        ).split()
    )
    subprocess.check_call(
        (
            f"kubectl apply -k {repo_url}/gpu_plugin/"
            f"overlays/nfd_labeled_nodes?ref={plugin_version}"
        ).split()
    )

    time.sleep(30)  # node feature discovery will need some time
    subprocess.check_call(
        "kubectl -n default rollout status ds/intel-gpu-plugin".split()
    )


if __name__ == "__main__":
    main()
