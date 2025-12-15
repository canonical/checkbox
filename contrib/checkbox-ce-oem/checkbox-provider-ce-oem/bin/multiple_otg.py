#!/usr/bin/env python3

import argparse
import glob
import logging
import os
import subprocess
import tempfile
import time

from importlib import import_module
from importlib.machinery import SourceFileLoader
from multiprocessing import Process
from pathlib import Path
from rpyc_client import rpyc_client
from rpyc_test_methods import configure_local_network
from typing import Union

OTG_MODULE = "libcomposite"
CHECKBOX_RUNTIME = os.environ.get("CHECKBOX_RUNTIME", "")
CHECKBOX_BASE_PROVIDER = os.path.join(
    CHECKBOX_RUNTIME, "providers/checkbox-provider-base"
)


logging.basicConfig(level=logging.DEBUG)


def initial_configfs() -> Union[tempfile.TemporaryDirectory, Path]:
    """
    return a Path object with current mount point
        when the kernel configfs has been mounted
    Or return a TemporaryDirectory object and mount it as a kernel configfs

    Returns:
        Union[tempfile.TemporaryDirectory, Path]: kernel configfs directory
    """
    logging.info("initialize configfs")
    ret = subprocess.check_output("mount -t configfs", shell=True, text=True)
    if ret.strip():
        configfs_dir = Path(ret.split()[2])
        logging.info("kernel configfs has been mounted on %s", configfs_dir)
    else:
        configfs_dir = Path(tempfile.NamedTemporaryDirectory().name)
        subprocess.run("mount -t configfs none {}".format(configfs_dir.name))
        logging.info("mount configfs on %s", configfs_dir.name)
    return configfs_dir


