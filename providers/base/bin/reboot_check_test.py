#!/usr/bin/env python3

import argparse
import os
import subprocess
import re
import shutil
import filecmp
import sys
import enum
import typing as T


# Checkbox could run in a snap container, so we need to prepend this root path
RUNTIME_ROOT = os.getenv("CHECKBOX_RUNTIME", default="")
# Snap mount point, see https://snapcraft.io/docs/environment-variables#heading--snap
SNAP = os.getenv("SNAP", default="")


class ShellResult:
    """Wrapper class around the return value of run_command, guarantees non-null"""

    def __init__(self, return_code: int, stdout: str, stderr: str):
        self.return_code = return_code
        self.stdout = stdout
        self.stderr = stderr


def run_command(args: T.List[str]) -> ShellResult:
    """Wrapper around subprocess.run

    :param args: same args that goes to subprocess.run
    :type args: T.List[str]
    :return: return code, stdout and stderr, all non-null
    :rtype: ShellResult
    """
    # PIPE is needed for subprocess.run to capture stdout and stderr (<=3.7 behavior)
    out = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return ShellResult(
        return_code=out.returncode,
        # if there's nothing on stdout, .stdout is None, so we need a default value
        stdout=(out.stdout or b"").decode(),
        stderr=(out.stderr or b"").decode(),
    )
    # This could throw on non-UTF8 decodable byte strings, but that should be rare
    # since utf-8 is backwards compatible with ascii


def is_fwts_supported() -> bool:
    return shutil.which("fwts") is not None


def fwts_log_check_passed(
    output_directory: str, fwts_arguments=["klog", "oops"]
) -> bool:
    """Check if fwts logs passes the checks specified in sleep_test_log_check.py.
    This script live in the same directory

    :param output_directory: where the output of fwts should be redirected to
    :type output_directory: str
    :return: whether sleep_test_log_check.py returned 0 (success)
    :rtype: bool
    """
    log_file_path = "{}/fwts_{}.log".format(
        output_directory, "_".join(fwts_arguments)
    )
    subprocess.run(["fwts", "-r", log_file_path, *fwts_arguments])
    result = subprocess.run(
        [
            "sleep_test_log_check.py",
            "-v",
            "--ignore-warning",
            "-t",
            "all",
            log_file_path,
        ]
    )

    return result.returncode == 0


def get_failed_services() -> T.List[str]:
    """Counts the number of failed services listed in systemctl

    :return: number of failed services
    """
    command = [
        "systemctl",
        "list-units",
        "--system",
        "--no-ask-password",
        "--no-pager",
        "--no-legend",
        "--state=failed",
    ]  # only print the names of the services that failed

    return run_command(command).stdout.split()


class DeviceInfoCollector:

    class Device(enum.Enum):
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
    }  # used for comparison and dump calls

    def get_drm_info(self) -> str:
        return str(os.listdir("/sys/class/drm"))

    def get_wireless_info(self) -> str:
        iw_out = run_command(["iw", "dev"])
        lines = iw_out.stdout.splitlines()
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
        return run_command(
            [
                "checkbox-support-lsusb",
                "-f",
                '"{}"/var/lib/usbutils/usb.ids'.format(RUNTIME_ROOT),
                "-s",
            ]
        ).stdout

    def get_pci_info(self) -> str:
        return run_command(
            ["lspci", "-i", "{}/usr/share/misc/pci.ids".format(SNAP)],
        ).stdout

    def compare_device_lists(
        self, expected_dir: str, actual_dir: str, devices=DEFAULT_DEVICES
    ) -> bool:
        """Compares the list of devices in expected_dir against actual_dir

        :param expected_dir: a directory of files containing the expected values the device list
        :param actual_dir: a directory of files containing the actual device list
        :return: whether the device list matches
        """
        print(
            "Comparing device list files in (expected){} against (actual){}...".format(
                expected_dir, actual_dir
            )
        )
        for device in devices["required"]:
            # file paths of the expected and actual device lists
            expected = "{}/{}_log".format(expected_dir, device)
            actual = "{}/{}_log".format(actual_dir, device)
            if not filecmp.cmp(expected, actual):
                print(
                    "The output of {} differs from the list gathered at the beginning of the session!".format(
                        device
                    ),
                    file=sys.stderr,
                )
                return False

        for device in devices["optional"]:
            expected = "{}/{}_log".format(expected_dir, device)
            actual = "{}/{}_log".format(actual_dir, device)
            if not filecmp.cmp(expected, actual):
                print(
                    "[WARN] Items under {} has changed.".format(actual),
                    "If this machine dynamically switches between GPUs, this might be expected",
                    file=sys.stderr,
                )

        return True

    def dump(
        self,
        output_directory: str, 
        devices: T.Dict[str, T.List[Device]] = DEFAULT_DEVICES
    ) -> None:


        os.makedirs(output_directory, exist_ok=True)
        # add extra behavior if necessary
        for device in devices["required"]:
            with open(
                "{}/{}_log".format(output_directory, device.value), "w"
            ) as file:
                file.write(self.dump_function[device]())

        for device in devices["optional"]:
            with open(
                "{}/{}_log".format(output_directory, device.value), "w"
            ) as file:
                file.write(self.dump_function[device]())

        os.sync()

    def __init__(self) -> None:
        # self.output_directory = output_directory
        self.dump_function = {
            self.Device.PCI: self.get_pci_info,
            self.Device.DRM: self.get_drm_info,
            self.Device.USB: self.get_usb_info,
            self.Device.WIRELESS: self.get_wireless_info,
        }


