#!/usr/bin/env python3
# Copyright 2025 Canonical Ltd.
# All rights reserved.
#
"""Run and check `dss` commands

Authors:
    - Abdullah (@motjuste) <abdullah.abdullah@canonical.com>
"""

import typing as t

from common import (
    create_parser_with_checks_as_commands,
    run_command as common_run_command,
)

_TIMEOUT_SEC: float = 10.0 * 60  # seconds


def run_command(*command: str, **kwargs) -> str:
    if "timeout" not in kwargs:
        kwargs["timeout"] = _TIMEOUT_SEC
    return common_run_command(*command, **kwargs)


def parse_args(args: t.List[str] | None = None) -> dict[str, t.Any]:
    parser = create_parser_with_checks_as_commands(
        [
            can_be_initialized,
            can_be_purged,
            has_mlflow_ready,
            has_intel_gpu_acceleration_enabled,
            has_nvidia_gpu_acceleration_enabled,
            can_create_notebook,
            can_start_removing_notebook,
        ],
        description="Run and check 'dss' commands",
    )
    parser.add_argument(
        "--timeout",
        default=_TIMEOUT_SEC,
        type=float,
        help="set timeout for command, in seconds",
    )
    return dict(parser.parse_args(args).__dict__)


def main(args: t.List[str] | None = None) -> None:
    global _TIMEOUT_SEC
    parsed = parse_args(args)
    _TIMEOUT_SEC = parsed.pop("timeout")
    parsed.pop("func")(**parsed)


def can_be_initialized(kube_config_text: str) -> None:
    """Check that `dss` can be initialized with the given `kube_config`"""
    result = run_command("dss", "initialize", "--kubeconfig", kube_config_text)
    assert "DSS initialized" in result, "dss was not initialised"


def can_be_purged() -> None:
    """Check that `dss` can be purged"""
    result = run_command("dss", "purge")
    assert "Success: All DSS components and notebooks purged successfully" in result


def has_mlflow_ready() -> None:
    """Check that `dss status` shows MLFlow in ready state"""
    _status_must_have("MLflow deployment: Ready")


def has_intel_gpu_acceleration_enabled() -> None:
    """Check that `dss status` shows Intel GPU acceleration enabled"""
    _status_must_have("Intel GPU acceleration: Enabled")


def has_nvidia_gpu_acceleration_enabled() -> None:
    """Check that `dss status` shows NVIDIA GPU acceleration enabled"""
    _status_must_have("NVIDIA GPU acceleration: Enabled")


def can_create_notebook(name: str, image: str) -> None:
    """Check that `dss` can create notebook with given `name` using given `image`"""
    result = run_command("dss", "create", name, "--image", image)
    assert (
        f"Success: Notebook {name} created successfully" in result
    ), f"dss could not create notebook '{name}' with image '{image}'"


def can_start_removing_notebook(name: str) -> None:
    """Check that `dss` can start removing notebook with given `name`"""
    result = run_command("dss", "remove", name)
    assert (
        f"Removing the notebook {name}" in result
    ), f"dss could not remove notebook '{name}'"


def _status_must_have(expected_result: str) -> None:
    result = run_command("dss", "status")
    assert expected_result in result, f"dss status does not have '{expected_result}'"


if __name__ == "__main__":
    main()
