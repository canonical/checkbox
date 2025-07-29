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

import argparse
import os
from pathlib import Path
import subprocess
import textwrap
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


def create_parser(checks_names: t.Sequence[str]) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=textwrap.dedent(
            """
           Check notebooks in DSS by running Python scripts in their pods.

           Possible scripts to run must be placed in the data directory,
           and named as `<check_name>.py` for them to be available as a
           check named `<check_name>`.  The data directory is NOT searched
           recursively.

           If no scripts are found in the data directory, an error is raised.

           `./data` is used as the data directory by default, but it can
           be overridden by setting `PLAINBOX_PROVIDER_DATA` in the env.
           """
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "notebook_name",
        type=str,
        help="Name of the notebook in DSS to run the check in",
    )
    parser.add_argument(
        "check_name",
        type=str,
        choices=checks_names,
        help="Name of check to perform in the notebook",
    )
    return parser


def get_available_checks() -> t.Dict[str, Path]:
    data_dir = Path(os.getenv("PLAINBOX_PROVIDER_DATA", "data"))
    checks = {script.stem: script for script in data_dir.glob("*.py")}
    if len(checks) == 0:
        raise ValueError(f"no Python scripts found in directory {data_dir}")
    return checks


def main(args: t.List[str] | None = None) -> None:
    checks = get_available_checks()
    parser = create_parser(sorted(checks.keys()))
    parsed = parser.parse_args(args)

    script = checks[parsed.check_name].read_text()
    run_script_in_notebook(parsed.notebook_name, script)


if __name__ == "__main__":  # pragma: no cover
    main()
