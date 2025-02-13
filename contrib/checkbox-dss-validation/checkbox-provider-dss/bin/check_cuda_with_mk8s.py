#!/usr/bin/env python3
# Copyright 2025 Canonical Ltd.
# All rights reserved.
#
"""Check enabling CUDA with microk8s

Authors:
    - Abdullah (@motjuste) <abdullah.abdullah@canonical.com>
"""

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
    result = run_command(
        "sudo",
        "microk8s",
        "enable",
        "gpu",
        "--driver=operator",
        f"--version={operator_version}",
    )
    nvidia_was_enabled = "NVIDIA is enabled" in result
    gpu_was_already_enabled = "gpu is already enabled" in result
    assert nvidia_was_enabled or gpu_was_already_enabled
    verify_all_rollouts()


def has_all_validations_successful() -> None:
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
