#!/usr/bin/env python3
import re
import sys
import logging
from pathlib import Path

SOC_ROOT = "/sys/devices/soc0"


def init_logger():
    """
    Set the logger to log DEBUG and INFO to stdout, and
    WARNING, ERROR, CRITICAL to stderr.
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    logger_format = "%(asctime)s %(levelname)-8s %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"

    # Log DEBUG and INFO to stdout, others to stderr
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setFormatter(logging.Formatter(logger_format, date_format))

    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setFormatter(logging.Formatter(logger_format, date_format))

    stdout_handler.setLevel(logging.DEBUG)
    stderr_handler.setLevel(logging.WARNING)

    # Add a filter to the stdout handler to limit log records to
    # INFO level and below
    stdout_handler.addFilter(lambda record: record.levelno <= logging.INFO)

    root_logger.addHandler(stderr_handler)
    root_logger.addHandler(stdout_handler)

    return root_logger


def get_soc_family():
    """
    Read data from /sys/devices/soc0/family

    Raises:
        SystemExit: If failed to identify SoC family

    Returns:
        soc_family (str): SoC family.
    """
    soc_family = ""
    soc_file = Path(SOC_ROOT).joinpath("family")
    if soc_file.is_file():
        soc_family = soc_file.read_text().strip("\n")
        logging.info("SoC family is %s", soc_family)
    else:
        raise FileNotFoundError(
            "{} file is not available".format(str(soc_file))
        )

    return soc_family


def get_soc_id():
    """
    Read data from /sys/devices/soc0/soc_id

    Returns:
        soc_id (str): SoC ID.
    """
    soc_id = ""
    soc_file = Path(SOC_ROOT).joinpath("soc_id")
    if soc_file.is_file():
        soc_id = soc_file.read_text().strip("\n")
    else:
        raise FileNotFoundError(
            "{} file is not available".format(str(soc_file))
        )

    logging.info("SoC ID is %s", soc_id)
    return soc_id


def get_kernel_version():
    """
    Get kernel version

    Raises:
        SystemExit: If failed to identify kernel version

    Returns:
        kernel_ver (str): Kernel version
    """
    path = "/proc/version"
    kernel_file = Path(path)
    if kernel_file.is_file():
        raw_data = kernel_file.read_text().strip("\n")
    else:
        raise FileNotFoundError("{} file is not available".format(path))

    kernel_match = re.search(
        r"Linux version ([0-9]+\.[0-9]+)\.[0-9]+-", raw_data
    )
    if kernel_match is None:
        raise ValueError("Failed to identify kernel version")

    return kernel_match.groups()[0]


def determine_expected_imx_vpu(soc_type, kernel_version):
    """
    Query the supported VPU for specific i.MX SoC Type

    Args:
        soc_type (str): The type of i.MX SoC

    Raises:
        SystemExit: If the SoC type is not defined.

    Returns:
        expected_devices (list): the supported i.MX VPU device of SoC
    """
    expected_devices = []
    if soc_type == "i.MX8MM":
        expected_devices = ["ion", "mxc_hantro", "mxc_hantro_h1"]
    elif soc_type == "i.MX8ML":
        expected_devices = ["ion", "mxc_hantro", "mxc_hantro_h1"]
    elif soc_type == "i.MX8MQ":
        expected_devices = ["ion", "mxc_hantro"]
    elif soc_type == "i.MX8MP":
        expected_devices = ["ion", "mxc_hantro", "mxc_hantro_vc8000e"]
    else:
        raise SystemExit(
            "Supported VPU devices for {} is not defined".format(soc_type)
        )

    major_ver, minor_ver = kernel_version.split(".")
    if int(major_ver) > 5 or (int(major_ver) == 5 and int(minor_ver) >= 15):
        expected_devices.remove("ion")

    return expected_devices


def check_imx_vpu_devices():
    """
    Check the i.MX VPU devices

    Args:
        soc_type (str): i.MX SoC Type

    Raises:
        SystemExit: If the SoC type is not expected
                    If VPU devices are not expected

    Reference:
        https://github.com/Freescale/libimxvpuapi#dwl-and-ewl-errors
    """
    result = True

    expected_devices = determine_expected_imx_vpu(
        get_soc_id(), get_kernel_version()
    )
    nodes = [dev.name for dev in list(Path("/dev").iterdir())]
    for dev in expected_devices:
        if dev in nodes:
            logging.info("The %s device is available", dev)
        else:
            logging.error("The %s device is not exists!", dev)
            result = False

    if result:
        logging.info("# VPU devices check: Passed")
    else:
        raise SystemExit("# VPU devices check: Failed")


def get_v4l2_devices():
    """
    Get the name of all V4L2 devices

    Returns:
        v4l2_dev_name (list): V4L2 device name
    """
    v4l2_dev_name = []
    for device in sorted(Path("/sys/class/video4linux").glob("video*/name")):
        v4l2_dev_name.append(device.read_text().strip("\n"))

    return v4l2_dev_name


def check_mtk_vpu_devices():
    """
    Detect MTK Video processing unit is available

    Raises:
        SystemExit: if no VPU device is detected or
                    the device node is not expected

    Reference:
        https://mediatek.gitlab.io/aiot/doc/aiot-dev-guide/master/sw/yocto/release-notes/aiot-yocto-v22.2-release-note.html
    """
    expected_device_pattern = [
        "mtk-vcodec-dec",
        "mtk-vcodec-enc",
        "mtk-mdp[0-9]*:m2m",
    ]

    check_result = []
    for pattern in expected_device_pattern:
        for dev_name in get_v4l2_devices():
            if re.search(pattern, dev_name):
                check_result.append(dev_name)
                logging.info("VPU %s device detected", dev_name)
                break

    if len(check_result) == len(expected_device_pattern):
        logging.info("# VPU devices check: Passed")
    else:
        raise SystemExit("# VPU devices check: Failed")


def main():
    """
    Detect Video processing unit is available

    Raises:
        SystemExit: if no VPU device is detected or
                    the device node is not expected
    """
    init_logger()
    supported_funcions = {
        "Freescale i.MX": check_imx_vpu_devices,
        "jep106:0426": check_mtk_vpu_devices,
    }

    family = get_soc_family()
    if family in supported_funcions.keys():
        supported_funcions.get(family)()
    else:
        logging.error("This %s SoC model is not supported", family)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
