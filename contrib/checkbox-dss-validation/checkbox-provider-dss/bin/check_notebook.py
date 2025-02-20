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
"""Check notebooks in DSS"""

import subprocess
import textwrap
import typing as t

from common import create_parser_with_checks_as_commands, run_command

_TIMEOUT_SEC: float = 15.0 * 60  # seconds

SUCCESS_MARKER = "CHECKBOX_DSS_TEST_SUCCESSFUL"

SCRIPT = {
    "pytorch_is_available": textwrap.dedent(
        f"""
        import torch
        print(torch.__version__)
        print("{SUCCESS_MARKER}")
        """
    ),
    "tensorflow_is_available": textwrap.dedent(
        f"""
        import tensorflow as tf
        print(tf.config.experimental.list_physical_devices())
        print("{SUCCESS_MARKER}")
        """
    ),
    "pytorch_can_use_intel_gpu": textwrap.dedent(
        f"""
        import sys
        import torch
        import intel_extension_for_pytorch as ipex

        print(torch.__version__)
        print(ipex.__version__)

        if torch.xpu.device_count() < 1:
            raise AssertionError("no XPUs are available")

        [
            print(i, torch.xpu.get_device_properties(i))
            for i in range(torch.xpu.device_count())
        ]
        print("{SUCCESS_MARKER}")
        """
    ),
    "tensorflow_can_use_intel_gpu": textwrap.dedent(
        f"""
        import tensorflow as tf
        import intel_extension_for_tensorflow as itex

        devices = tf.config.experimental.list_physical_devices()
        if any("XPU" in device for device in devices):
            print("{SUCCESS_MARKER}")
        else:
            raise AssertionError("XPU device not found")
        """
    ),
    "pytorch_can_use_nvidia_gpu": textwrap.dedent(
        f"""
        import torch
        if not torch.cuda.is_available():
            raise AssertionError("CUDA is not available")
        print("{SUCCESS_MARKER}")
        """
    ),
    "tensorflow_can_use_nvidia_gpu": textwrap.dedent(
        f"""
        import tensorflow as tf

        devices = tf.config.experimental.list_physical_devices("GPU")
        if any("GPU" in device for device in devices):
            print("{SUCCESS_MARKER}")
        else:
            raise AssertionError("CUDA device not found")
        """
    ),
}


def parse_args(args: t.List[str] | None = None) -> dict[str, t.Any]:
    parser = create_parser_with_checks_as_commands(
        [
            has_pytorch_available,
            has_tensorflow_available,
            can_use_intel_gpu_in_pytorch,
            can_use_intel_gpu_in_tensorflow,
            can_use_nvidia_gpu_in_pytorch,
            can_use_nvidia_gpu_in_tensorflow,
        ],
        description="Check notebooks in DSS",
    )
    parser.add_argument(
        "--timeout",
        default=_TIMEOUT_SEC,
        type=float,
        help="set timeout for command, in seconds",
    )
    return dict(parser.parse_args(args).__dict__)


def has_pytorch_available(notebook_name: str) -> None:
    """Check that notebook with given name has Pytorch available"""
    run_script_in_notebook(
        notebook_name,
        SCRIPT["pytorch_is_available"],
    )


def has_tensorflow_available(notebook_name: str) -> None:
    """Check that notebook with given name has Tensorflow available"""
    run_script_in_notebook(
        notebook_name,
        SCRIPT["tensorflow_is_available"],
    )


def can_use_intel_gpu_in_pytorch(notebook_name: str) -> None:
    """Check that notebook with given name can use Intel GPU in Pytorch"""
    run_script_in_notebook(
        notebook_name,
        SCRIPT["pytorch_can_use_intel_gpu"],
    )


def can_use_intel_gpu_in_tensorflow(notebook_name: str) -> None:
    """Check that notebook with given name can use Intel GPU in Tensorflow"""
    run_script_in_notebook(
        notebook_name,
        SCRIPT["tensorflow_can_use_intel_gpu"],
    )


def can_use_nvidia_gpu_in_pytorch(notebook_name: str) -> None:
    """Check that notebook with given name can use Intel GPU in Pytorch"""
    run_script_in_notebook(
        notebook_name,
        SCRIPT["pytorch_can_use_nvidia_gpu"],
    )


def can_use_nvidia_gpu_in_tensorflow(notebook_name: str) -> None:
    """Check that notebook with given name can use Intel GPU in Tensorflow"""
    run_script_in_notebook(
        notebook_name, SCRIPT["tensorflow_can_use_nvidia_gpu"]
    )


def run_script_in_notebook(notebook_name: str, script: str) -> None:
    pod = get_notebook_pod(notebook_name)
    result = run_script_in_pod(pod, script)
    if SUCCESS_MARKER not in result:
        raise AssertionError(f"{SUCCESS_MARKER} not in results:\n{result}")


def run_script_in_pod(pod_name: str, script: str) -> str:
    return run_command(
        "kubectl",
        "-n",
        "dss",
        "exec",
        pod_name,
        "--",
        "python",
        "-c",
        script,
        timeout=_TIMEOUT_SEC,
    )


def get_notebook_pod(notebook_name: str) -> str:
    cmd = "kubectl get pods -n dss --field-selector=status.phase==Running"
    all_pods = subprocess.check_output(cmd.split(), text=True)
    for line in all_pods.splitlines():
        if len(line) == 0:
            continue
        pod_name = line.split()[0]
        if pod_name.startswith(f"{notebook_name}-"):
            return pod_name
    raise AssertionError(
        f"no RUNNING pod for notebook {notebook_name} was found",
        f"available pods: {all_pods}"
    )


def main(args: t.List[str] | None = None) -> None:
    global _TIMEOUT_SEC
    parsed = parse_args(args)
    _TIMEOUT_SEC = parsed.pop("timeout")
    parsed.pop("func")(**parsed)


if __name__ == "__main__":  # pragma: no cover
    main()
