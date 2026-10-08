#!/usr/bin/env python3
"""Map Qualcomm QMMF camera IDs to sensor and CSI wiring metadata."""

import argparse
import datetime
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import textwrap
import time

CAM_SERVER_LOG_LINES = 20000
DT_ROOT = "/sys/firmware/devicetree/base"


def non_negative_integer(value):
    try:
        parsed = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError("must be an integer")
    if parsed < 0:
        raise argparse.ArgumentTypeError("must not be negative")
    return parsed


def build_parser():
    parser = argparse.ArgumentParser(
        description=(
            "Read CamX, kernel, sysfs, and Device Tree data to map "
            "Qualcomm cameras. Runtime capture tests require --test."
        ),
        epilog=(
            "Runtime capture uses qtiqmmfsrc and fakesink without writing "
            "video files. A failed resolution does not prove the sensor "
            "is broken; retry with a mode supported by that sensor."
        ),
    )
    parser.add_argument(
        "--test",
        nargs="?",
        const="__ALL__",
        metavar="IDS",
        help="test comma-separated QMMF IDs (default: all discovered)",
    )
    parser.add_argument("--width", type=non_negative_integer, default=640)
    parser.add_argument("--height", type=non_negative_integer, default=480)
    parser.add_argument("--fps", type=non_negative_integer, default=30)
    parser.add_argument("--seconds", type=non_negative_integer, default=5)
    parser.add_argument(
        "--restart-between",
        action="store_true",
        help="restart cam-server before each runtime test",
    )
    parser.add_argument(
        "--service", default="cam-server.service", metavar="NAME"
    )
    return parser


