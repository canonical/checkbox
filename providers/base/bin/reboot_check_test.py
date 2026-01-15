#!/usr/bin/env python3

import argparse
import os
import subprocess as sp
import shutil
import filecmp
import sys
import typing as T
from checkbox_support.scripts.image_checker import has_desktop_environment
from datetime import datetime
import time
import platform


def get_checkbox_runtime_path() -> "str | None":
    """Finds the correct checkbox runtime path in $CHECKBOX_RUNTIME
    CHECKBOX_RUNTIME is a string of paths separated by \n
    Only the /snap/checkbox/checkbox-runtime/... lines is the one we need
    Iter the lines and find it

    :return: None if not in a snap or failed to find this
    """
    if "CHECKBOX_RUNTIME" not in os.environ:
        return None

    lines = os.environ["CHECKBOX_RUNTIME"].strip().splitlines()
    for line in lines:
        if "checkbox-runtime" in line:
            return line


def get_timestamp_str() -> str:
    with open("/proc/uptime", "r") as f:
        # uptime file always have 2 numbers
        # uptime_seconds total_idle_seconds
        # take the 1st one
        uptime_seconds = f.readline().split()[0]

    return "Time: {}. Uptime: {} seconds".format(
        datetime.now().strftime("%m/%d/%Y, %H:%M:%S"), uptime_seconds
    )


def get_current_boot_id() -> str:
    with open("/proc/sys/kernel/random/boot_id", "r") as f:
        # the boot_id file has a Version 4 UUID with hyphens
        # journalctl doesn't use hyphens so we just remove it
        return f.read().strip().replace("-", "")


