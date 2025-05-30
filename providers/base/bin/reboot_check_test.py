#!/usr/bin/env python3

import argparse
import os
import subprocess as sp
import re
import shutil
import filecmp
import sys
import typing as T
from checkbox_support.scripts.image_checker import has_desktop_environment
from datetime import datetime
import time


# Checkbox could run in a snap container, so we need to prepend this root path
RUNTIME_ROOT = os.getenv("CHECKBOX_RUNTIME", default="")
# Snap mount point, see
# https://snapcraft.io/docs/environment-variables#heading--snap
SNAP = os.getenv("SNAP", default="")


def get_timestamp_str() -> str:
    with open("/proc/uptime", "r") as f:
        # uptime file always have 2 numbers
        # uptime_seconds total_idle_seconds
        # take the 1st one
        uptime_seconds = f.readline().split()[0]

    return "Time: {}; Uptime: {} seconds".format(
        datetime.now().strftime("%m/%d/%Y, %H:%M:%S"), uptime_seconds
    )


def get_current_boot_id() -> str:
    with open("/proc/sys/kernel/random/boot_id", "r") as f:
        # the boot_id file has a Version 4 UUID with hypens
        # journalctl doesn't use hypens so we just remove it
        return f.read().strip().replace("-", "")


class DeviceInfoCollector:

    class Device:
        PCI = "pci"
        WIRELESS = "wireless"
        USB = "usb"
        DRM = "drm"

    DEFAULT_DEVICES = {
        "required": [
            Device.WIRELESS,
            Device.PCI,
            Device.USB,
        ],  # these can fail the test case
        "optional": [Device.DRM],  # these only produce warnings
    }  # type: dict[str, list[str]]
    # to modify, add more values in the enum
    # and reference them in required/optional respectively

    COMMAND_TIMEOUT_SECONDS = 30

    def get_drm_info(self) -> str:
        return str(sorted(os.listdir("/sys/class/drm")))

    def get_wireless_info(self) -> str:
        iw_out = sp.check_output(
            ["iw", "dev"],
            timeout=self.COMMAND_TIMEOUT_SECONDS,
            universal_newlines=True,
        )
        lines = iw_out.splitlines()
        lines_to_write = list(
            filter(
                lambda line: "addr" in line
                or "Interface" in line
                or "ssid" in line,
                sorted(lines),
            )
        )
        return "\n".join(map(lambda line: line.strip(), lines_to_write))

    def get_usb_info(self) -> str:
        out = sp.check_output(
            [
                "checkbox-support-lsusb",
                "-f",
                '"{}"/var/lib/usbutils/usb.ids'.format(RUNTIME_ROOT),
                "-s",
            ],
            universal_newlines=True,
            timeout=self.COMMAND_TIMEOUT_SECONDS,
        ).splitlines()
        out.sort()
        return "\n".join(out)

    def get_pci_info(self) -> str:
        return sp.check_output(
            ["lspci", "-i", "{}/usr/share/misc/pci.ids".format(SNAP)],
            timeout=self.COMMAND_TIMEOUT_SECONDS,
            universal_newlines=True,
        )

    def compare_device_lists(
        self,
        expected_dir: str,
        actual_dir: str,
        devices: T.Dict[str, T.List[str]] = DEFAULT_DEVICES,
    ) -> bool:
        """Compares the list of devices in expected_dir against actual_dir

        :param expected_dir: files containing the expected device list
        :param actual_dir: files containing the actual device list
        :param devices: what devices do we want to compare, see DEFAULT_DEVICES
        :return: whether the device list matches
        """
        print(
            "Comparing devices in (expected) {} against (actual) {}...".format(
                expected_dir, actual_dir
            )
        )
        for device in devices["required"]:
            # file paths of the expected and actual device lists
            expected = "{}/{}_log".format(expected_dir, device)
            actual = "{}/{}_log".format(actual_dir, device)
            if not filecmp.cmp(expected, actual):
                print(
                    "[ ERR ] The output of {} differs!".format(device),
                    file=sys.stderr,
                )
                self.print_diff(device, expected, actual)
                return False

        for device in devices["optional"]:
            expected = "{}/{}_log".format(expected_dir, device)
            actual = "{}/{}_log".format(actual_dir, device)
            if not filecmp.cmp(expected, actual):
                print(
                    "[ WARN ] Items under {} have changed.".format(actual),
                    file=sys.stderr,
                )
                self.print_diff(device, expected, actual)

        return True

    def dump(
        self,
        output_directory: str,
        devices: T.Dict[str, T.List[str]] = DEFAULT_DEVICES,
    ) -> None:
        os.makedirs(output_directory, exist_ok=True)
        # add extra behavior if necessary
        for device in devices["required"]:
            with open(
                "{}/{}_log".format(output_directory, device), "w"
            ) as file:
                file.write(self.dump_function[device]())

        for device in devices["optional"]:
            with open(
                "{}/{}_log".format(output_directory, device), "w"
            ) as file:
                file.write(self.dump_function[device]())

        os.sync()

    def print_diff(self, name: str, expected_path: str, actual_path: str):
        with open(expected_path) as file_expected, open(
            actual_path
        ) as file_actual:
            print("Expected {} output:".format(name), file=sys.stderr)
            print(file_expected.read(), file=sys.stderr)
            print("Actual {} output:".format(name), file=sys.stderr)
            print(file_actual.read(), file=sys.stderr)
            print("End of {} diff".format(name), file=sys.stderr)

    def __init__(self) -> None:
        self.dump_function = {
            self.Device.PCI: self.get_pci_info,
            self.Device.DRM: self.get_drm_info,
            self.Device.USB: self.get_usb_info,
            self.Device.WIRELESS: self.get_wireless_info,
        }


