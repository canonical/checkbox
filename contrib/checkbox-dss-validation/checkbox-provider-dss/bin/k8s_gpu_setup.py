#!/usr/bin/env python3
#
# This file is part of Checkbox.
#
# Copyright 2025 Canonical Ltd.
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
"""Setup K8s cluster to use any detected GPUs from NVIDIA or Intel."""

import argparse
import json
import shlex
import subprocess
import time
import typing as t

from checkbox_support.helpers.retry import run_with_retry
from checkbox_support.helpers.timeout import timeout
from checkbox_support.parsers.udevadm import UdevadmParser


GPU_CATEGORIES = set(["VIDEO"])
VENDOR_NVIDIA = set(["NVIDIA Corporation"])
VENDOR_INTEL = set(["Intel Corporation"])

SLEEP_BEFORE_ROLLOUT = 60  # seconds

SNAP_MK8S = "/var/snap/microk8s"
MK8S_CONTAINERD_INFO = {
    "CONTAINERD_CONFIG": f"{SNAP_MK8S}/current/args/containerd-template.toml",
    "CONTAINERD_SOCKET": f"{SNAP_MK8S}/common/run/containerd.sock",
}

SKIP = "SKIP"


def main(args: t.List[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Setup K8s cluster to use any detected GPUs from NVIDIA or Intel."
            " The availability of any GPUs is parsed from udevadm database."
            " Microk8s requires some special handling, so please use the"
            " appropriate flag if the target cluster is based on Microk8s."
            " Please ENSURE that kube-config is setup for kubectl and helm."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--microk8s",
        help="Whether the K8s cluster is microk8s",
        action="store_true",
    )
    parser.add_argument(
        "nvidia_version",
        help=(
            "Operator version for NVIDIA GPU if found;"
            f" pass '{SKIP}' to not install it."
        ),
        type=_version_or_skip,
    )
    parser.add_argument(
        "intel_version",
        help=(
            "Plugin version for Intel GPU is found;"
            f" pass {SKIP} to not install it."
        ),
        type=_version_or_skip,
    )
    given = parser.parse_args(args)

    if given.nvidia_version is None and given.intel_version is None:
        print("SKIPped detecting and setting up all GPUs")
        return

    nvidia_detected, intel_detected = detect_available_gpu_vendors()
    if nvidia_detected and given.nvidia_version is not None:
        setup_nvidia_gpu_operator(given.nvidia_version, given.microk8s)
    if intel_detected and given.intel_version is not None:
        setup_intel_gpu_plugin(given.intel_version, given.microk8s)


def detect_available_gpu_vendors() -> t.Tuple[bool, bool]:
    cmd = "udevadm info --export-db"
    output = subprocess.check_output(shlex.split(cmd), text=True)
    udev = UdevadmParser(output)
    found_nvidia, found_intel = False, False
    for device in udev.run():
        if getattr(device, "category") in GPU_CATEGORIES:
            vendor = getattr(device, "vendor")
            if not found_nvidia:
                found_nvidia = vendor in VENDOR_NVIDIA
            if not found_intel:
                found_intel = vendor in VENDOR_INTEL
    print(f"Detected NVIDIA GPU: {found_nvidia}")
    print(f"Detected Intel GPU:  {found_intel}")
    return found_nvidia, found_intel


@timeout(60 * 15)  # 15 minutes
def setup_nvidia_gpu_operator(version: str, is_microk8s: bool) -> None:
    print(f"Installing NVIDIA GPU Operator {version}", flush=True)

    for cmd in [
        "helm repo add nvidia https://helm.ngc.nvidia.com/nvidia",
        "helm repo update",
    ]:
        subprocess.run(shlex.split(cmd), check=True)
    print("Added nvidia helm repo successfully", flush=True)

    ns = "gpu-operator-resources"
    helm_install = (
        "helm install --wait --generate-name --create-namespace"
        f" -n {ns} nvidia/gpu-operator --version={version}"
    )
    if is_microk8s:
        print("Passing containerd config for Microk8s", flush=True)
        helm_install = f"{helm_install} -f -"
        helm_config_dict = {
            "toolkit": {
                "env": [
                    {"name": name, "value": value}
                    for name, value in MK8S_CONTAINERD_INFO.items()
                ]
            }
        }
        helm_config = json.dumps(helm_config_dict).encode()
    else:
        helm_config = None

    subprocess.run(shlex.split(helm_install), input=helm_config, check=True)

    # NOTE:@motjuste: Even with retry, we need to time.sleep
    #   run_with_retry keeps trying until it succeeds or times out, but even a
    #   single success is enough to finish.
    #
    #   Unfortunately, the rollout status of the following required daemonsets
    #   update multiple times initially, before finally settling down.  Hence,
    #   we need to wait here before verifying rollouts.
    print(f"sleeping for {SLEEP_BEFORE_ROLLOUT} sec before checking rollout")
    time.sleep(SLEEP_BEFORE_ROLLOUT)

    for daemonset in [
        "ds/nvidia-device-plugin-daemonset",
        "ds/nvidia-operator-validator",
    ]:
        cmd = f"kubectl -n {ns} rollout status {daemonset}"
        run_with_retry(subprocess.run, 200, 3, shlex.split(cmd), check=True)
    print("Finished NVIDIA GPU operator setup successfully", flush=True)


@timeout(60 * 15)  # 15 minutes
def setup_intel_gpu_plugin(version: str, is_microk8s: bool) -> None:
    _ = is_microk8s  # irrelevant at the moment
    print(f"Installing Intel GPU plugin {version}", flush=True)
    repo = (
        "https://github.com/intel/"
        "intel-device-plugins-for-kubernetes/deployments"
    )
    urls = [
        f"{repo}/nfd?ref={version}",
        f"{repo}/nfd/overlays/node-feature-rules?ref={version}",
        f"{repo}/gpu_plugin/overlays/nfd_labeled_nodes?ref={version}",
    ]
    for url in urls:
        cmd = f"kubectl apply -k {url}"
        subprocess.run(shlex.split(cmd), check=True)

    print(f"sleeping for {SLEEP_BEFORE_ROLLOUT} sec before checking rollout")
    time.sleep(SLEEP_BEFORE_ROLLOUT)

    for cmd in [
        "kubectl -n node-feature-discovery rollout status ds/nfd-worker",
        "kubectl -n default rollout status ds/intel-gpu-plugin",
    ]:
        run_with_retry(subprocess.run, 100, 3, shlex.split(cmd), check=True)
    print("Finished Intel GPU plugin setup successfully", flush=True)


def _version_or_skip(value: str) -> str | None:
    if value == "":
        raise argparse.ArgumentTypeError("Empty value is not allowed")
    return None if value == SKIP else None


if __name__ == "__main__":  # pragma: no cover
    main()