# Snap mount point, see
# https://snapcraft.io/docs/environment-variables#heading--snap
SNAP = os.getenv("SNAP", default="").rstrip("/")
# global const for subprocess calls that should timeout
COMMAND_TIMEOUT_SECONDS = 30
CHECKBOX_RUNTIME = get_checkbox_runtime_path() or ""  # TODO: use path objects


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

    def get_drm_info(self) -> str:
        return str(sorted(os.listdir("/sys/class/drm")))

    def get_wireless_info(self) -> str:
        iw_out = sp.check_output(
            ["iw", "dev"],
            timeout=COMMAND_TIMEOUT_SECONDS,
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
                '"{}"/var/lib/usbutils/usb.ids'.format(CHECKBOX_RUNTIME),
                "-s",
            ],
            universal_newlines=True,
            timeout=COMMAND_TIMEOUT_SECONDS,
        ).splitlines()
        out.sort()
        return "\n".join(out)

    def get_pci_info(self) -> str:
        return sp.check_output(
            ["lspci", "-i", "{}/usr/share/misc/pci.ids".format(SNAP)],
            timeout=COMMAND_TIMEOUT_SECONDS,
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
        self,
        output_directory: str,
        fwts_arguments: T.Sequence[str] = ["klog", "oops"],
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

    def get_desktop_environment_variables(
        self,
    ) -> T.Optional[T.Dict[str, str]]:
        """Gets all the environment variables used by the desktop process

        :return: dict[str, str] similar to os.environ
            None if the desktop process is not found
        """
        # "-s" guarantees at most 1 result
        # do not use check_output here,
        # pidof will return 1 when process is not found
        gnome_pid = sp.run(
            ["pidof", "-s", "gnome-shell"],
            stdout=sp.PIPE,
            universal_newlines=True,
        )
        # TODO: remove unity related checks after 16.04 reaches EOL
        compiz_pid = sp.run(  # 16.04 only
            ["pidof", "-s", "compiz"], stdout=sp.PIPE, universal_newlines=True
        )

        desktop_pid = None  # type: int | None
        if gnome_pid.returncode == 0:
            desktop_pid = int(gnome_pid.stdout)
        elif compiz_pid.returncode == 0:
            desktop_pid = int(compiz_pid.stdout)

        if desktop_pid is None:
            # this means the desktop failed to load
            # or we are not in a graphical session
            return None

        # /proc/pid/environ is a null-char separated string
        proc_env_strings = sp.check_output(
            ["cat", "/proc/{}/environ".format(desktop_pid)],
            universal_newlines=True,
        ).split("\0")

        # ideally we don't manually parse this and just use the env file
        # but py3.5 only takes a mapping for the env param
        desktop_env_vars = {}  # type: dict[str, str]
        for env_str in proc_env_strings:
            kv = env_str.split("=", maxsplit=1)  # DISPLAY=:0
            if len(kv) == 2:
                key, value = kv
                desktop_env_vars[key] = value

        return desktop_env_vars

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
                "if an external GPU is connected,",
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
                "If the device is not supposed to have a display,",
                "then skipping is expected.",
            )

        return connected_to_display

    def pick_glmark2_executable(
        self, xdg_session_type: str, cpu_arch: str
    ) -> str:
        """
        Pure function that picks a glmark2 executable based on xdg_session_type
        and cpu arch

        :param xdg_session_type: the $XDG_SESSION_TYPE variable
        :param cpu_arch: the `uname -m` value like x86_64
        :return: glmark2 command to use. Caller is responsible for checking if
                 the command exists
        """
        if cpu_arch in ("x86_64", "amd64"):
            # x86 DUTs should run the version that uses the full opengl api
            glmark2_executable = "glmark2"
        else:
            # default to es2 as the common denominator
            # TODO: explicitly check for aarch64?
            glmark2_executable = "glmark2-es2"

        if xdg_session_type == "wayland":
            glmark2_executable += "-wayland"
        # if x11, don't add anything
        return glmark2_executable

    def gl_renderer_str_is_hardware_renderer(self, gl_renderer: str) -> bool:
        """Checks if gl_renderer is produced by a hardware renderer.

        This uses the same logic as unity_support_test. Details:
        https://github.com/canonical/checkbox/issues/1630#issuecomment-2540843110

        :param gl_renderer: the GL_RENDERER string.
        https://registry.khronos.org/OpenGL-Refpages/gl4/html/glGetString.xhtml
        :return: whether GL_RENDERER is produced by a hardware renderer
        """
        # These 2 values are carried over from unity_support_test
        # never seen this before on devices after ubuntu 16
        if gl_renderer in ("Software Rasterizer", "Mesa X11"):
            return False
        # https://docs.mesa3d.org/envvars.html#envvar-GALLIUM_DRIVER
        # it's almost always the 'llvmpipe' case if we find software rendering
        if "llvmpipe" in gl_renderer or "softpipe" in gl_renderer:
            return False

        return True

    def extract_gl_renderer_str(
        self,
        glmark2_validate_output: str,
    ) -> T.Optional[str]:
        """Attempts to extract GL_RENDERER from `glmark2 --validate`'s output

        :param glmark2_validate_output: the .stdout from `glmark2 --validate`
        :return: GL_RENDERER itself or None if couldn't be determined
        """
        gl_renderer_line = None  # type: str | None
        for line in glmark2_validate_output.splitlines():
            if "GL_RENDERER" in line:
                gl_renderer_line = line
                break

        if gl_renderer_line is None:
            return None

        return gl_renderer_line.split(":")[-1].strip()

    def is_hardware_renderer_available(self) -> bool:
        """
        Checks if hardware rendering is being used by calling glmark2
        - THIS ASSUMES A DRM CONNECTION EXISTS
        - self.has_display_connection() should be called first if unsure

        :return: True if a hardware renderer is active, otherwise return False
        """

        desktop_env_vars = self.get_desktop_environment_variables()
        if desktop_env_vars is None:
            print(
                "[ ERR ] Unable to get the environment variables",
                "used by the current desktop. Is the desktop process running?",
            )
            return False

        XDG_SESSION_TYPE = desktop_env_vars.get("XDG_SESSION_TYPE")

        if XDG_SESSION_TYPE not in ("x11", "wayland"):
            # usually it's tty if we get here,
            # happens when gnome failed to start or not using graphical session
            print(
                "[ ERR ] Unsupported session type: '{}'.".format(
                    XDG_SESSION_TYPE
                ),
                "Expected either 'x11' or 'wayland'",
                file=sys.stderr,
            )
            return False

        print("XDG_SESSION type used by the desktop is:", XDG_SESSION_TYPE)

        glmark2_executable = self.pick_glmark2_executable(
            XDG_SESSION_TYPE, platform.uname().machine
        )
        glmark2_data_path = "/usr/share/glmark2"

        try:
            # PATH override is needed for snaps on classic ubuntu
            # to allow the glmark2 command itself to be discovered
            desktop_env_vars["PATH"] = os.environ["PATH"]
            glmark2_output = sp.run(
                # all glmark2 programs share the same args
                [glmark2_executable, "--off-screen", "--validate"],
                stdout=sp.PIPE,
                stderr=sp.STDOUT,
                universal_newlines=True,
                # be more relaxed on this timeout in case
                # the device needs a lot of time to wake up the GPU
                timeout=120,
                # literally dump all envs from gnome/unity to glmark2
                env=desktop_env_vars,
            )
        except sp.TimeoutExpired:
            print(
                "[ ERR ] {} timed out after 120s.".format(glmark2_executable),
                "Marking this test as failed.",
                file=sys.stderr,
            )
            return False

        if glmark2_output.returncode != 0:
            print(
                "[ ERR ] {} returned {}. Error is: {}".format(
                    glmark2_executable,
                    glmark2_output.returncode,
                    glmark2_output.stdout,
                ),
                file=sys.stderr,
            )
            return False

        gl_renderer = self.extract_gl_renderer_str(glmark2_output.stdout)

        if gl_renderer is None:
            print(
                "[ ERR ] {} did not return a renderer string".format(
                    glmark2_executable
                ),
                file=sys.stderr,
            )
            return False

        print(
            "GL_RENDERER found by {} is: {}".format(
                glmark2_executable, gl_renderer
            )
        )
        is_hardware_rendered = self.gl_renderer_str_is_hardware_renderer(
            gl_renderer
        )
        if is_hardware_rendered:
            print("[ OK ] This machine is using a hardware renderer!")
            return True

        print("[ ERR ] Software rendering detected", file=sys.stderr)
        return False


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


