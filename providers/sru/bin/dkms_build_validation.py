#!/usr/bin/env python3
#
# Copyright 2017-2024 Canonical Ltd.
# Written by:
#   Taihsiang Ho (tai271828) <taihsiang.ho@canonical.com>
#   Fernando Bravo <fernando.bravo.hernandez@canonical.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3,
# as published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from collections import Counter
import logging
from packaging import version
import re
import subprocess
import sys
import textwrap
from typing import Dict, List, Optional, Set, Tuple

logger = logging.getLogger("dkms_build_validation")


def run_command(command: List[str]) -> str:
    """Run a shell command and return its output"""
    try:
        result = subprocess.check_output(
            command,
            stderr=subprocess.STDOUT,  # We capture stdout and stderr in stdout
            universal_newlines=True,
        )
        return result.strip()
    except subprocess.CalledProcessError as e:
        raise SystemExit(
            "Command '{}' failed with exit code {}:\n{}".format(
                e.cmd, e.returncode, e.stdout
            )
        )


def parse_version(ver: str) -> version.Version:
    """Parse the version string and return a version object"""
    match = re.match(r"(\d+\.\d+\.\d+(-\d+)?)", ver)
    if match:
        parsed_version = version.parse(match.group(1))
    else:
        raise SystemExit(f"Invalid version string: {ver}")
    return parsed_version


def parse_dkms_status(dkms_status: str, ubuntu_release: str) -> List[Dict]:
    """Parse the output of 'dkms status', the result is a list of dictionaries
    that contain the kernel version parsed the status for each one.
    """
    kernel_info = []
    for line in dkms_status.splitlines():
        details, fullstatus = line.split(": ")
        if " " in fullstatus:
            status, rest = fullstatus.split(maxsplit=1)
            logger.warning("dkms status included warning:")
            logger.warning(f" module: {details}")
            logger.warning(f" message: {rest}")
        else:
            status = fullstatus
        # will only get comma separated info on two statuses
        # https://github.com/dell/dkms/blob/master/dkms.in#L1866
        if status in ("built", "installed"):
            if version.parse(ubuntu_release) >= version.parse("22.04"):
                kernel_ver = details.split(", ")[1]
            else:
                kernel_ver = details.split(", ")[2]
            # newer releases print "module/version, kernel, arch",
            # older ones "module, version, kernel, arch"
            fields = details.split(", ")
            if "/" in fields[0]:
                module, module_version = fields[0].split("/", 1)
            else:
                module, module_version = fields[0], fields[1]
            kernel_info.append(
                {
                    "version": kernel_ver,
                    "status": status,
                    "module": module,
                    "module_version": module_version,
                }
            )
            print(
                "Found module {}, status {} for kernel version {}".format(
                    details, status, kernel_ver
                )
            )

    sorted_kernel_info = sorted(
        kernel_info, key=lambda x: parse_version(x["version"])
    )
    return sorted_kernel_info


def check_kernel_version(
    kernel_ver_current: str, sorted_kernel_info: List[Dict], dkms_status: str
) -> int:
    kernel_ver_max = sorted_kernel_info[-1]["version"]
    if kernel_ver_max != kernel_ver_current:
        msg = textwrap.dedent(
            """
            Current kernel version does not match the latest built DKMS module.
            Your running kernel: {kernel_ver_current}
            Latest DKMS module built on kernel: {kernel_ver_max}
            Maybe the target DKMS was not built,
            or you are not running the latest available kernel.
            """.format(
                kernel_ver_current=kernel_ver_current,
                kernel_ver_max=kernel_ver_max,
            )
        )
        logger.error(msg)
        logger.error(f"=== DKMS status ===\n{dkms_status}")
        return 1
    return 0


def check_dkms_module_count(sorted_kernel_info: List[Dict], dkms_status: str):
    kernel_ver_max = sorted_kernel_info[-1]["version"]
    kernel_ver_min = sorted_kernel_info[0]["version"]

    version_count = Counter([item["version"] for item in sorted_kernel_info])
    number_dkms_min = version_count[kernel_ver_min]
    number_dkms_max = version_count[kernel_ver_max]
    number_dkms_min = version_count[kernel_ver_min]
    number_dkms_max = version_count[kernel_ver_max]

    if number_dkms_min != number_dkms_max:
        msg = textwrap.dedent(
            """
            {number_dkms_min}  modules for {kernel_ver_min}
            {number_dkms_max}  modules for {kernel_ver_max}
            DKMS module number is inconsistent. Some modules may not be built.
            """.format(
                number_dkms_min=number_dkms_min,
                kernel_ver_min=kernel_ver_min,
                number_dkms_max=number_dkms_max,
                kernel_ver_max=kernel_ver_max,
            )
        )
        logger.warning(msg)
        logger.warning(f"=== DKMS status ===\n{dkms_status}")
        return 1
    return 0


def get_context_lines(log: List[str], line_numbers: Set[int]) -> List[str]:
    # Create a set with the indexes of the lines to be printed
    context_lines = set()
    context = 5
    n_lines = len(log)
    for i in line_numbers:
        min_numbers = max(0, i - context)
        max_numbers = min(n_lines, i + context + 1)
        for j in range(min_numbers, max_numbers):
            context_lines.add(j)
    return [log[i] for i in sorted(context_lines)]