class FwtsTester:
    def is_fwts_supported(self) -> bool:
        return shutil.which("fwts") is not None

    def fwts_log_check_passed(
        self, output_directory: str, fwts_arguments=["klog", "oops"]
    ) -> bool:
        """
        Check if fwts logs passes the checks specified in sleep_test_log_check
        This script live in the same directory

        :param output_directory: where the output of fwts should be written to
        :type output_directory: str
        :return: whether sleep_test_log_check.py returned 0 (success)
        :rtype: bool
        """
        log_file_path = "{}/fwts_{}.log".format(
            output_directory, "_".join(fwts_arguments)
        )
        sp.run(["fwts", "-r", log_file_path, "-q", *fwts_arguments])
        result = sp.run(
            [
                "sleep_test_log_check.py",
                "-v",
                "--ignore-warning",
                "-t",
                "all",
                log_file_path,
            ],
        )

        return result.returncode == 0


class HardwareRendererTester:

    def has_display_connection(self) -> bool:
        """
        Checks if a display is connected by searching /sys/class/drm

        :return: True if there's at least 1 node that is connected
        """

        # look for GPU file nodes first
        DRM_PATH = "/sys/class/drm"
        possible_gpu_nodes = [
            directory
            for directory in os.listdir(DRM_PATH)
            if directory != "version"
        ]
        if len(possible_gpu_nodes) == 0:
            # kernel doesn't see any GPU nodes
            print(
                "There's nothing under {}".format(DRM_PATH),
                "if an external GPU is connected,"
                "check if the connection is loose.",
            )
            return False

        print("Listing all DRM connection statuses:")

        connected_to_display = False
        for gpu in possible_gpu_nodes:
            # for each gpu, check for connection
            # return true if anything is connected
            try:
                with open("{}/{}/status".format(DRM_PATH, gpu)) as status_file:
                    status_str = status_file.read().strip().lower()
                    # - card0: connected
                    print(" - {}: {}".format(gpu, status_str))

                    if status_str == "connected":
                        connected_to_display = True
            except FileNotFoundError:
                # this just means we don't have a status file
                # => no connection, continue to the next
                pass
            except Exception as e:
                print("Unexpected error: ", e, file=sys.stderr)

        if not connected_to_display:
            print(
                "No display is connected. This case will be skipped.",
                "Maybe the display cable is not connected?",
                "If the device is not supposed to have a display,"
                "then skipping is expected.",
            )

        return connected_to_display

    def is_hardware_renderer_available(self) -> bool:
        """
        Checks if hardware rendering is being used.
        THIS ASSUMES A DRM CONNECTION EXISTS
        - self.has_display_connection() should be called first if unsure

        :return: True if a hardware renderer is active, otherwise return False
        :rtype: bool
        """

        DISPLAY = os.getenv("DISPLAY", "")

        if DISPLAY == "":
            print("$DISPLAY is not set, we will let unity_support infer this")
        else:
            print("Checking $DISPLAY={}".format(DISPLAY))

        unity_support_output = sp.run(
            ["{}/usr/lib/nux/unity_support_test".format(RUNTIME_ROOT), "-p"],
            stdout=sp.PIPE,
            universal_newlines=True,
        )
        if unity_support_output.returncode != 0:
            print(
                "[ ERR ] unity support test returned {}. Error is: {}".format(
                    unity_support_output.returncode,
                    unity_support_output.stdout,
                ),
                file=sys.stderr,
            )
            return False

        is_hardware_rendered = (
            self.parse_unity_support_output(unity_support_output.stdout).get(
                "Not software rendered"
            )
            == "yes"
        )
        if is_hardware_rendered:
            print("[ OK ] This machine is using a hardware renderer!")
            return True

        print("[ ERR ] Software rendering detected", file=sys.stderr)
        return False

    def wait_for_graphical_target(self, max_wait_seconds: int) -> bool:
        """Wait for the DUT to reach graphical.target in systemd critical chain

        :param max_wait_seconds: num seconds to wait at most
        :return: whether graphical.target was reached within max_wait_seconds
        """

        start = time.time()
        while time.time() - start < max_wait_seconds:
            try:
                out = sp.run(
                    [
                        "systemd-analyze",
                        "critical-chain",
                        "graphical.target",
                        "--no-pager",
                    ],
                    stdout=sp.DEVNULL,
                    stderr=sp.DEVNULL,
                    timeout=min(10, max_wait_seconds),
                )
                if out.returncode == 0:
                    return True
                else:
                    time.sleep(1)
            except sp.TimeoutExpired:
                print("systemd-analyze timed out!")
                return False

        return False

    def parse_unity_support_output(
        self, unity_output_string: str
    ) -> T.Dict[str, str]:
        """
        Parses the output of `unity_support_test` into a dictionary

        :param output_string: the raw output from running unity_support_test -p
        :type output_string: str
        :return: string key-value pairs that mirror the output of unity_support
        Left hand side of the first colon are the keys;
        right hand side are the values.
        :rtype: dict[str, str]
        """

        output = {}  # type: dict[str, str]
        for line in unity_output_string.split("\n"):
            # max_split=1 to prevent splitting the string after the 1st colon
            words = line.split(":", maxsplit=1)
            if len(words) == 2:
                key = words[0].strip()
                value = remove_color_code(words[1].strip())
                output[key] = value

        return output