def parse_arguments():
    parser = argparse.ArgumentParser(
        prog="Reboot tests",
        description="This script is used to collect device information and to check for differences between reboots.",
    )
    parser.add_argument(
        "-d",
        "--dump-to",
        required=True,
        dest="output_directory",
        help="Absolute path to the output directory. Device info-dumps will be written here.",
    )
    parser.add_argument(
        "-c",
        "--compare-to",
        dest="comparison_directory",
        help="Absolute path to the comparison directory. This should contain the ground-truth.",
    )
    parser.add_argument(
        "-s",
        "--service-check",
        default=False,
        dest="do_service_check",
        action="store_true",
        help="Whether the script should check if all system services are running",
    )
    parser.add_argument(
        "-f",
        "--fwts-check",
        default=False,
        dest="do_fwts_check",
        action="store_true",
        help="Whether the script should look for fwts log errors",
    )
    parser.add_argument(
        "-g",
        "--graphics",
        default=False,
        dest="do_renderer_check",
        action="store_true",
        help="Whether the script should check if hardware rendering is being used",
    )

    return parser.parse_args()


def remove_color_code(string: str) -> str:
    """Removes ANSI color escape sequences from string

    :param string: the string that you would like to remove color code
    credit: Hanhsuan Lee <hanhsuan.lee@canonical.com>
    """
    return re.sub(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])", "", string)


def get_display_id() -> T.Optional[str]:
    """Returns the active display id
    https://github.com/canonical/checkbox/blob/main/contrib/pc-sanity/bin/renderer-mesa-driver-check.sh

    :return: the display id, usually ":0" if there's only 1 display
    :rtype: str
    """
    DISPLAY = os.getenv("DISPLAY", default="")

    if DISPLAY != "":
        print("Using $DISPLAY env variable: {}".format(DISPLAY))
        return DISPLAY  # use the environment var if non-empty

    session_id = (
        run_command(["loginctl", "list-sessions", "--no-legend"])
        .stdout.split()[0]
        .strip()
        # string is guaranteed to be non-empty, at least 1 user is logged in
    )

    display_server_type = (
        run_command(["loginctl", "show-session", session_id, "-p", "Type"])
        .stdout.split("=")[1]
        .strip()  # it should look like Type=wayland, split and take 2nd word
    )

    # NOTE: Xwayland doesn't immediately start after a reboot
    # For now, we will assume :0 exists and use it as the display id
    if display_server_type == "wayland":
        pgrep_out = run_command(["pgrep", "-a", "Xwayland"])
        # search for a process called Xwayland, take the 3rd arg, which is the display id
        if pgrep_out.return_code == 0:
            return pgrep_out.stdout.split()[2]
        else:
            print('[WARN] Waylad session detected, but Xwayland process is not found. Assuming :0 display')
            return ':0'

    if display_server_type == "x11":
        w_out = run_command(["w", "--no-header"])
        if len(w_out.stdout) != 0:
            return w_out.stdout.split()[2]
        return None

    return None  # Unsupported window system