# DKMS reports the module of a failed build in the line that follows the
# build error message, e.g.
# Error! Bad return status for module build on kernel: 6.8.0-44 (x86_64)
# Consult /var/lib/dkms/nvidia/550.107.02/build/make.log for more information.
MAKE_LOG_RE = re.compile(
    r"Consult /var/lib/dkms/(?P<module>[^/\s]+)/(?P<version>[^/\s]+)"
    r"/build/make\.log"
)


def get_failed_module(
    log: List[str], err_line_number: int
) -> Optional[Tuple[str, str]]:
    """Get the name and version of the module of a DKMS build error.

    Return None if the log does not identify the failing module.
    """
    if err_line_number + 1 >= len(log):
        return None
    match = MAKE_LOG_RE.search(log[err_line_number + 1])
    if not match:
        return None
    return match.group("module"), match.group("version")


def is_superseded(
    log: List[str],
    err_line_number: int,
    module: str,
    failed_version: str,
    installed_version: Optional[str],
) -> bool:
    """Tell if a later build fixed a module build error.

    It did if the module is installed now and either:
    - the installed version is the one that failed, so a retry worked;
    - the installed version shows up in the log after the error, e.g.
      "Loading new nvidia/580.95.05 DKMS files..." ("nvidia-580.95.05"
      on older DKMS).

    Known gap: a log line can name a version without building it, e.g.
    "Module nvidia/460.56 already installed ..., skip.". If an upgrade
    failed but left the old version installed, such a line would hide
    the failure. Packaged modules don't hit this: dh_dkms and Ubuntu's
    nvidia-dkms-* packages remove the old version before installing the
    new one, so a failed upgrade leaves no version installed.
    """
    if installed_version is None:
        return False
    if installed_version == failed_version:
        return True
    # start after the error and its "Consult ... make.log" line
    start = err_line_number + 2
    mentions = (
        "{}/{}".format(module, installed_version),
        "{}-{}".format(module, installed_version),
    )
    return any(mention in line for line in log[start:] for mention in mentions)


def has_dkms_build_errors(
    kernel_ver_current: str, sorted_kernel_info: List[Dict]
) -> int:
    """Scan the APT log for DKMS build errors for the running kernel.

    Errors fixed by a later build (e.g. a driver upgrade or a retry)
    are only reported as warnings. All other errors fail the test,
    including a failed upgrade that left the old version installed.
    """
    log_path = "/var/log/apt/term.log"
    err_msg = "Bad return status for module build on kernel: {}".format(
        kernel_ver_current
    )
    with open(log_path) as f:
        log = f.readlines()

    # versions of the modules installed for the running kernel
    installed_modules = {
        entry["module"]: entry["module_version"]
        for entry in sorted_kernel_info
        if entry["version"] == kernel_ver_current
        and entry["status"] == "installed"
    }

    superseded_line_numbers = set()
    unresolved_line_numbers = set()
    for line_number, line in enumerate(log):
        if err_msg not in line:
            continue
        failed = get_failed_module(log, line_number)
        if failed is None:
            unresolved_line_numbers.add(line_number)
            continue
        module, failed_version = failed
        installed_version = installed_modules.get(module)
        if is_superseded(
            log, line_number, module, failed_version, installed_version
        ):
            superseded_line_numbers.add(line_number)
            logger.warning(
                "dkms build error for module {}/{} was superseded: "
                "{}/{} was built later and is installed for kernel {} "
                "now".format(
                    module,
                    failed_version,
                    module,
                    installed_version,
                    kernel_ver_current,
                )
            )
        else:
            unresolved_line_numbers.add(line_number)

    if unresolved_line_numbers:
        logger.error(f"Found dkms build error messages in {log_path}")
        logger.error("\n=== build log ===")
        err_with_context = get_context_lines(log, unresolved_line_numbers)
        logger.error("".join(err_with_context))
        return 1

    if superseded_line_numbers:
        logger.warning("\n=== superseded build log ===")
        err_with_context = get_context_lines(log, superseded_line_numbers)
        logger.warning("".join(err_with_context))
    return 0


def main():
    # Get the kernel version and DKMS status
    ubuntu_release = run_command(["lsb_release", "-r"]).split()[-1]
    dkms_status = run_command(["dkms", "status"])

    # Parse and sort the DKMS status and sort the kernel versions
    sorted_kernel_info = parse_dkms_status(dkms_status, ubuntu_release)

    # if there are no built or installed dkms modules there is nothing
    # to check
    if not sorted_kernel_info:
        print("No installed dkms modules found, nothing to check")
        return 0

    # kernel_ver_max should be the same as kernel_ver_current
    kernel_ver_current = run_command(["uname", "-r"])
    if check_kernel_version(
        kernel_ver_current, sorted_kernel_info, dkms_status
    ):
        return 1

    # Count the occurrences of the latest and the oldest kernel version and
    # compare the number of DKMS modules for min and max kernel versions
    check_dkms_module_count(sorted_kernel_info, dkms_status)

    # Scan the APT log for errors during system update
    return has_dkms_build_errors(kernel_ver_current, sorted_kernel_info)


if __name__ == "__main__":
    sys.exit(main())