def run_command(arguments, privileged=False, **kwargs):
    command = list(arguments)
    if privileged and os.geteuid() != 0:
        if shutil.which("sudo"):
            sudo_check = subprocess.run(
                ["sudo", "-n", "true"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
            if sudo_check.returncode == 0:
                command = ["sudo", "-n"] + command
    try:
        return subprocess.run(command, check=False, **kwargs)
    except OSError as error:
        return subprocess.CompletedProcess(
            command, 127, stdout="", stderr=str(error)
        )


def run_output(arguments, privileged=False):
    result = run_command(
        arguments,
        privileged=privileged,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return result.stdout or ""


def parse_camx_enumeration(lines):
    cameras = {}
    for line in lines:
        required_fields = ("frameworkId", "cameraId", "sensorName")
        if not all(field in line for field in required_fields):
            continue
        camera_match = re.search(r"cameraId[ =:]+(\d+)", line)
        sensor_match = re.search(r"sensorName[ =:]+([^, )]+)", line)
        if not camera_match or not sensor_match:
            continue
        sensor_id_match = re.search(r"sensorId[ =:]+(\d+)", line)
        framework_match = re.search(r"frameworkId[ =:]+(\d+)", line)
        logical_match = re.search(r"logicalCamId[ =:]+(\d+)", line)
        camera_id = camera_match.group(1)
        cameras.setdefault(
            camera_id,
            {
                "camera": camera_id,
                "framework": (
                    framework_match.group(1) if framework_match else ""
                ),
                "logical": logical_match.group(1) if logical_match else "",
                "sensor_id": (
                    sensor_id_match.group(1) if sensor_id_match else ""
                ),
                "sensor": sensor_match.group(1),
            },
        )
    return sorted(cameras.values(), key=lambda item: int(item["camera"]))


def parse_kernel_probes(lines):
    probes = {}
    for line in lines:
        if "Probe success for" not in line:
            continue
        sensor_match = re.search(r"Probe success for ([^ ,]+)", line)
        if not sensor_match:
            continue
        slot_match = re.search(r"slot:(\d+)", line)
        chip_match = re.search(r"sensor_id:0x([0-9A-Fa-f]+)", line)
        probes.setdefault(
            sensor_match.group(1),
            {
                "sensor": sensor_match.group(1),
                "slot": slot_match.group(1) if slot_match else "",
                "chip": chip_match.group(1) if chip_match else "",
            },
        )
    return [probes[key] for key in sorted(probes)]


def read_dt_u32(path):
    try:
        with open(path, "rb") as handle:
            value = handle.read(4)
    except OSError:
        return None
    if len(value) != 4:
        return None
    return int.from_bytes(value, byteorder="big")


def read_dt_string(path):
    try:
        with open(path, "rb") as handle:
            value = handle.read()
    except OSError:
        return None
    decoded = value.decode("utf-8", "replace").replace("\x00", "")
    return decoded or None


def _read_first_u32(directory, names):
    for name in names:
        value = read_dt_u32(os.path.join(directory, name))
        if value is not None:
            return value
    return None


def _read_first_string(directory, names):
    for name in names:
        value = read_dt_string(os.path.join(directory, name))
        if value:
            return value
    return None


def read_device_tree(root=DT_ROOT):
    entries = []
    if not os.path.isdir(root):
        return entries
    for directory, _, _ in os.walk(root):
        node_name = os.path.basename(directory)
        if not node_name.startswith(("qcom,cam-sensor", "cam-sensor")):
            continue
        slot = read_dt_u32(os.path.join(directory, "cell-index"))
        phy = _read_first_u32(
            directory, ("csiphy-sd-index", "qcom,csiphy-sd-index")
        )
        cci = _read_first_u32(directory, ("cci-master", "qcom,cci-master"))
        name = _read_first_string(
            directory, ("sensor-name", "qcom,sensor-name")
        )
        if slot is not None or phy is not None:
            entries.append(
                {
                    "slot": str(slot) if slot is not None else "-",
                    "phy": str(phy) if phy is not None else "-",
                    "cci": str(cci) if cci is not None else "-",
                    "name": name or "-",
                    "node": directory,
                }
            )
    entries.sort(
        key=lambda item: (
            int(item["slot"]) if item["slot"].isdigit() else -1,
            item["node"],
        )
    )
    unique_entries = {}
    for entry in entries:
        unique_entries.setdefault(entry["slot"], entry)
    return list(unique_entries.values())


def collect_system_data(service):
    if shutil.which("journalctl"):
        camx_log = run_output(
            [
                "journalctl",
                "-u",
                service,
                "--no-pager",
                "-n",
                str(CAM_SERVER_LOG_LINES),
            ],
            privileged=True,
        )
    else:
        camx_log = ""
    dmesg_log = run_output(["dmesg"], privileged=True)
    return camx_log.splitlines(), dmesg_log.splitlines()


def find_device_tree_entry(device_tree, slot):
    for entry in device_tree:
        if entry["slot"] == slot:
            return entry
    return None


def print_table(headers, rows, widths):
    separator = "-+-".join("-" * width for width in widths)
    header = " | ".join(
        value.ljust(width) for value, width in zip(headers, widths)
    )
    print(header)
    print(separator)
    for row in rows:
        cells = [
            textwrap.wrap(
                str(value),
                width=width,
                break_long_words=True,
                break_on_hyphens=False,
            )
            or [""]
            for value, width in zip(row, widths)
        ]
        for line_index in range(max(len(cell) for cell in cells)):
            line = [
                cell[line_index] if line_index < len(cell) else ""
                for cell in cells
            ]
            formatted = " | ".join(
                value.ljust(width) for value, width in zip(line, widths)
            )
            print(formatted)


def print_report(service, cameras, probes, device_tree):
    print("Qualcomm camera mapping")
    print("=======================")
    print("Camera service: {}\n".format(service))
    if not cameras:
        print(
            "No CamX camera enumeration was found in {} logs.".format(service)
        )
        print("Try restarting the service, then rerun this script:")
        print("  sudo systemctl restart {}\n".format(service))
    else:
        probes_by_sensor = {item["sensor"]: item for item in probes}
        rows = []
        for camera in cameras:
            probe = probes_by_sensor.get(camera["sensor"])
            slot = ""
            chip = ""
            source = "CamX"
            if probe:
                slot = probe["slot"]
                chip = probe["chip"]
                source = "CamX+klog"
            elif camera["sensor_id"]:
                slot = camera["sensor_id"]
            dt_entry = (
                find_device_tree_entry(device_tree, slot) if slot else None
            )
            phy = dt_entry["phy"] if dt_entry else ""
            cci = dt_entry["cci"] if dt_entry else ""
            if dt_entry:
                source += "+DT"
            rows.append(
                [
                    camera["camera"],
                    camera["sensor"],
                    slot or "-",
                    chip or "-",
                    phy or "-",
                    cci or "-",
                    source,
                ]
            )
        print_table(
            ["QMMF", "CamX sensor", "Slot", "Chip ID", "CSI", "CCI", "Source"],
            rows,
            [5, 22, 4, 10, 4, 4, 12],
        )

    print("\nKernel sensor probes")
    print("--------------------")
    if probes:
        for probe in probes:
            print(
                "sensor={:<12} slot={:<3} sensor_id={}".format(
                    probe["sensor"], probe["slot"] or "-", probe["chip"] or "-"
                )
            )
    else:
        print('No "Probe success for ..." records found in dmesg.')

    print("\nDevice Tree camera wiring")
    print("-------------------------")
    if device_tree:
        print_table(
            ["Slot", "CSI", "CCI", "Sensor", "DT node"],
            [
                [
                    entry["slot"],
                    entry["phy"],
                    entry["cci"],
                    entry["name"],
                    os.path.basename(entry["node"]),
                ]
                for entry in device_tree
            ],
            [5, 4, 4, 22, 30],
        )
    else:
        print("No camera sensor nodes with CSI PHY metadata found.")


def camera_ids_to_test(test_option, cameras):
    if test_option is None:
        return None
    if test_option == "__ALL__":
        camera_ids = [camera["camera"] for camera in cameras]
    else:
        camera_ids = test_option.split(",")
    if not camera_ids or any(
        not re.fullmatch(r"\d+", item) for item in camera_ids
    ):
        raise ValueError(
            "invalid camera IDs; expected comma-separated integers"
        )
    return camera_ids


def run_capture(camera, args, output_path):
    pipeline = [
        "gst-launch-1.0",
        "-e",
        "qtiqmmfsrc",
        "camera={}".format(camera),
        "!",
        "video/x-raw,format=NV12,width={},height={},framerate={}/1".format(
            args.width, args.height, args.fps
        ),
        "!",
        "fakesink",
        "sync=false",
    ]
    try:
        with open(output_path, "w", encoding="utf-8") as output:
            process = subprocess.Popen(
                pipeline,
                stdout=output,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
            )
            timed_out = False
            try:
                process.wait(timeout=args.seconds)
            except subprocess.TimeoutExpired:
                timed_out = True
                process.send_signal(signal.SIGINT)
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
        return 124 if timed_out else process.returncode
    except OSError as error:
        with open(output_path, "w", encoding="utf-8") as output:
            output.write(str(error))
        return 127


def classify_capture(return_code, output):
    if re.search(r"Got EOS|EOS received", output):
        return "PASS"
    if re.search(r"StartVideoTracks Failed|Failed to start stream", output):
        return "FAIL-STREAM-CONFIG"
    if re.search(r"Failed to Open Camera|Recorder Connect failed", output):
        return "FAIL-CAMERA-SERVICE"
    if return_code in (124, 130):
        return "TIMEOUT"
    if return_code == 0:
        return "PASS"
    return "FAIL"


def capture_metadata(service, since):
    sensor = ""
    if shutil.which("journalctl"):
        journal = run_output(
            ["journalctl", "-u", service, "--since", since, "--no-pager"],
            privileged=True,
        )
        sensors = re.findall(r"SensorName:([^ ]+)", journal)
        if sensors:
            sensor = sensors[-1]
    dmesg = run_output(["dmesg"], privileged=True)
    if not sensor:
        sensors = re.findall(r"CAM_START_DEV Success for ([^ ]+)", dmesg)
        if sensors:
            sensor = sensors[-1]
    phys = re.findall(r"CAM_START_PHYDEV: (\d+)", dmesg)
    return sensor or "-", phys[-1] if phys else "-"


def run_tests(args, camera_ids):
    if not shutil.which("gst-launch-1.0"):
        raise RuntimeError("gst-launch-1.0 is required for --test")
    inspect_result = run_command(
        ["gst-inspect-1.0", "qtiqmmfsrc"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    if inspect_result.returncode != 0:
        raise RuntimeError("qtiqmmfsrc is not available")

    print(
        "\nRuntime tests ({}x{}@{}, {}s each)".format(
            args.width, args.height, args.fps, args.seconds
        )
    )
    print("----------------------------------------")
    with tempfile.TemporaryDirectory(
        prefix="dragonwing-camera-map-"
    ) as temp_dir:
        for camera in camera_ids:
            if args.restart_between:
                print(
                    "camera={}: restarting {} ... ".format(
                        camera, args.service
                    ),
                    end="",
                )
                result = run_command(
                    ["systemctl", "restart", args.service],
                    privileged=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                if result.returncode == 0:
                    time.sleep(3)
                    print("done")
                else:
                    print("failed")

            start_marker = datetime.datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            )
            output_path = os.path.join(
                temp_dir, "camera-{}.log".format(camera)
            )
            print("camera={}: ".format(camera), end="", flush=True)
            return_code = run_capture(camera, args, output_path)
            try:
                with open(
                    output_path, encoding="utf-8", errors="replace"
                ) as handle:
                    output = handle.read()
            except OSError:
                output = ""
            result = classify_capture(return_code, output)
            sensor, phy = capture_metadata(args.service, start_marker)
            print(
                "{} (rc={}, sensor={}, csiphy={})".format(
                    result, return_code, sensor, phy
                )
            )
            if result != "PASS":
                details = [
                    line
                    for line in output.splitlines()
                    if re.search(
                        r"ERROR:|Failed|Invalid stream|maximum|"
                        r"max Res|requested Res",
                        line,
                    )
                ]
                for line in details[-8:]:
                    print("  {}".format(line))


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        camx_lines, dmesg_lines = collect_system_data(args.service)
        cameras = parse_camx_enumeration(camx_lines)
        probes = parse_kernel_probes(dmesg_lines)
        device_tree = read_device_tree()
        print_report(args.service, cameras, probes, device_tree)
        camera_ids = camera_ids_to_test(args.test, cameras)
        if camera_ids is None:
            return 0
        if not camera_ids:
            raise ValueError(
                "no camera IDs were discovered; pass IDs explicitly"
            )
        run_tests(args, camera_ids)
    except (RuntimeError, ValueError) as error:
        print("error: {}".format(error), file=sys.stderr)
        return 1

    print("\nNotes")
    print("-----")
    print("* QMMF camera ID comes from CamX frameworkId/cameraId enumeration")
    print(
        "* Sensor slot comes from the kernel probe and Device Tree cell-index."
    )
    print(
        "* CSI PHY comes from Device Tree csiphy-sd-index and "
        "CAM_START_PHYDEV."
    )
    print(
        "* Do not use runtime CSID as physical wiring; it may be "
        "dynamically allocated."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
