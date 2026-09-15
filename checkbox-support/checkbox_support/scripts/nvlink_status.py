"""
Check the NVLink status of NVIDIA GPUs using ctypes bindings to libnvml.
"""

import argparse
import ctypes
import logging
import sys

logger = logging.getLogger(__name__)

# NVML return codes
# https://github.com/NVIDIA/nvidia-settings/blob/5b341a9e54f08ac324e148e1e7e102030e42b1c4/src/nvml.h#L1293
NVML_SUCCESS = 0
NVML_ERROR_NOT_SUPPORTED = 3

# NVLink links are typically numbered 0-5 on modern GPUs
NVLINK_MAX_LINKS = 6


def check_nv_link_status(missing_lib_result: bool = False) -> bool:
    """
    Check NVLink status using ctypes binding to libnvml.

    :param missing_lib_result: value to return when libnvidia-ml.so.1
                                can't be loaded, i.e. there is no NVIDIA
                                driver installed on the system.

    :returns: True if NVLink is active/detected on any GPU,
              False otherwise.
    """
    try:
        # Try to load the NVIDIA Management Library
        nvml = ctypes.CDLL("libnvidia-ml.so.1")
    except OSError:
        logger.info("libnvidia-ml.so.1 not found, assuming no NVLink")
        return missing_lib_result

    # Initialize NVML
    nvmlInit = nvml.nvmlInit_v2
    nvmlInit.restype = ctypes.c_int

    # https://github.com/NVIDIA/nvidia-settings/blob/5b341a9e54f08ac324e148e1e7e102030e42b1c4/src/nvml.h#L3974-L4000
    ret = nvmlInit()
    if ret != NVML_SUCCESS:
        logger.info("NVML initialization failed")
        return False

    try:
        # Get device count
        nvmlDeviceGetCount = nvml.nvmlDeviceGetCount_v2
        nvmlDeviceGetCount.argtypes = [ctypes.POINTER(ctypes.c_uint)]
        nvmlDeviceGetCount.restype = ctypes.c_int

        device_count = ctypes.c_uint()
        ret = nvmlDeviceGetCount(ctypes.byref(device_count))
        if ret != NVML_SUCCESS:
            return False

        # Check each device for NVLink
        # https://github.com/NVIDIA/nvidia-settings/blob/5b341a9e54f08ac324e148e1e7e102030e42b1c4/src/nvml.h#L4593-L4639
        nvmlDeviceGetHandleByIndex = nvml.nvmlDeviceGetHandleByIndex_v2
        nvmlDeviceGetHandleByIndex.argtypes = [
            ctypes.c_uint,
            ctypes.POINTER(ctypes.c_void_p),
        ]
        # https://github.com/NVIDIA/nvidia-settings/blob/5b341a9e54f08ac324e148e1e7e102030e42b1c4/src/nvml.h#L9486-L9504
        nvmlDeviceGetHandleByIndex.restype = ctypes.c_int

        nvmlDeviceGetNvLinkState = nvml.nvmlDeviceGetNvLinkState
        nvmlDeviceGetNvLinkState.argtypes = [
            ctypes.c_void_p,
            ctypes.c_uint,
            ctypes.POINTER(ctypes.c_uint),
        ]
        nvmlDeviceGetNvLinkState.restype = ctypes.c_int

        for i in range(device_count.value):
            handle = ctypes.c_void_p()
            ret = nvmlDeviceGetHandleByIndex(i, ctypes.byref(handle))
            if ret != NVML_SUCCESS:
                continue

            for link in range(NVLINK_MAX_LINKS):
                state = ctypes.c_uint()
                ret = nvmlDeviceGetNvLinkState(
                    handle, link, ctypes.byref(state)
                )
                # Skip if not supported
                if ret == NVML_ERROR_NOT_SUPPORTED:
                    continue
                # Check if link is active (state == 1)
                if ret == NVML_SUCCESS and state.value == 1:
                    return True

        return False
    finally:
        # Shutdown NVML
        nvml.nvmlShutdown()


def _args_parsing(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--missing-lib-exit-code",
        type=int,
        choices=[0, 1],
        default=1,
        help=(
            "Exit code to use when libnvidia-ml.so.1 can't be loaded, "
            "i.e. there is no NVIDIA driver installed. "
            "Defaults to 1 (same as 'NVLink not detected')."
        ),
    )
    return parser.parse_args(argv)


def main(argv=None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    args = _args_parsing(argv)

    # missing_lib_result is a bool, so map the requested exit code
    # (0 or 1) to what check_nv_link_status should return in that case:
    # exit code 0 means "NVLink detected" (True), exit code 1 means
    # "NVLink not detected" (False).
    missing_lib_result = args.missing_lib_exit_code == 0

    if check_nv_link_status(missing_lib_result):
        logger.info("NVLink detected")
        return 0

    logger.info("NVLink not detected")
    return 1


if __name__ == "__main__":
    sys.exit(main())
