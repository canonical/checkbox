#!/usr/bin/env python3
# Copyright 2025 Canonical Ltd.
# All rights reserved.
#
"""Check enabling Intel GPU acceleration in Kubernetes

Authors:
    - Abdullah (@motjuste) <abdullah.abdullah@canonical.com>
"""

import time
import typing as t

from common import create_parser_with_checks_as_commands, run_command

INTEL_DEVICE_PLUGIN_BASE_URL = (
    "https://github.com/intel/intel-device-plugins-for-kubernetes/deployments"
)
SLOTS_PER_GPU = 10


def parse_args(args: t.List[str] | None = None) -> dict[str, t.Any]:
    parser = create_parser_with_checks_as_commands(
        [
            can_be_enabled_with_plugin_version,
            node_label_is_attached,
            has_enough_capacity_slots,
            has_enough_allocatable_slots,
        ],
        description="Check enabling CUDA with microk8s",
    )
    return dict(parser.parse_args(args).__dict__)


def can_be_enabled_with_plugin_version(plugin_version: str) -> None:
    result = run_command("enable_intel.sh", plugin_version, str(SLOTS_PER_GPU))
    # nvidia_was_enabled = "NVIDIA is enabled" in result
    # gpu_was_already_enabled = "gpu is already enabled" in result
    # assert nvidia_was_enabled or gpu_was_already_enabled
    verify_all_rollouts()


def node_label_is_attached() -> None:
    result = run_command(
        "kubectl",
        "get",
        "node",
        "-o",
        "jsonpath='{.items[0].metadata.labels.intel\\.feature\\.node\\.kubernetes\\.io/gpu}')",  # noqa: E501
    )
    assert "true" in result


def has_enough_capacity_slots() -> None:
    result = run_command(
        "kubectl",
        "get",
        "node",
        "-o",
        "jsonpath='{.items[0].status.capacity.gpu\\.intel\\.com/i915}'",
    )
    assert int(result) >= SLOTS_PER_GPU


def has_enough_allocatable_slots() -> None:
    result = run_command(
        "kubectl",
        "get",
        "node",
        "-o",
        "jsonpath='{.items[0].status.allocatable.gpu\\.intel\\.com/i915}'",
    )
    assert int(result) >= SLOTS_PER_GPU


def verify_all_rollouts():
    verify_nfd_worker_rollout()
    verify_plugin_rollout()


def verify_nfd_worker_rollout():
    verify_rollout_of_daemonset("nfd-worker", "node-feature-discovery")


def verify_plugin_rollout():
    verify_rollout_of_daemonset("intel-gpu-plugin", "default")


def verify_rollout_of_daemonset(daemonset: str, namespace: str):
    print(f"sleeping for 10 seconds before checking rollout of {daemonset}")
    time.sleep(10)
    result = run_command(
        "kubectl",
        "-n",
        namespace,
        "rollout",
        "status",
        f"ds/{daemonset}",
    )
    expected = f'daemon set "{daemonset}" successfully rolled out'
    assert expected in result


def main(args: t.List[str] | None = None) -> None:
    parsed = parse_args(args)
    parsed.pop("func")(**parsed)


if __name__ == "__main__":
    main()
