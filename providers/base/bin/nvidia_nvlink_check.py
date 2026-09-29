#!/usr/bin/env python3
import subprocess
import sys


def check_nvlink_status():
    # Run the nvidia-smi nvlink status command
    output = subprocess.check_output(
        ["nvidia-smi", "nvlink", "--status"],
        stderr=subprocess.STDOUT,
        universal_newlines=True,
    ).strip()

    print(output)

    # Case 1: Driver 580 behavior on unsupported devices (returns nothing)
    if not output:
        return False

    # Case 2: Driver 595 behavior on unsupported devices (explicitly states
    # lack of support)
    if (
        "does not have or support Nvlink" in output
        or "Not supported" in output
    ):
        return False

    # Case 3: NVLink is present and active
    # Active links typically look like:
    # $ nvidia-smi nvlink --status -i 0
    #     Link 0: active
    #     Link 1: active
    #     Link 2: active
    #     Link 3: active
    #
    # or
    #
    #     Link 0: 50 GB/s
    #     Link 1: 50 GB/s
    if "Link" in output:
        return True

    # Fallback safety: If there is output but no active links are declared
    return False


if __name__ == "__main__":
    if check_nvlink_status():
        print("NVLink Status: AVAILABLE and Active")
        sys.exit(0)
    else:
        print("NVLink Status: NOT AVAILABLE (or No Active Links)")
        sys.exit(1)