def has_display_connection() -> bool:
    """Checks if a display is connected by searching the /sys/class/drm directory

    :return: True if there's at least 1 node that is connected
    """

    # look for GPU file nodes first
    DRM_PATH = "/sys/class/drm"
    possible_gpu_nodes = os.listdir(DRM_PATH)
    if len(possible_gpu_nodes) == 0 or possible_gpu_nodes == ["version"]:
        # kernel doesn't see any GPU nodes
        print(
            "There's nothing under {}".format(DRM_PATH),
            "if an external GPU is connected, check if the connection is loose",
        )
        return False

    print("These nodes", possible_gpu_nodes, "exist")
    print("Checking for display connection...")

    for gpu in possible_gpu_nodes:
        # for each gpu, check for connection, return true if anything is connected
        try:
            status_file = open("{}/{}/status".format(DRM_PATH, gpu))
            if status_file.read().strip().lower() == "connected":
                print("{} is connected to display!".format(gpu))
                return True
        except FileNotFoundError:
            pass  # this just means we don't have a status file => no connection
        except Exception as e:
            print("Unexpected error: ", e, file=sys.stderr)

    print(
        "No display is connected. This case will be skipped.",
        "Maybe the display cable is not connected?",
    )
    return False


def is_hardware_renderer_available() -> bool:
    """Checks if hardware rendering is being used. THIS ASSUMES A DRM CONNECTION EXISTS

    :return: True if a hardware renderer is active, otherwise return False
    :rtype: bool
    """

    # Now we know some kind of display exists, run unity_support_test
    display_id = get_display_id()
    if display_id is None:
        print("No display id was found.", file=sys.stderr)
        # No display id was found
        return False

    print("Checking display id: {}".format(display_id))

    unity_support_output = run_command(
        [
            "{}/usr/lib/nux/unity_support_test".format(RUNTIME_ROOT),
            "-p",
            "-display",
            display_id,
        ]
    )
    if unity_support_output.return_code != 0:
        return False

    is_hardware_rendered = (
        parse_unity_support_output(unity_support_output.stdout).get(
            "Not software rendered"
        )
        == "yes"
    )
    if is_hardware_rendered:
        print("[ OK ] This machine is using a hardware renderer!")
        return True

    return False


def parse_unity_support_output(output_string: str) -> T.Dict[str, str]:
    """Parses the output of `unity_support_test` into a dictionary

    :param output_string: the raw output from running `unity_support_test -p`
    :type output_string: str
    :return: string key-value pairs that mirror the output of unity_support_test.
        Left hand side of the first colon are the keys; right hand side are the values.
    :rtype: dict[str, str]
    """

    output = {}  # type: dict[str, str]
    for line in output_string.split("\n"):
        # max_split=1 to prevent splitting the string after the 1st colon
        words = line.split(":", maxsplit=1)
        if len(words) == 2:
            key = words[0]
            value = remove_color_code(words[1].strip())
            output[key] = value

    return output


def main() -> int:
    """Main routine

    :return: an return code for checkbox to consume, 1 = failed, 0 = success
    :rtype: int
    """

    args = parse_arguments()

    # all 4 tests pass by default
    # they only fail if their respective flags are specified
    # if no flags are specified, calling this script is a no-op
    fwts_passed = True
    device_comparison_passed = True
    renderer_test_passed = True
    service_check_passed = True

    if args.comparison_directory is not None:
        if args.output_directory is None:
            print(
                "Error: Please also specify an output directory with the -d flag.",
                file=sys.stderr,
            )
        else:
            collector = DeviceInfoCollector()
            collector.dump(args.output_directory)
            collector.compare_device_lists(
                args.comparison_directory, args.output_directory
            )

    # dump (no checks) if only output_directory is specified
    if args.output_directory is not None and args.comparison_directory is None:
        DeviceInfoCollector().dump(args.output_directory)

    if args.do_fwts_check:
        if is_fwts_supported() and not fwts_log_check_passed(
            args.output_directory
        ):
            fwts_passed = False

    if args.do_service_check:
        print("Checking for failed system services...")

        failed_services = get_failed_services()
        if len(failed_services) > 0:
            print(
                "These services failed: {}".format(failed_services),
                file=sys.stderr,
            )
            service_check_passed = False

    if args.do_renderer_check and has_display_connection():
        # skip renderer test if there's no display
        renderer_test_passed = is_hardware_renderer_available()

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
