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
import typing as t


def run_script_in_notebook(notebook_name: str, script: str) -> None:
    pod = get_notebook_pod(notebook_name)
    base_cmd = f"kubectl -n dss exec {pod} -- python -c"
    subprocess.check_call([*base_cmd.split(), script])


def get_notebook_pod(notebook_name: str) -> str:
    cmd = [
        "kubectl",
        "get",
        "pods",
        "-n",
        "dss",
        "--field-selector=status.phase==Running",
        "-o",
        "jsonpath={.items[*].metadata.name}",
    ]
    all_pods = subprocess.check_output(cmd, text=True)
    for pod_name in all_pods.split():
        if pod_name.startswith(f"{notebook_name}-"):
            return pod_name
    raise AssertionError(
        f"no RUNNING pod for notebook {notebook_name} was found",
        f"available pods: {all_pods}",
    )


def main(args: t.List[str] | None = None) -> None:
    raise NotImplementedError


if __name__ == "__main__":  # pragma: no cover
    main()
