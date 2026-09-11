#!/usr/bin/env python3
import subprocess
import argparse
import shlex
import os
import json
import logging
import re

RESOLUTIONS = {
    "2160p": {"width": 3840, "height": 2160},
    "1440p": {"width": 2560, "height": 1440},
    "1080p": {"width": 1920, "height": 1080},
    "720p": {"width": 1280, "height": 720},
    "480p": {"width": 640, "height": 480},
    "240p": {"width": 320, "height": 240},
}

logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
    ],
)


def normalize_sensor_name(sensor_name):
    """Normalize CamX sensor names to the supported_camera.json keys."""
    value = (sensor_name or "").strip()
    if not value:
        return value

    lower = value.lower()
    if lower.startswith("cmk_"):
        return lower[len("cmk_") :]
    return value


def run_cmd(command):
    ret = subprocess.run(
        shlex.split(command),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        encoding="utf-8",
    )
    return ret


def read_json_file(path):
    """Read the content of a JSON file"""
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        logging.error("Fail to load the '{}' file".format(path))
        raise


def find_camx_camera_ids_for_sensor(sensor_name):
    """Map a sensor name to the CamX camera IDs discovered on the board."""
    try:
        ret = run_cmd("journalctl -u cam-server.service --no-pager")
    except Exception:
        return []

    sensor_name = normalize_sensor_name(sensor_name)
    if not sensor_name:
        return []

    matches = []
    for line in (ret.stdout or "").splitlines():
        if "cameraId" not in line or "sensorName" not in line:
            continue

        camera_match = re.search(r"cameraId\s*[:=]\s*(\d+)", line)
        sensor_match = re.search(r"sensorName\s*[:=]\s*([^,\s)]+)", line)
        if not camera_match or not sensor_match:
            continue

        camx_sensor = normalize_sensor_name(sensor_match.group(1).strip())
        if camx_sensor.lower() != sensor_name.lower():
            continue

        matches.append(camera_match.group(1))

    return sorted(set(matches), key=int)


def read_u32(path):
    """Read a 32-bit value from a Device Tree property file."""
    try:
        with open(path, "rb") as handle:
            data = handle.read(4)
            if len(data) != 4:
                return None
            return int.from_bytes(data, byteorder="big")
    except OSError:
        return None


def parse_journal_csi_for_sensor(sensor_name, journal_lines):
    """Extract CSI metadata for one sensor from journal output."""
    matches = {}
    for line in journal_lines:
        if "Probe success for" in line:
            sensor_match = re.search(r"Probe success for ([^ ,]+)", line)
            slot_match = re.search(r"slot:(\d+)", line)
            chip_match = re.search(r"sensor_id:0x([0-9A-Fa-f]+)", line)
            if (
                sensor_match
                and sensor_match.group(1).lower() == sensor_name.lower()
            ):
                matches = {
                    "slot": int(slot_match.group(1)) if slot_match else None,
                    "chip": (
                        chip_match.group(1).upper() if chip_match else None
                    ),
                }
                break

        if "CAM_START_PHYDEV:" in line and "csiphy" not in matches:
            phy_match = re.search(r"CAM_START_PHYDEV: (\d+)", line)
            if phy_match:
                matches["csiphy"] = int(phy_match.group(1))

        if "SensorName:" in line and "slot" not in matches:
            sensor_match = re.search(r"SensorName:([^ ]+)", line)
            if (
                sensor_match
                and sensor_match.group(1).lower() == sensor_name.lower()
            ):
                slot_match = re.search(r"slot:(\d+)", line)
                if slot_match:
                    matches["slot"] = int(slot_match.group(1))

    return matches


def find_dt_csi_for_sensor(sensor_name):
    """Look up CSI metadata from the Device Tree when available."""
    matches = {}
    try:
        dt_root = "/sys/firmware/devicetree/base"
        if not os.path.isdir(dt_root):
            return matches

        for root, _, _ in os.walk(dt_root):
            if not any(
                name in root for name in ("qcom,cam-sensor", "cam-sensor")
            ):
                continue

            name_path = os.path.join(root, "sensor-name")
            alt_name_path = os.path.join(root, "qcom,sensor-name")
            for path in (name_path, alt_name_path):
                if not os.path.exists(path):
                    continue
                try:
                    with open(path, "rb") as handle:
                        dt_name = (
                            handle.read()
                            .decode("utf-8", "ignore")
                            .strip("\x00")
                        )
                except OSError:
                    continue

                if dt_name.lower() != sensor_name.lower():
                    continue

                slot_path = os.path.join(root, "cell-index")
                phy_path = os.path.join(root, "csiphy-sd-index")
                alt_phy_path = os.path.join(root, "qcom,csiphy-sd-index")
                cci_path = os.path.join(root, "cci-master")
                alt_cci_path = os.path.join(root, "qcom,cci-master")

                slot = read_u32(slot_path)
                phy = read_u32(phy_path) if os.path.exists(phy_path) else None
                if phy is None:
                    phy = read_u32(alt_phy_path)
                cci = read_u32(cci_path) if os.path.exists(cci_path) else None
                if cci is None:
                    cci = read_u32(alt_cci_path)

                matches.update(
                    {
                        "slot": (
                            slot if slot is not None else matches.get("slot")
                        ),
                        "csiphy": (
                            phy if phy is not None else matches.get("csiphy"),
                        ),
                        "cci": (
                            cci if cci is not None else matches.get("cci"),
                        ),
                    }
                )
                return matches
    except Exception:
        pass

    return matches


