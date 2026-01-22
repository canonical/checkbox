#!/usr/bin/env python3
import os
from pathlib import (
    Path,
)
from typing import (
    Optional,
)


def find_npu_device_path() -> Optional[Path]:
    base_sys_path = Path("/sys/class/accel")
    if not base_sys_path.is_dir():
        raise SystemExit("'{}' is not a directory.".format(base_sys_path))

    for device_dir in base_sys_path.iterdir():
        try:
            # Check if the driver's name is 'intel_vpu'
            driver_path = device_dir / "device" / "driver"
            if "intel_vpu" in driver_path.readlink().name:
                device_path = Path("/dev/accel") / device_dir.name
                if device_path.exists():
                    return device_path
        except (
            IOError,
            FileNotFoundError,
        ):
            # Ignore directories that don't match the expected structure
            continue

    raise SystemExit("Could not find an Intel NPU device in /sys/class/accel.")


def main():
    npu_device = find_npu_device_path()

    # Check for read and write permissions
    has_readwrite_perm = os.access(
        npu_device,
        os.R_OK | os.W_OK,
    )

    if not has_readwrite_perm:
        raise SystemExit(
            "User lacks required permissions for {}".format(npu_device)
        )


if __name__ == "__main__":
    main()