class OtgConfigFsOperatorBase:
    """
    This is a object to setup the USB gadget to support different OTG scenario
    Reference https://www.kernel.org/doc/Documentation/usb/gadget_configfs.txt
    """

    OTG_FUNCTION = ""
    OTG_TARGET_MODULE = ""

    def __init__(self, root_path: Path, udc_path: str, usb_type: str):
        self._child_modules = self._get_child_modules()
        self.root_path = root_path
        self.usb_gadget_node = None
        self.udc_node = Path("/sys/class/udc").joinpath(udc_path)
        self.usb_type = usb_type

    def __enter__(self):
        logging.info("Setup the OTG configurations on %s UDC node", self.udc_node)
        if self._child_modules:
            logging.info(self._child_modules)
            # To clean up the OTG modules
            self.disable_otg_related_modules(self._child_modules)
        self.enable_otg_module([OTG_MODULE])
        self.usb_gadget_node = Path(
            tempfile.TemporaryDirectory(
                dir=self.root_path.joinpath("usb_gadget"), prefix="udc_"
            ).name
        )
        self.otg_setup()
        self.create_otg_configs()
        self.create_otg_function()
        return self

    def __exit__(self, exec, value, tb):
        logging.debug("Clean up OTG configurations")
        self._cleanup_usb_gadget()
        cur_modules = [
            mod for mod in self._get_child_modules() if mod not in self._child_modules
        ]
        self.disable_otg_related_modules(cur_modules)
        if self._child_modules:
            self.enable_otg_module(self._child_modules)
        self.otg_teardown()

    def _get_child_modules(self):
        output = subprocess.check_output(
            "lsmod | awk '/^libcomposite/ {print $4}'",
            shell=True,
            text=True,
            universal_newlines=True,
        )
        return output.strip("\n").split(",") if output.strip("\n") else []

    def enable_otg_module(self, modules):
        for module in modules:
            subprocess.run("modprobe {}".format(module), shell=True, check=True)

    def disable_otg_related_modules(self, modules):
        for module in modules:
            subprocess.run("modprobe -r {}".format(module), shell=True, check=True)

    def otg_setup(self):
        """
        This is function for doing any extra step for specific OTG function
        such as collecting ethernet interface, serial interface
             and create an USB image file
        """
        pass

    def otg_teardown(self):
        """
        This is function for doing any extra step for specific OTG function
        such as delete an USB image file
        """
        pass

    def create_otg_configs(self):
        logging.info("create USB gadget")
        path_lang = self.usb_gadget_node.joinpath("strings", "0x409")
        path_lang.mkdir()

        vid_file = self.usb_gadget_node.joinpath("idVendor")
        vid_file.write_text("0xabcd")
        pid_file = self.usb_gadget_node.joinpath("idProduct")
        pid_file.write_text("0x9999")

        # create configs
        udc_configs = self.usb_gadget_node.joinpath("configs", "c.1")
        udc_configs.mkdir()
        max_power_file = udc_configs.joinpath("MaxPower")
        max_power_file.write_text("120")

    def create_otg_function(self):
        logging.info("create function")
        self.enable_otg_module([self.OTG_TARGET_MODULE])
        func_name = "{}.0".format(self.OTG_FUNCTION)
        function_path = self.usb_gadget_node.joinpath("functions", func_name)

        if not function_path.exists():
            function_path.mkdir()

        self.usb_gadget_node.joinpath("configs", "c.1", func_name).symlink_to(
            function_path, True
        )

    def _cleanup_usb_gadget(self):
        func_name = "{}.0".format(self.OTG_FUNCTION)
        self.usb_gadget_node.joinpath("strings", "0x409").rmdir()
        self.usb_gadget_node.joinpath("configs", "c.1", func_name).unlink(True)
        self.usb_gadget_node.joinpath("configs", "c.1").rmdir()
        self.usb_gadget_node.joinpath("functions", func_name).rmdir()
        self.usb_gadget_node.rmdir()

    def enable_otg(self):
        if self.udc_node.exists():
            self.usb_gadget_node.joinpath("UDC").write_text(self.udc_node.name)
        else:
            logging.error("UDC node '%s' not exists", self.udc_node)
            raise ValueError(self.udc_node)

    def disable_otg(self):
        self.usb_gadget_node.joinpath("UDC").write_text("")

    def self_check(self):
        """ensure the USB device been generated.

        Returns:
            bool: return True when a USB device been detected
        """
        logging.debug("check")
        return True

    def detection_check_on_rpyc(self, rpyc_ip):
        """
        This is a function to detect OTG device on client
        """
        pass

    def function_check_with_rpyc(self, rpyc_ip):
        """
        this is a function to perform OTG testing on client
        """
        pass


class OtgMassStorageSetup(OtgConfigFsOperatorBase):

    OTG_FUNCTION = "mass_storage"
    OTG_TARGET_MODULE = "usb_f_mass_storage"

    def otg_setup(self):
        """
        This is function for doing any extra step for specific OTG function
        such as collecting ethernet interface, serial interface
             and create an USB storage
        """
        logging.info("Create an USB image file for Mass Storage Test")
        self._usb_img = tempfile.NamedTemporaryFile("+bw", delete=False)
        subprocess.run(
            "dd if=/dev/zero of={} bs=1M count=1024".format(self._usb_img.name),
            shell=True,
            check=True,
        )
        subprocess.run(
            "mkdosfs -F 32 {}".format(self._usb_img.name),
            shell=True,
            check=True,
        )
        logging.info("%s file been created", self._usb_img.name)

    def otg_teardown(self):
        logging.info("Delete USB image file from %s", self._usb_img.name)
        os.remove(self._usb_img.name)

    def create_otg_function(self):
        logging.info("create function")
        self.enable_otg_module([self.OTG_TARGET_MODULE])
        func_name = "{}.0".format(self.OTG_FUNCTION)
        function_path = self.usb_gadget_node.joinpath("functions", func_name)

        if not function_path.exists():
            function_path.mkdir()

        function_path.joinpath("lun.0", "file").write_text(self._usb_img.name)

        self.usb_gadget_node.joinpath("configs", "c.1", func_name).symlink_to(
            function_path, True
        )

    def detection_check_on_rpyc(self, rpyc_ip):
        logging.info("USB drive detection on RPYC")
        mounted_drive = rpyc_client(rpyc_ip, "usb_drive_check", self.usb_type)
        if mounted_drive:
            logging.info(
                "Found USB device and mounted as '%s' on rpyc server",
                mounted_drive,
            )
        else:
            raise RuntimeError("No USB device found on rpyc server")
        self._target_dev = mounted_drive

    def function_check_with_rpyc(self, rpyc_ip):
        logging.info("USB read/write testing on RPYC")
        raise SystemExit(
            rpyc_client(
                rpyc_ip,
                "usb_storage_test",
                self.usb_type,
            )
        )

    def otg_test_process(self, rpyc_ip):
        logging.info("Start Mass Storage Testing with OTG interface")
        t_thread = Process(target=self.function_check_with_rpyc, args=(rpyc_ip,))
        t_thread.start()
        logging.debug("Launch USB detection and storage tests on RPYC server")
        # Sleep few seconds to activate USB detection on RPYC server
        time.sleep(3)
        self.enable_otg()
        t_thread.join()
        self.disable_otg()

        if t_thread.exitcode == 0:
            logging.info("OTG Mass Storage test passed")
        else:
            logging.debug("Exit code: %s", t_thread.exitcode)
            raise RuntimeError("OTG Mass Storage test failed")


