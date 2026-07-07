#!/usr/bin/env python3
import subprocess
import argparse
import shlex
import sys
import glob
import logging
import os

logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
    ],
)


def run_cmd(command):
    try:
        logging.info("Executing command: '{}'".format(command))
        ret = subprocess.run(
            shlex.split(command),
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding="utf-8",
        )
        return ret
    except subprocess.CalledProcessError as e:
        logging.error("Error while running {0}:".format(e.cmd))
        logging.error(e.output)
        raise


def read_file(path):
    """Read the content of a file"""
    try:
        with open(path, "r") as file:
            return file.read().strip()
    except Exception as e:
        logging.error(f"Failed to read {path}: {e}")
        raise


def check_soc_info():
    """Check if soc info matches the device"""

    soc_path = "/sys/devices/soc0/"
    soc_files = {"family": "family", "machine": "machine", "soc_id": "soc_id"}
    soc_info = {
        "family": "Snapdragon",
        "machine": (
            "Qualcomm Technologies, Inc. "
            "Robotics RB3gen2 addons vision mezz platform"
        ),
        "soc_id": "498",
    }

    for key, file in soc_files.items():
        ret = run_cmd("cat {}{}".format(soc_path, file)).stdout.strip()
        if ret != soc_info[key]:
            logging.error(
                "{} does not match: expected {}, got {}".format(
                    key, soc_info[key], ret
                )
            )
            sys.exit(1)

    logging.info("SoC info matches.")
    sys.exit(0)


def check_cpu_online():
    """Check if all CPUs are online."""

    cpu_files = glob.glob("/sys/devices/system/cpu/cpu*/online")

    offline_cpus = []
    for cpu in cpu_files:
        status = read_file(cpu)
        if status != "1":
            offline_cpus.append(cpu)

    if offline_cpus:
        logging.error(f"CPUs offline: {offline_cpus}")
        sys.exit(1)

    logging.info("All CPUs are online.")
    sys.exit(0)


def check_zram_enablement():
    """Check if zram is enabled"""

    expected_configs = {
        "CONFIG_ZRAM=m",
        "CONFIG_ZRAM_DEF_COMP_LZORLE=y",
        'CONFIG_ZRAM_DEF_COMP="lzo-rle"',
    }

    kernel = os.uname().release
    config_file = "/boot/config-{}".format(kernel)

    logging.info("checking zram configs in {} ...".format(config_file))
    configs = read_file(config_file).splitlines()
    missing_configs = expected_configs - set(configs)
    if missing_configs:
        logging.error("Missing zram configs:")
        for c in missing_configs:
            logging.error(c)
        sys.exit(1)

    logging.info("All configs are set")

    # check if device exist
    logging.info("checking device node /dev/zram0 ...")
    if not os.path.exists("/dev/zram0"):
        logging.error("zram device is not exist!")
        sys.exit(1)

    # check if zram is working
    logging.info("checking zram status ...")
    cmd = "grep /dev/zram0 /proc/swaps"
    try:
        ret = run_cmd(cmd).stdout.strip()
        logging.info(ret)
        logging.info("zram is working")
        sys.exit(0)
    except Exception:
        logging.error("zram is not woring")
        sys.exit(1)


