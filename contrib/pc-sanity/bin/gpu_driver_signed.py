#!/usr/bin/env python3

import os
import subprocess
import sys


def get_gpu_addresses():
    gpu_classes = ["0300", "0302", "0380"]
    gpus = []

    for gpu_class in gpu_classes:
        output = subprocess.check_output(
            ["lspci", "-n", "-d", f"::{gpu_class}"],
            text=True,
            stderr=subprocess.DEVNULL,
        )
        for line in output.strip().split("\n"):
            if line:
                gpus.append(line.split()[0])

    return gpus


def has_gpu_driver(gpu):
    if not gpu.startswith("0000:"):
        gpu = f"0000:{gpu}"

    try:
        with open(f"/sys/bus/pci/devices/{gpu}/vendor") as f:
            vendor = f.read().strip()
        with open(f"/sys/bus/pci/devices/{gpu}/device") as f:
            device = f.read().strip()
    except (FileNotFoundError, OSError) as e:
        print(f"E: Cannot read device info for {gpu}: {e}")
        return False

    driver_path = f"/sys/bus/pci/devices/{gpu}/driver"
    if not os.path.isdir(driver_path):
        print(f"E: Your GPU {gpu} ({vendor}:{device}) hasn't driver.")
        subprocess.run(["lspci", "-nnvk", "-s", gpu])
        return False

    driver = os.path.basename(os.readlink(driver_path))
    print(f"Your GPU {gpu} is using {driver}.")
    return True


def has_nvidia_signature(modinfo_output, nvidia_version):
    if "Canonical Ltd. Kernel Module Signing" in modinfo_output:
        print("Nvidia driver is signed.")
        return True

    print("E: Your nvidia driver is not signed by Canonical.")
    kernel_version = subprocess.check_output(
        ["uname", "-r"], text=True
    ).strip()
    major_version = nvidia_version.split(".")[0]
    print(
        f"E: Expecting linux-modules-nvidia-{major_version}-{kernel_version}."
    )
    return False


def has_nvidia_package_support(nvidia_version):
    pkg = f"nvidia-driver-{nvidia_version.split('.')[0]}"

    try:
        apt_output = subprocess.check_output(
            ["apt", "show", pkg],
            stderr=subprocess.DEVNULL,
            text=True,
        )
        support = None
        for line in apt_output.split("\n"):
            if line.startswith("Support:"):
                support = line.split()[1]
                break

        if support == "LTSB":
            print("Nvidia driver is LTS version.")
            return True
        elif support == "PB":
            print("Nvidia driver is production version.")
            return True
        else:
            print(f"E: {pkg} is not LTS version, please check.")
            print(f"Package {pkg} has support type: {support}")
            subprocess.run(["apt-cache", "madison", pkg])
            return False
    except subprocess.CalledProcessError as e:
        print(f"E: Cannot check package {pkg}: {e}")
        return False


def get_nvidia_version_modinfo():
    """
    Get NVIDIA driver version from modinfo.

    Returns:
        Tuple of (version_string, modinfo_output) if driver is present,
        (None, None) otherwise
    """
    try:
        modinfo_output = subprocess.check_output(
            ["modinfo", "nvidia"],
            stderr=subprocess.DEVNULL,
            text=True,
        )
    except subprocess.CalledProcessError:
        # NVIDIA driver not loaded or not present
        return None, None

    for line in modinfo_output.split("\n"):
        if line.startswith("version:"):
            return line.split()[1], modinfo_output

    return None, None


def main():
    has_errors = False

    # Verify driver for each GPU
    gpus = get_gpu_addresses()
    for gpu in gpus:
        if not has_gpu_driver(gpu):
            has_errors = True

    # Verify signature and package support for NV
    nvidia_version, modinfo_output = get_nvidia_version_modinfo()
    if nvidia_version:
        print(f"Nvidia version is {nvidia_version}.")

        if not has_nvidia_signature(modinfo_output, nvidia_version):
            has_errors = True

        if not has_nvidia_package_support(nvidia_version):
            has_errors = True

    return has_errors


if __name__ == "__main__":
    sys.exit(main())
