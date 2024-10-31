import argparse
import glob
import logging
import os
import re
import shutil
import subprocess
import tempfile

from contextlib import contextmanager
from pathlib import Path
from rpyc_client import rpyc_client


MODULE_MAPPING = {
    "usb": "usb_f_mass_storage",
    "ethernet": "usb_f_ecm",
    "serial": "usb_f_acm",
}
OTG_MODULE = "libcomposite"
GADGET_PATH = "/sys/kernel/config/usb_gadget"
UDC_G1_NODE = Path(GADGET_PATH).joinpath("g1")
UDC_CONFIG = UDC_G1_NODE.joinpath("configs", "c.1")
UDC_NODE = UDC_G1_NODE.joinpath("UDC")


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
    os.makedirs(UDC_G1_NODE.name)

    path_lang = UDC_G1_NODE.joinpath("strings", "0x409")
    os.makedirs(path_lang.name) # english language

    vid_file = UDC_G1_NODE.joinpath("idVendor")
    vid_file.write_text("0xabcd")
    pid_file = UDC_G1_NODE.joinpath("idProduct")
    pid_file.write_text("0x9999")

    # create configs
    os.makedirs(UDC_CONFIG.name)
    max_power_file = UDC_CONFIG.joinpath("MaxPower")
    max_power_file.write_text("120")


def _create_function(function):
    logging.info("create function")
    subprocess.run("modprobe usb_f_{}".format(function))
    function_path = UDC_G1_NODE.joinpath("functions", "{}.0".format(function))

    if not os.path.isdir(function_path):
        os.makedirs(function_path)

    if function == "mass_storage":
        with tempfile.TemporaryDirectory() as tmp_dir:
            img = os.path.join(tmp_dir, "lun0.img")
            subprocess.run("dd if=/dev/zero of={} bs=1M count=16".format(img))
            subprocess.run("mkdosfs -F 32 {}".format(img))

            with open(os.path.join(function_path, "lun.0", "file"), "w") as f:
                f.write(img)

    os.symlink(
        function_path,
        UDC_CONFIG.joinpath("{}.0".format(function)).name
        )


def otg_testing(method):
    pass


def _identify_udc_bus(otg_bus, udc_list):
    for udc in udc_list:
        if udc in otg_bus:
            return udc
        elif glob.glob(
            "/sys/devices/platform/**/{}/{}*".format(udc, otg_bus)
        ):
            return udc
    return "None"


def dump_otg_info(configs):
    otg_nodes = glob.glob(
        "/sys/firmware/devicetree/base/**/dr_mode", recursive=True
    )
    udc_list = [os.path.basename(f) for f in glob.glob("/sys/class/udc/*")]
    otg_mapping = {}
    for node in otg_nodes:
        mode = Path(node).read_text().strip()
        usb_bus = re.search(r"usb@([a-z0-9]*)", node)
        otg_mapping[usb_bus] = mode

    for config in configs.split():
        otg_conf = config.split(":")
        if len(otg_conf) == 2:
            udc_bus = _identify_udc_bus(otg_conf[1], udc_list)
            print("USB_port: {}".format(otg_conf[0]))
            print("USB_node: {}".format(otg_conf[1]))
            print("Mode: {}".format(otg_mapping.get(config[0], "")))
            print("UDC: {}".format(udc_bus))
            print()


class ConfigFsOperator(tempfile.TemporaryDirectory):

    def __enter__(self):
        subprocess.run(
            "mount -t configfs none {}".format(self.name),
            shell=True,
            check=True
        )
        super.__init__()

    def __exit__(self, exc, value, tb):
        subprocess.run("umount {}".format(self.name))
        super.__exit__(exc, value, tb)

    def create_otg_gadget(self):
        gadget_root = Path(self.name, "usb_gadget")
        gadget_root.mkdir()
        self.gadget_node = gadget_root.joinpath("g1")
        self.gadget_node.mkdir()

        # create PID and VID file
        self.gadget_node.joinpath("idVendor").write_text("0xabcd")
        self.gadget_node.joinpath("idProduct").write_text("0x9999")

        # create serial no, manufacture and product
        string_dir = self.gadget_node.joinpath("strings")
        string_dir.mkdir()
        lang_dir = string_dir.joinpath("0x409")
        lang_dir.mkdir()
        lang_dir.joinpath("serialnumber").write_text("1234567")
        lang_dir.joinpath("manufacturer").write_text("canonical")
        lang_dir.joinpath("product").write_text("otg_device")

    def create_otg_config(self):
        config_root = self.gadget_node.joinpath("configs")
        config_root.mkdir()
        config_node = config_root.joinpath("c.1")
        config_node.mkdir()

        config_node.joinpath("MaxPower").write_text("120")
        string_dir = config_node.joinpath("strings")
        string_dir.mkdir()
        lang_dir = string_dir.joinpath("0x409")
        lang_dir.mkdir()
        lang_dir.joinpath("configuration").write_text("otg")

    def create_otg_function(self):
        pass

class OtgTestBase():
    """
    This is a object to setup the USB gadget to support different OTG scenario
    Reference https://www.kernel.org/doc/Documentation/usb/gadget_configfs.txt
    """
    def __init__(self, bus_addr):
        self._addr = bus_addr

    def _get_related_libcomposite_modules(self):
        ret = subprocess.run("lsmod | awk '/^libcomposite/ {print $4}'")
        if ret.returncode == 0:
            return ret.stdout.split(",")
        return []

    def _enable_libcomposite_module(self):
        modules = self._get_related_libcomposite_modules()
        if modules:
            # libcomposite module has been loaded, unload corresponding module
            for module in modules:
                subprocess.run("modprobe -r {}".format(module), check=True)
        else:
            # load libcomposite
            subprocess.run("modprobe {}".format(module), check=True)

    def _identify_configfs_dir(self):


    def _pre_setup_env(self):
        self._enable_libcomposite_module()

    def create_gadget(self):
        pass

    def create_config(self):
        pass

    def create_function(self):
        pass

    def associate_function_and_config(self):
        pass

    def enable_gadget(self):
        pass

    def disable_gadget(self):
        pass

    def clean_up(self):
        pass


class OtgTest():

    def __init__(self, mode, address):
        self._mode = mode
        self._address = address

    def __enter__(self):
        self._prepare_env()

    def __exit__(self):
        try:
            UDC_NODE.write_text("")
            shutil.rmtree(GADGET_PATH)
        except Exception as err:
            logging.error(err)

    def _prepare_env(self):
        _initial_gadget()
        _create_otg_configs()
        _create_function(self._mode)

    def activate_otg(self):
        # Activate OTG
        UDC_NODE.write_text(self._address)

    @classmethod
    def mass_storage(cls, type, address):
        rpyc_client()

    def ethernet(self, type, address):
        pass

    def serial(self, type, address):
        pass


def register_arguments():
    parser = argparse.ArgumentParser(
        description="OTG test method"
    )

    sub_parser = parser.add_subparsers(
        dest="mode",
        required=True,
    )
    test_parser = sub_parser.add_parser("test")
    test_parser.add_argument(
        "-t",
        "--type",
        required=True,
        choices=["mass_storage", "ethernet", "serial"]
    )
    test_parser.add_argument("-a", "--address", required=True, type=str)

    info_parser = sub_parser.add_parser("info")
    info_parser.add_argument("-c", "--config", required=True, type=str)

    return parser.parse_args()


def main():
    args = register_arguments()
    if args.mode == "test":
        with prepare_env():
            getattr(OtgTest, args.type)(args.type, args.address)
    elif args.mode == "info":
        dump_otg_info(args.config)


if __name__ == "__main__":
    main()