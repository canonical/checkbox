#!/usr/bin/env python3

# TODO: Match python 3.5 syntax


import argparse
import os
import subprocess
import re
import shutil
import filecmp
import sys
import typing as T
from subprocess import PIPE


# Checkbox could run in a snap container, so we need to prepend this root path
RUNTIME_ROOT = os.getenv("CHECKBOX_RUNTIME", default="")
# Snap mount point, see https://snapcraft.io/docs/environment-variables#heading--snap
SNAP = os.getenv("SNAP", default="")


def is_fwts_supported() -> bool:
    return shutil.which("fwts") is not None


def fwts_log_check_passed(output_directory: str) -> bool:
    """Check if fwts logs passes the checks specified in sleep_test_log_check.py. 
    This script live in the same directory

    :param output_directory: where the output of fwts should be redirected to
    :type output_directory: str
    :return: whether sleep_test_log_check.py returned 0 (success)
    :rtype: bool
    """
    log_file_path = "{}/fwts_klog_oops.log".format(output_directory)
    subprocess.run(
        [
            "fwts",
            "-r",
            log_file_path,
            "klog",
            "oops",
        ]
    )
    result = subprocess.run(
        [
            "./sleep_test_log_check.py",
            "-v",
            "--ignore-warning",
            "-t",
            "all",
            log_file_path,
        ]
    )

    return result.returncode == 0


def compare_device_lists(expected_dir: str, actual_dir: str) -> bool:
    """Compares the list of devices in expected_dir against actual_dir

    :param expected_dir: a directory of files containing the expected values the device list
    :param actual_dir: a directory of files containing the actual device list
    :return: whether the device list matches
    """
    print("Comparing devices...")
    for name in ["lspci", "iw", "lsusb"]:
        # file paths of the expected and actual device lists
        expected = "{}/{}_log".format(expected_dir, name)
        actual = "{}/{}_log".format(actual_dir, name)
        if not filecmp.cmp(expected, actual):
            print(
                "The output of {} differs from the original list gathered at the beginning of the session!".format(
                    name
                )
            )
            return False

    return True