def find_csi_interface_for_sensor(sensor_name):
    """Look up the CSI PHY/slot/CCI wiring for a sensor name.

    Prefer the persisted journal logs over transient dmesg buffers, since the
    latter can be flushed or rotated by the time the test runs.
    """
    sensor_name = normalize_sensor_name(sensor_name)
    if not sensor_name:
        return {}

    matches = {}
    journal_cmds = [
        "journalctl -u cam-server.service --no-pager",
        "journalctl -k --no-pager",
    ]
    for cmd in journal_cmds:
        try:
            journal = run_cmd(cmd)
        except Exception:
            continue

        matches = parse_journal_csi_for_sensor(
            sensor_name,
            (journal.stdout or "").splitlines(),
        )
        if matches:
            break

    dt_matches = find_dt_csi_for_sensor(sensor_name)
    if dt_matches:
        for key, value in dt_matches.items():
            if value is not None:
                matches[key] = value

    return matches


def parse_camera_entry(entry):
    """Parse a single requested camera entry into a normalized tuple."""
    if ":" not in entry:
        name = normalize_sensor_name(entry)
        camera_ids = find_camx_camera_ids_for_sensor(name)
        csi = find_csi_interface_for_sensor(name)
        return (None, name, camera_ids, csi)

    left, right = entry.split(":", 1)
    left = left.strip()
    right = right.strip()

    if left.isdigit() and right:
        name = normalize_sensor_name(right)
        return (left, name, [left], find_csi_interface_for_sensor(name))

    if right.isdigit():
        name = normalize_sensor_name(left)
        camera_id = right
        return (
            camera_id,
            name,
            [camera_id],
            find_csi_interface_for_sensor(name),
        )

    name = normalize_sensor_name(right)
    return (left, name, [left], find_csi_interface_for_sensor(name))


def resolve_camera_entries(camera_entries):
    """Return camera entries as (index, name, camera_ids, csi) for display."""
    return [parse_camera_entry(entry) for entry in camera_entries]


def normalize_supported_camera_name(name, supported_cameras):
    """Return the canonical supported-camera name, if available."""
    if name in supported_cameras:
        return name

    for candidate in supported_cameras:
        if candidate.lower() == name.lower():
            return candidate
    return None


def get_csi_label(csi):
    """Convert CSI metadata to a display label."""
    if csi.get("csiphy") is not None:
        return str(csi["csiphy"])
    if csi.get("slot") is not None:
        return str(csi["slot"])
    return "unknown"


def print_camera_resolution(name, camera_id, csi, supported_cameras):
    """Print one resolved camera entry and its supported resolutions."""
    csi_label = get_csi_label(csi)
    for rate in supported_cameras[name]:
        print("name: {}".format(name))
        print("camera: {}".format(camera_id))
        print("csi: {}".format(csi_label))
        print("resolution: {}".format(rate))
        print("width: {}".format(RESOLUTIONS[rate]["width"]))
        print("height: {}".format(RESOLUTIONS[rate]["height"]))
        print()


def get_camera_list(args):
    """Print connected cameras and their supported resolutions."""

    path = os.path.expandvars(
        os.path.join(
            "$PLAINBOX_PROVIDER_DATA",
            "Dragonwing",
            "camera_resolution",
            "supported_cameras.json",
        )
    )
    supported_cameras = read_json_file(path)

    cameras = args.cameras.split() if args.cameras else []
    if not cameras:
        logging.error("No camera names or IDs were provided")
        return 1

    raise_error = getattr(args, "raise_error", True)
    found_camera = False
    issue_names = []
    for _, name, camera_ids, csi in resolve_camera_entries(cameras):
        normalized_name = normalize_supported_camera_name(
            name,
            supported_cameras,
        )
        if normalized_name is None:
            if raise_error:
                issue_names.append(name)
            continue
        name = normalized_name

        if not camera_ids:
            if raise_error:
                issue_names.append(name)
            continue

        found_camera = True
        for camera_id in camera_ids:
            print_camera_resolution(name, camera_id, csi, supported_cameras)

    if raise_error and issue_names:
        logging.error(
            "Unavailable cameras: %s",
            ", ".join(sorted(set(issue_names))),
        )
        return 1
    if not found_camera and raise_error:
        return 1
    return 0


def main():
    commands = {
        "camera-list": get_camera_list,
    }
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "subcommand", help=("subcommand to run"), choices=commands.keys()
    )
    parser.add_argument(
        "-c",
        "--cameras",
        type=str,
        help="connected cameras as either 'name' or 'name:id' / 'index:name'",
    )
    parser.add_argument(
        "--skip-unavailable",
        action="store_false",
        dest="raise_error",
        default=True,
        help="skip unavailable cameras instead of raising an error",
    )
    args = parser.parse_args()

    return commands[args.subcommand](args)


if __name__ == "__main__":
    raise SystemExit(main())