class OtgEthernetSetup(OtgConfigFsOperatorBase):

    OTG_FUNCTION = "ecm"
    OTG_TARGET_MODULE = "usb_f_ecm"

    def _collect_net_intfs(self):
        return [os.path.basename(intf) for intf in glob.glob("/sys/class/net/*")]

    def otg_setup(self):
        self._net_intfs = self._collect_net_intfs()

    def self_check(self):
        """
        Ensure the ethernet device been generated by usb gadget

        Returns:
            bool: Return True when an USB Ethernet interface been detected
        """
        logging.info("Validate a new network interface been generated")
        cur_net_intfs = self._collect_net_intfs()
        if len(cur_net_intfs) == len(self._net_intfs):
            raise RuntimeError("OTG network interface not available")

        otg_net_intf = [x for x in cur_net_intfs if x not in self._net_intfs]
        if len(otg_net_intf) != 1:
            logging.error("Found more than one new interface. %s", otg_net_intf)
        else:
            logging.info("Found new network interface '%s'", otg_net_intf[0])
        self._net_dev = otg_net_intf[0]

    def detection_check_on_rpyc(self, rpyc_ip):
        logging.info("Network interface detection on RPYC")
        ret = rpyc_client(rpyc_ip, "ethernet_check")
        if ret:
            logging.info("Found %s network interface on rpyc server", ret)
        else:
            raise RuntimeError("No network interface found on rpyc server")
        self._target_net_dev = list(ret)[0]

    def function_check_with_rpyc(self, rpyc_ip):
        configure_local_network(self._net_dev, "169.254.0.1/24")
        logging.info("Configure the %s network on RPYC", self._target_net_dev)
        rpyc_client(
            rpyc_ip,
            "configure_local_network",
            self._target_net_dev,
            "169.254.0.10/24",
        )
        logging.info("Ping from DUT to Target")
        _module = SourceFileLoader(
            "_",
            os.path.join(CHECKBOX_BASE_PROVIDER, "bin/gateway_ping_test.py"),
        ).load_module()
        test_func = getattr(_module, "perform_ping_test")
        ret = test_func([self._net_dev], "169.254.0.10")
        if ret != 0:
            raise RuntimeError("Failed to ping DUT from RPYC server")

    def otg_test_process(self, rpyc_ip):
        self.enable_otg()
        self.self_check()
        self.detection_check_on_rpyc(rpyc_ip)
        self.function_check_with_rpyc(rpyc_ip)
        self.disable_otg()