def poll_systemctl_is_system_running(max_wait_seconds: int) -> bool:
    """Poll systemd and see if it finished booting

    :param max_wait_seconds: max number of seconds to wait
    :return: whether "systemctl is-system-running" returns a state that's not
             "initializing" or "starting" within max_wait_seconds
    :raises: sp.TimeoutExpired if the command timed out
    """

    start = time.time()
    status = None  # type: str | None
    while time.time() - start < max_wait_seconds:
        # https://unix.stackexchange.com/questions
        # /460324/is-there-a-way-to-wait-for-boot-to-complete

        # The better way to do this is
        # with the --wait flag so we don't busy-poll, but that's not available
        # on ubuntu 16 and 18
        # TODO: remove this function once we drop ubuntu 18 and use --wait
        out = sp.run(
            ["systemctl", "is-system-running"],
            stdout=sp.PIPE,
            stderr=sp.STDOUT,
            universal_newlines=True,
            timeout=min(COMMAND_TIMEOUT_SECONDS, max_wait_seconds),
        )
        status = out.stdout.strip()
        # all possible return values:
        # https://www.freedesktop.org/software/systemd/man
        # /latest/systemctl.html#is-system-running
        if status in ("initializing", "starting"):
            # only mark these 2 states as "still booting"
            # to be consistent with the behavior of --wait
            time.sleep(1)
        else:
            print(
                "Final 'systemctl is-system-running' return value: {}".format(
                    status
                )
            )
            return True

    print(
        "Final 'systemctl is-system-running' return value: {}".format(status)
    )
    return False


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
        "--boot-ready-timeout",
        default=120,
        type=int,
        dest="boot_ready_timeout",
        help=(
            "How many seconds should we wait for systemd to report "
            "that it has fully booted up before running the rest of the test. "
            "Default is 120 seconds."
        ),
    )

    return parser


def main() -> int:
    """Main routine

    :return: an return code for checkbox to consume, 1 = failed, 0 = success
    :rtype: int
    """

    args = create_parser().parse_args()

    print("Waiting for boot to finish...")
    if poll_systemctl_is_system_running(args.boot_ready_timeout):
        print("[ OK ] System finished booting!")
    else:
        print(
            "[ WARN ] System did not finish booting",
            "in {} seconds.".format(args.boot_ready_timeout),
            "Continuing reboot checks as-is.",
            file=sys.stderr,
        )

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
                "These services failed:\n{}".format(
                    "\n".join(failed_services)
                ),
                file=sys.stderr,
            )
            service_check_passed = False
        else:
            print("[ OK ] Didn't find any failed system services!")

    if args.do_renderer_check:
        tester = HardwareRendererTester()
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
    exit(main())
