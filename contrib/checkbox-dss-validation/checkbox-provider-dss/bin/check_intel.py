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
"""Check enabling Intel GPU acceleration in Kubernetes"""

import time
import typing as t

from common import create_parser_with_checks_as_commands, run_command

SLOTS_PER_GPU = 10
SUCCESS_MARKER = "CHECKBOX_DSS_ENABLE_INTEL_SUCCESSFUL"


def parse_args(args: t.List[str] | None = None) -> dict[str, t.Any]:
    parser = create_parser_with_checks_as_commands(
        [
            can_be_enabled_with_plugin_version,
            node_label_is_attached,
            has_enough_capacity_slots,
            has_enough_allocatable_slots,
        ],
        description="Check enabling Intel GPU acceleration in Kubernetes",
    )
    return dict(parser.parse_args(args).__dict__)


def can_be_enabled_with_plugin_version(plugin_version: str) -> None:
    """Verify enabling Intel GPU plugin with the given version in K8s"""
    result = run_command("enable_intel.sh", plugin_version, str(SLOTS_PER_GPU))
    if SUCCESS_MARKER not in result:
        raise AssertionError("Couldn't verify enabling Intel GPU plugin")
    verify_all_rollouts()


def node_label_is_attached() -> None:
    """Verify appropriate Intel GPU label is attached to the node"""
    result = run_command(
        "kubectl",
        "get",
        "node",
        "-o",
        "jsonpath='{.items[0].metadata.labels.intel\\.feature\\.node\\.kubernetes\\.io/gpu}')",  # noqa: E501
    )
    assert "true" in result


def has_enough_capacity_slots() -> None:
    """Verify that the node has enough Intel GPU capacity slots"""
    print("sleeping for 10 seconds before checking capacity slots")
    time.sleep(10)
    result = run_command(
        "kubectl",
        "get",
        "node",
        "-o",
        "jsonpath='{.items[0].status.capacity.gpu\\.intel\\.com/i915}'",
    )
    result = result.replace("'", "")
    if len(result) < 1:
        raise AssertionError("No result for Intel GPU capacity slots")
    if int(result) < SLOTS_PER_GPU:
        raise AssertionError(
            f"{result} is less than expected capacity slots {SLOTS_PER_GPU}"
        )


def has_enough_allocatable_slots() -> None:
    """Verify that the node has enough Intel GPU allocatable slots"""
    print("sleeping for 10 seconds before checking allocatable slots")
    time.sleep(10)
    result = run_command(
        "kubectl",
        "get",
        "node",
        "-o",
        "jsonpath='{.items[0].status.allocatable.gpu\\.intel\\.com/i915}'",
    )
    result = result.replace("'", "")
    if len(result) < 1:
        raise AssertionError("No result for Intel GPU allocatable slots")
    if int(result) < SLOTS_PER_GPU:
        raise AssertionError(
            f"{result} is less than expected allocatable slots {SLOTS_PER_GPU}"
        )


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
    if expected not in result:
        raise AssertionError(f"Couldn't verify rollout of {daemonset}")


def main(args: t.List[str] | None = None) -> None:
    parsed = parse_args(args)
    parsed.pop("func")(**parsed)


if __name__ == "__main__":
    main()