class OtgSerialSetup(OtgConfigFsOperatorBase):

    OTG_FUNCTION = "acm"
    OTG_TARGET_MODULE = "usb_f_acm"

    def _collect_serial_intfs(self):
        return [os.path.basename(intf) for intf in glob.glob("/dev/ttyGS*")]

    def otg_setup(self):
        self._ser_intfs = self._collect_serial_intfs()

    def self_check(self):
        """
        Ensure a Serial device been generated by usb gadget

        Returns:
            bool: Return True when a Serial interface been detected
        """
        logging.info("Validate a new serial interface been generated")
        cur_ser_intfs = self._collect_serial_intfs()
        if len(cur_ser_intfs) == len(self._ser_intfs):
            raise RuntimeError("OTG network interface not available")

        otg_ser_intf = [x for x in cur_ser_intfs if x not in self._ser_intfs]
        if len(otg_ser_intf) != 1:
            logging.error("Found more than one new interface. %s", otg_ser_intf)
        else:
            logging.info("Found new network interface '%s'", otg_ser_intf[0])
        self._serial_iface = otg_ser_intf[0]

    def detection_check_on_rpyc(self, rpyc_ip):
        ret = rpyc_client(rpyc_ip, "serial_check")
        if ret:
            logging.info("Found %s serial interface on rpyc server", ret)
        else:
            logging.debug("No serial interface found on rpyc server")
        self._target_serial_dev = list(ret)[0]

    def function_check_with_rpyc(self, rpyc_ip):
        logging.info("perform serial client test on DUT")
        func = getattr(import_module("serial_test"), "client_mode")
        func(
            "/dev/{}".format(self._serial_iface),
            "USB",
            [],
            115200,
            8,
            "N",
            1,
            3,
            1024,
        )

    def otg_test_process(self, rpyc_ip):
        self.enable_otg()
        self.self_check()
        self.detection_check_on_rpyc(rpyc_ip)

        try:
            logging.info("start serial server on rpyc server")
            t_thread = Process(
                target=rpyc_client,
                args=(
                    rpyc_ip,
                    "enable_serial_server",
                    "/dev/serial/by-id/{}".format(self._target_serial_dev),
                    "USB",
                    [],
                    115200,
                    8,
                    "N",
                    1,
                    3,
                    1024,
                ),
            )
            t_thread.start()
            time.sleep(3)
            self.function_check_with_rpyc(rpyc_ip)
        except SystemExit as err:
            logging.debug(err)
        finally:
            t_thread.kill()
        self.disable_otg()


OTG_TESTING_MAPPING = {
    "mass_storage": OtgMassStorageSetup,
    "ethernet": OtgEthernetSetup,
    "serial": OtgSerialSetup,
}


def otg_testing(udc_node, test_func, rpyc_ip, usb_type):
    configfs_dir = initial_configfs()
    with OTG_TESTING_MAPPING[test_func](configfs_dir, udc_node, usb_type) as otg_cfg:
        otg_cfg.otg_test_process(rpyc_ip)


def dump_otg_info(configs):
    for config in configs.split():
        otg_conf = config.split(":")
        if len(otg_conf) == 3:
            print("USB_CONNECTOR: {}".format(otg_conf[0]))
            print("UDC_NODE: {}".format(otg_conf[1]))
            print("USB_TYPE: {}".format(otg_conf[2]))
            print()


def register_arguments():
    parser = argparse.ArgumentParser(description="OTG test method")

    sub_parser = parser.add_subparsers(
        dest="mode",
        required=True,
    )
    test_parser = sub_parser.add_parser("test")
    test_parser.add_argument(
        "-t",
        "--type",
        required=True,
        choices=["mass_storage", "ethernet", "serial"],
    )
    test_parser.add_argument("-u", "--udc-node", required=True, type=str)
    test_parser.add_argument(
        "--usb-type", default="usb2", type=str, choices=["usb2", "usb3"]
    )
    test_parser.add_argument("--rpyc-address", required=True, type=str)

    info_parser = sub_parser.add_parser("info")
    info_parser.add_argument("-c", "--config", required=True, type=str)

    return parser.parse_args()


def main():
    args = register_arguments()
    if args.mode == "test":
        otg_testing(args.udc_node, args.type, args.rpyc_address, args.usb_type)
    elif args.mode == "info":
        dump_otg_info(args.config)


if __name__ == "__main__":
    main()
