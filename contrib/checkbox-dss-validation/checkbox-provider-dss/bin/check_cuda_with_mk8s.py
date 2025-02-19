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
"""Check enabling CUDA with microk8s"""

import time
import typing as t

from common import create_parser_with_checks_as_commands, run_command


def parse_args(args: t.List[str] | None = None) -> dict[str, t.Any]:
    parser = create_parser_with_checks_as_commands(
        [
            can_be_enabled_with_operator_version,
            has_all_validations_successful,
        ],
        description="Check enabling CUDA with microk8s",
    )
    return dict(parser.parse_args(args).__dict__)


def can_be_enabled_with_operator_version(operator_version: str) -> None:
    """Verify enabling CUDA addon in microk8s of given operator_version"""
    result = run_command(
        "sudo",
        "microk8s",
        "enable",
        "gpu",
        "--driver=operator",
        f"--version={operator_version}",
    )
    was_enabled_mk8s_in_1_28 = "NVIDIA is enabled" in result
    was_enabled_mk8s_in_1_31 = "Deployed NVIDIA GPU operator" in result
    nvidia_was_enabled = was_enabled_mk8s_in_1_28 or was_enabled_mk8s_in_1_31
    gpu_was_already_enabled = "gpu is already enabled" in result
    assert nvidia_was_enabled or gpu_was_already_enabled
    verify_all_rollouts()


def has_all_validations_successful() -> None:
    """Verify that all NVIDIA operator validations were successful"""
    result = run_command(
        "kubectl",
        "logs",
        "-n",
        "gpu-operator-resources",
        "-lapp=nvidia-operator-validator",
        "-c",
        "nvidia-operator-validator",
    )
    assert "all validations are successful" in result


def verify_all_rollouts():
    verify_node_feature_discovery_rollout()
    verify_plugin_rollout()
    verify_validator_rollout()


def verify_node_feature_discovery_rollout():
    verify_rollout_of_daemonset("gpu-operator-node-feature-discovery-worker")


def verify_plugin_rollout():
    verify_rollout_of_daemonset("nvidia-device-plugin-daemonset")


def verify_validator_rollout():
    verify_rollout_of_daemonset("nvidia-operator-validator")


def verify_rollout_of_daemonset(daemonset: str):
    print(f"sleeping for 10 seconds before checking rollout of {daemonset}")
    time.sleep(10)
    result = run_command(
        "kubectl",
        "-n",
        "gpu-operator-resources",
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
