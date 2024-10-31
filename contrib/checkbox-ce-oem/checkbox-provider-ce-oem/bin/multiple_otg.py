import logging
import os
import subprocess

from contextlib import contextmanager
from pathlib import Path


MODULE_MAPPING = {
    "usb": "usb_f_mass_storage",
    "ethernet": "usb_f_ecm",
    "serial": "usb_f_acm",
}
OTG_MODULE = "libcomposite"
GADGET_PATH = "/sys/kernel/config/usb_gadget"


def _get_otg_module():
    ret = subprocess.run(
        "lsmod | grep {}".format(OTG_MODULE),
        shell=True,
        universal_newlines=True
    )
    return ret.stdout.strip()


def enable_otg_module():
    disable_otg_related_modules()

    if not _get_otg_module():
        subprocess.run("modprode {}".format(OTG_MODULE))


def disable_otg_related_modules():
    ret = subprocess.run("lsmod | awk '/^libcomposite/ {print $4}'")
    if ret.returncode == 0:
        for module in ret.stdout.split(","):
            subprocess.run("modprobe -r {}".format(module))


def _initial_gadget():
    logging.info("initial gadget")
    enable_otg_module()

    ret = subprocess.run("mount | configfs")
    if not ret.stdout.strip():
        subprocess.run(
            "mount -t configfs none {}".format(os.path.split(GADGET_PATH))
        )

def _create_otg_configs():
    logging.info("create gadget")
    path_g1 = os.path.join(GADGET_PATH, "g1")
    os.makedirs(path_g1)

    path_lang = os.path.join(path_g1, "strings", "0x409") # english lang
    os.makedirs(path_lang)

    path_g1 = Path(path_g1)
    vid_file = path_g1.joinpath("idVendor")
    vid_file.write_text("0xabcd")
    pid_file = path_g1.joinpath("idProduct")
    pid_file.write_text("0x9999")

    # create configs
    path_config = path_g1.joinpath("configs", "c.1")
    os.makedirs(path_config)

    max_power_file = path_config.joinpath("MaxPower")
    max_power_file.write_text("120")


def otg_testing(method):
    pass


def teardown():
    pass

@contextmanager
def prepare_env():
    try:
        _initial_gadget()
        _create_otg_configs()
    except Exception as err:
        logging.error(err)
    finally:
        teardown()


def main():
    with prepare_env():
        otg_testing()


if __name__ == "__main__":
    main()