def get_failed_services() -> T.List[str]:
    """
    Counts the number of failed services listed in systemctl

    :return: a list of failed services as they appear in systemctl
    """
    command = [
        "systemctl",
        "list-units",
        "--system",
        "--no-ask-password",
        "--no-pager",
        "--no-legend",
        "--state=failed",
        "--plain",  # plaintext, otherwise it includes color codes
    ]

    return sp.check_output(command, universal_newlines=True).splitlines()


def create_parser():
    parser = argparse.ArgumentParser(
        prog="Reboot tests",
        description="Collects device info and compares them across reboots",
    )
    parser.add_argument(
        "-d",
        "--dump-to",
        required=False,
        dest="output_directory",
        help="Device info-dumps will be written here",
    )
    parser.add_argument(
        "-c",
        "--compare-to",
        dest="comparison_directory",
        help="Directory of ground-truth for device info comparison",
    )
    parser.add_argument(
        "-s",
        "--service-check",
        default=False,
        dest="do_service_check",
        action="store_true",
        help="If specified, check if all system services are running",
    )
    parser.add_argument(
        "-f",
        "--fwts-check",
        default=False,
        dest="do_fwts_check",
        action="store_true",
        help="If specified, look for fwts log errors",
    )
    parser.add_argument(
        "-g",
        "--graphics",
        default=False,
        dest="do_renderer_check",
        action="store_true",
        help="If specified, check if hardware rendering is being used",
    )
    parser.add_argument(
        "--graphical-target-timeout",
        default=120,
        type=int,
        dest="graphical_target_timeout",
        help="How many seconds should we wait for systemd to report "
        "that it has reached graphical.target in its critical chain "
        "before the renderer check starts. "
        "Default is 120 seconds. Ignored if -g/--graphics is not specified.",
    )

    return parser