def get_failed_services() ->T.List[str]:
    """Counts the number of failed services listed in systemctl

    :return: number of failed services
    :rtype: int
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
    output = subprocess.run(command).stdout.decode()

    return output.split()


def dump_device_info(output_directory: str) -> None:
    """Writes information of PCI, wireless, and USB devices to the specified directory

    :param output_directory: where the output should be written to.
    If this directory doesn't already exist, this function will create it.
    :type output_directory: str
    """

    print("Dumping the devices information to {}".format(output_directory))

    # specifying exist_ok=True for now to mimic mkdir -p's behavior,
    # TODO: check if this is intended
    os.makedirs(output_directory, exist_ok=True)

    print("Checking PCI devices...")
    with open("{}/lspci_log".format(output_directory), "w") as f:
        lspci_out = subprocess.run(
            ["lspci", "-i", "{}/usr/share/misc/pci.ids".format(SNAP)],
            stdout=PIPE,
            stderr=PIPE,
        )
        f.write(lspci_out.stdout.decode())

    print("Checking wireless connections...")
    with open("{}/iw_log".format(output_directory), "w") as f:
        iw_out = subprocess.run(["iw", "dev"], stdout=PIPE, stderr=PIPE)
        lines = iw_out.stdout.decode().splitlines()
        lines_to_write = list(
            filter(
                lambda line: "addr" in line
                or "Interface" in line
                or "ssid" in line,
                sorted(lines),
            )
        )
        f.write("\n".join(map(lambda line: line.strip(), lines_to_write)))

    print("Checking USB devices...")
    with open("{}/lsusb_log".format(output_directory), "w") as f:
        lsusb_out = subprocess.run(
            [
                "checkbox-support-lsusb",
                "-f",
                '"{}"/var/lib/usbutils/usb.ids'.format(RUNTIME_ROOT),
                "-s",
            ],
            stdout=PIPE,
            stderr=PIPE,
        )
        f.write(lsusb_out.stdout.decode())

    os.sync()  # force disk write
    print("Finished dumping device info!")


def parse_arguments():
    parser = argparse.ArgumentParser(
        prog="Reboot tests",
        description="This script is used to collect device information and to check for differences between reboots.",
    )
    parser.add_argument(
        "-d",
        dest="output_directory",
        help="Absolute path to the output directory",
    )
    parser.add_argument(
        "-c",
        dest="comparison_directory",
        help="Absolute path to the comparison directory",
    )
    parser.add_argument(
        "-s",
        default=False,
        dest="do_service_check",
        action="store_true",
        help="Whether the script should check if all system services are running",
    )
    parser.add_argument(
        "-f",
        default=False,
        dest="do_fwts_check",
        action="store_true",
        help="Whether the script should look for fwts log errors",
    )
    parser.add_argument(
        "-g",
        default=False,
        dest="do_renderer_check",
        action="store_true",
        help="Whether the script should check if hardware rendering is being used",
    )

    return parser.parse_args()  # type: ignore , checked manually


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
    XDG_SESSION_TYPE = os.getenv("XDG_SESSION_TYPE", default="")

    if DISPLAY != "":
        return DISPLAY  # use the environment var if non-empty

    session_id = (
        subprocess.run(["loginctl", "list-sessions", "--no-legend"]).stdout
        .decode()
        .split()[0]
        .strip()
        # string is guaranteed to be non-empty, at least 1 user is logged in
    )

    display_server_type = (
        subprocess.run(
            ["loginctl", "show-session", session_id, "-p", "Type"]
        )
        .stdout
        .decode()
        .split("=")[1]
        .strip()  # it should look like Type=wayland, split and take 2nd word
    )

    print("{} =? {}".format(XDG_SESSION_TYPE, display_server_type))

    if display_server_type == "wayland":
        # search for a process called xwayland, take the 3rd arg, which is the display id
        return (
            subprocess.run(["pgrep", "-a", 'Xwayland'])
            .stdout
            .decode()
            .split()[2]
        )

    if display_server_type == "x11":
        return (
            subprocess.run(["w", "--no-header"]).stdout.decode().split()[2]
        )

    return None  # Unsupported window system


def has_DRM_file_nodes() -> bool:
    """Checks of there's anything user/sys/class/drm

    :return: True if there are more items than just "version"
    """
    
    # look for GPU file nodes first
    possible_gpu_nodes = os.listdir("/sys/class/drm")
    if len(possible_gpu_nodes) == 0 or possible_gpu_nodes == ["version"]:
        # kernel doesn't see any GPU nodes
        print(
            "There's nothing under /sys/class/drm",
            "if an external GPU is connected, check if the connection is loose",
        )
        return False

    print("These nodes", possible_gpu_nodes, "exist")
    return True


def is_hardware_renderer_available() -> bool:
    """Checks if hardware rendering is being used

    :return: True if a hardware renderer is active or none exists, otherwise return False
    :rtype: bool
    """

    # Now we know some kind of display exists, run unity_support_test
    display_id = get_display_id()
    print("Checking display id: {}".format(display_id))
    if display_id is None:
        # No display id was found
        return False

    unity_support_output = subprocess.run(
        [
            "{}/usr/lib/nux/unity_support_test".format(RUNTIME_ROOT),
            "-p",
            "-display",
            display_id,
        ],
        stdout=PIPE,
        stderr=PIPE,
    )
    if unity_support_output.returncode != 0:
        return False

    is_hardware_rendered = (
        parse_unity_support_output(unity_support_output.stdout.decode()).get(
            "Not software rendered"
        )
        == "yes"
    )
    if not is_hardware_rendered:
        return False

    print("This machine is using a hardware renderer!")
    return True


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
    
    fwts_passed = False
    device_comparison_passed=False
    has_failed_services=False



    if args.output_directory is not None:
        dump_device_info(args.output_directory)
        supports_fwts = is_fwts_supported()
        if supports_fwts and not fwts_log_check_passed(args.output_directory):
            return 1

    if args.comparison_directory is not None:
        if args.output_directory is None:
            print(
                "Error: Please specify an output directory with the -d flag.",
                file=sys.stderr,
            )
        else:
            compare_device_lists(
                args.comparison_directory, args.output_directory
            )

    if args.do_service_check:
        print("Checking for failed system services...")
        failed_services = get_failed_services()
        if len(failed_services) > 0:
            print("These services failed: {}".format(failed_services), file=sys.stderr)
            return 1

    if args.do_fwts_check and (
        args.output_directory is None
        or not fwts_log_check_passed(args.output_directory)
    ):
        return 1

    if args.do_renderer_check:
        if not has_DRM_file_nodes():
            return 0  # skip gpu test if there's no GPU
        return 0 if is_hardware_renderer_available() else 1

    #  if [[ -n "$service_opt" && "$service_check" == "false" ]] || \
    #    [[ -n "$compare_dir" && "$device_check" == "false" ]] || \
    #    [[ -n "$fwts_opt" && "$fwts_check" == "false" ]]; then
    #     exit 1
    # fi

    return 0


if __name__ == "__main__":
    print(os.getcwd())
    return_code = main()
    exit(return_code)
    # dump_device_info("testoo")
    # is_hardware_renderer_available()