def check_dmabuf():
    """Check if dmabuf is enabled"""

    expected_configs = {
        "CONFIG_UDMABUF=y",
        "CONFIG_DMABUF_MOVE_NOTIFY=y",
        "CONFIG_DMABUF_HEAPS=y",
        "CONFIG_DMABUF_HEAPS_SYSTEM=y",
        "CONFIG_DMABUF_HEAPS_CMA=y",
        "CONFIG_QCOM_DMABUF_HEAPS=y",
        "CONFIG_QCOM_DMABUF_HEAPS_SYSTEM=y",
        "CONFIG_QCOM_DMABUF_HEAPS_SYSTEM_SECURE=y",
        "CONFIG_QCOM_DMABUF_HEAPS_CMA=y",
        "CONFIG_XEN_GNTDEV_DMABUF=y",
    }

    kernel = os.uname().release
    config_file = "/boot/config-{}".format(kernel)

    logging.info("checking dambuf configs in {} ...".format(config_file))
    configs = read_file(config_file).splitlines()

    missing_configs = expected_configs - set(configs)
    if missing_configs:
        logging.error("Missing dmabuf configs:")
        for c in missing_configs:
            logging.error(c)
        sys.exit(1)

    logging.info("All configs are set")

    # check dmabuf dir exist
    for path in ["/dev/dma_heap", "/sys/class/dma_heap"]:
        logging.info(f"Checking dir {path}...")
        if not os.path.exists(path):
            logging.error(f"{path} does not exist!")
            sys.exit(1)

    logging.info("All dmabuf checks passed.")


def pinctrl_support():
    """Check if pinctrl GPIO config files exist."""

    power_dir = (
        "/sys/devices/platform/soc@0/f100000.pinctrl/gpio/gpiochip547/power"
    )
    uevent_file = (
        "/sys/devices/platform/soc@0/f100000.pinctrl/gpio/gpiochip547/uevent"
    )

    if not (os.path.isdir(power_dir) and os.path.isfile(uevent_file)):
        logging.error("Missing pinctrl config files.")
        sys.exit(1)

    logging.info("Pinctrl config files found.")
    sys.exit(0)


def check_cpu_interrupts():
    """Check interrupt has all 8 cpus."""

    cmd = "head -n 1 /proc/interrupts"
    ret = run_cmd(cmd).stdout.strip().split()
    if len(ret) != 8:
        logging.error("only {} CPUs are listed.".format(len(ret)))
        sys.exit(1)

    logging.info("all CPUs are listed.")
    sys.exit(0)


def check_remoteproc():
    """Check if remoteproc info matchs and make sure it's runing"""

    expected = {
        # adsp
        "3000000.remoteproc": {
            "firmware": "qcom/qcs6490/adsp.mbn",
            "state": "running",
        },
        # cdsp
        "a300000.remoteproc": {
            "firmware": "qcom/qcs6490/cdsp.mbn",
            "state": "running",
        },
        # wpss
        "8a00000.remoteproc": {
            "firmware": "qcom/qcs6490/wpss.mbn",
            "state": "running",
        },
    }

    remoteproc_dirs = glob.glob("/sys/class/remoteproc/remoteproc*")
    for rp in remoteproc_dirs:
        name = read_file("{}/name".format(rp))
        if name in expected:
            # get firmware and state
            fw = read_file("{}/firmware".format(rp))
            state = read_file("{}/state".format(rp))
            # check if firmware and state match the expected for this rp
            if (
                fw == expected[name]["firmware"]
                and state == expected[name]["state"]
            ):
                logging.info(
                    "{} found, firmware: {}, state: {}".format(name, fw, state)
                )
                del expected[name]
            else:
                logging.error(
                    "{} mismatch, firmware: {}, state: {}".format(
                        name, fw, state
                    )
                )
                sys.exit(1)

    # check if all remoteproc are exist
    if expected:
        logging.error(
            "Missing remoteprocs: {}".format(", ".join(expected.keys()))
        )
        sys.exit(1)

    logging.info("All remoteproc checks passed.")
    sys.exit(0)


def main():
    commands = {
        "check-soc-info": check_soc_info,
        "check-cpu-online": check_cpu_online,
        "pinctrl-support": pinctrl_support,
        "check-remoteproc": check_remoteproc,
        "check-cpu-interrupts": check_cpu_interrupts,
        "check-zram-enablement": check_zram_enablement,
        "check-dmabuf": check_dmabuf,
    }
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "subcommand", help=("subcommand to run"), choices=commands.keys()
    )
    args = parser.parse_args()

    commands[args.subcommand]()


if __name__ == "__main__":
    main()