def remove_color_code(string: str) -> str:
    """
    Removes ANSI color escape sequences from string

    :param string: the string that you would like to remove color code
    credit: Hanhsuan Lee <hanhsuan.lee@canonical.com>
    """
    return re.sub(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])", "", string)


def main() -> int:
    """Main routine

    :return: an return code for checkbox to consume, 1 = failed, 0 = success
    :rtype: int
    """

    args = create_parser().parse_args()

    # all 4 tests pass by default
    # they only fail if their respective flags are specified
    # if no flags are specified, calling this script is a no-op
    fwts_passed = True
    device_comparison_passed = True
    renderer_test_passed = True
    service_check_passed = True

    print(
        "Starting reboot checks. {}. Boot ID: {}".format(
            get_timestamp_str(), get_current_boot_id()
        )
    )

    if args.comparison_directory is not None:
        if args.output_directory is None:
            print(
                "[ ERR ] Please specify an output directory with the -d flag.",
                file=sys.stderr,
            )
            raise ValueError(
                "Comparison directory is specified, but output directory isn't"
            )
        else:
            collector = DeviceInfoCollector()
            collector.dump(args.output_directory)
            if collector.compare_device_lists(
                args.comparison_directory, args.output_directory
            ):
                print("[ OK ] Devices match!")
            else:
                device_comparison_passed = False

    # dump (no checks) if only output_directory is specified
    if args.output_directory is not None and args.comparison_directory is None:
        print("Only dumping device info to {}".format(args.output_directory))
        DeviceInfoCollector().dump(args.output_directory)

    if args.do_fwts_check:
        tester = FwtsTester()
        if tester.is_fwts_supported() and not tester.fwts_log_check_passed(
            args.output_directory
        ):
            fwts_passed = False
        else:
            print("[ OK ] fwts checks passed!")

    if args.do_service_check:
        failed_services = get_failed_services()
        if len(failed_services) > 0:
            print(
                "These services failed: {}".format("\n".join(failed_services)),
                file=sys.stderr,
            )
            service_check_passed = False
        else:
            print("[ OK ] Didn't find any failed system services!")

    if args.do_renderer_check:
        tester = HardwareRendererTester()

        print("Checking if DUT has reached graphical.target...")
        graphical_target_reached = tester.wait_for_graphical_target(
            args.graphical_target_timeout
        )

        if not graphical_target_reached:
            print(
                "[ ERR ] systemd's graphical.target was not reached",
                "in {} seconds.".format(args.graphical_target_timeout),
                "Marking the renderer test as failed.",
            )
            renderer_test_passed = False
        else:
            print("Graphical target was reached!")
            if has_desktop_environment() and tester.has_display_connection():
                # skip renderer test if there's no display
                renderer_test_passed = tester.is_hardware_renderer_available()

    print("Finished reboot checks. {}".format(get_timestamp_str()))

    if (
        fwts_passed
        and device_comparison_passed
        and renderer_test_passed
        and service_check_passed
    ):
        return 0
    else:
        return 1


if __name__ == "__main__":
    return_code = main()
    exit(return_code)
