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
import json
import os
import subprocess
import typing as t

from checkbox_support.helpers.retry import run_with_retry
from checkbox_support.helpers.timeout import timeout

DEFAULT_NVIDIA_OPERATOR_VERSION = "v24.6.2"
DEFAULT_INTEL_PLUGIN_VERSION = "v0.30.0"

SNAP_MK8S = "/var/snap/microk8s"
MK8S_CONTAINERD_INFO = {
    "CONTAINERD_CONFIG": f"{SNAP_MK8S}/current/args/containerd-template.toml",
    "CONTAINERD_SOCKET": f"{SNAP_MK8S}/common/run/containerd.sock",
}


def main(args: t.List[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Setup K8s to use GPU from NVIDIA or Intel",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("vendor", choices=["nvidia", "intel"])
    parser.add_argument(
        "--version",
        required=False,
        default=None,
        help=(
            "Version of NVIDIA GPU Operator or Intel GPU Plugin, respectively;"
            " overrides respective env variables"
            " NVIDIA_GPU_OPERATOR_VERSION, or INTEL_GPU_PLUGIN_VERSION"
        ),
    )

    given = parser.parse_args(args)

    if given.vendor == "nvidia":
        if given.version is None:
            given.version = os.getenv(
                "NVIDIA_GPU_OPERATOR_VERSION", DEFAULT_NVIDIA_OPERATOR_VERSION
            )
        install_nvidia_gpu_operator(given.version)
    else:
        if given.version is None:
            given.version = os.getenv(
                "INTEL_GPU_PLUGIN_VERSION", DEFAULT_INTEL_PLUGIN_VERSION
            )
        install_intel_gpu_plugin(given.version)


@timeout(2)
def detect_if_microk8s() -> bool:
    try:
        status = subprocess.check_output(["microk8s", "status"], text=True)
        return status.startswith("microk8s is running")
    except subprocess.CalledProcessError:
        return False


@timeout(120)  # 2 minutes
def install_nvidia_gpu_operator(operator_version: str) -> None:
    setup_commands = [
        "helm repo add nvidia https://helm.ngc.nvidia.com/nvidia",
        "helm repo update",
    ]

    for command in setup_commands:
        subprocess.run(command.split(), check=True)

    ns = "gpu-operator-resources"
    helm_install = (
        "helm install --wait --generate-name --create-namespace"
        f" -n {ns} nvidia/gpu-operator --version={operator_version}"
    )

    try:
        is_microk8s = detect_if_microk8s()
    except TimeoutError:
        is_microk8s = False

    helm_config = None
    if is_microk8s:
        helm_install = f"{helm_install} -f -"
        helm_config = json.dumps(
            {
                "toolkit": {
                    "env": [
                        {"name": name, "value": value}
                        for name, value in MK8S_CONTAINERD_INFO.items()
                    ]
                }
            }
        ).encode()

    subprocess.run(helm_install.split(), input=helm_config, check=True)

    rollout = f"kubectl -n {ns} rollout status ds/nvidia-operator-validator"
    run_with_retry(subprocess.run, 10, 3, rollout.split(), check=True)


@timeout(900)  # 15 minutes
def install_intel_gpu_plugin(plugin_version: str) -> None:
    repo = (
        "https://github.com/intel/"
        "intel-device-plugins-for-kubernetes/deployments"
    )
    urls = [
        f"{repo}/nfd?ref={plugin_version}",
        f"{repo}/nfd/overlays/node-feature-rules?ref={plugin_version}",
        f"{repo}/gpu_plugin/overlays/nfd_labeled_nodes?ref={plugin_version}",
    ]
    for url in urls:
        setup_command = f"kubectl apply -k {url}"
        subprocess.check_call(setup_command.split())

    rollout_status = "kubectl -n default rollout status ds/intel-gpu-plugin"
    run_with_retry(subprocess.check_call, 10, 3, rollout_status.split())


if __name__ == "__main__":
    main()
