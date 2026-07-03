#!/usr/bin/env python3
import os
import sys
import time
import logging
import shlex
import subprocess
import argparse
import hashlib
from pathlib import Path

SYS_THERMAL_PATH = "/sys/class/thermal"


def init_logger():
    """
    Set the logger to log DEBUG and INFO to stdout, and
    WARNING, ERROR, CRITICAL to stderr.
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    logger_format = "%(asctime)s %(levelname)-8s %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"

    # Log DEBUG and INFO to stdout, others to stderr
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setFormatter(logging.Formatter(logger_format, date_format))

    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setFormatter(logging.Formatter(logger_format, date_format))

    stdout_handler.setLevel(logging.DEBUG)
    stderr_handler.setLevel(logging.WARNING)

    # Add a filter to the stdout handler to limit log records to
    # INFO level and below
    stdout_handler.addFilter(lambda record: record.levelno <= logging.INFO)

    root_logger.addHandler(stderr_handler)
    root_logger.addHandler(stdout_handler)

    return root_logger


class ThermalMonitor:

    def __init__(self, name):
        self._name = name
        self.root_node = Path(SYS_THERMAL_PATH).joinpath(self._name)
        self.type_node = self.root_node.joinpath("type")
        self.temp_node = self.root_node.joinpath("temp")
        self.mode_node = self.root_node.joinpath("mode")
        self.initial_temp = None

    def _read_node(self, node):
        if node.exists():
            try:
                return node.read_text().strip("\n")
            except Exception as e:
                raise SystemExit(
                    "Failed to read node: {}\n{}".format(str(node), e)
                )
        else:
            raise FileNotFoundError("{} file not exists".format(str(node)))

    @property
    def name(self):
        return self._name

    @property
    def type(self):
        return self._read_node(self.type_node)

    @property
    def temperature(self):
        temp = self._read_node(self.temp_node)
        if not temp.isnumeric():
            raise ValueError("temperate value is not a number!")
        return temp

    @property
    def mode(self):
        return self._read_node(self.mode_node)

    def _read_optional_node(self, node):
        if node.exists():
            return self._read_node(node)
        return ""

    def _resolve_optional_node_path(self, node):
        if node.exists():
            return str(node.resolve(strict=False))
        return ""

    @property
    def sysfs_path(self):
        return str(self.root_node.resolve(strict=False))

    @property
    def device_path(self):
        return self._resolve_optional_node_path(
            self.root_node.joinpath("device")
        )

    @property
    def of_node_path(self):
        return self._resolve_optional_node_path(
            self.root_node.joinpath("device", "of_node")
        )

    @property
    def firmware_node_path(self):
        return self._read_optional_node(
            self.root_node.joinpath("device", "firmware_node", "path")
        )

    @property
    def cdev_types(self):
        """Sorted tuple of cooling device types bound to this zone.

        Cooling devices are discovered via cdev* symlinks.

        cdev* entries are part of the official thermal sysfs ABI and
        are present whenever a cooling device is associated with the
        zone. They provide a richer identity signal than falling all
        the way back to just ``type``
        on zones that have no physical device node.

        Note: cdev bindings can change at runtime if cooling devices
        are rebound, so this value is less stable than
        of_node/firmware_node/device.
        """
        types = []
        for entry in sorted(self.root_node.glob("cdev[0-9]*")):
            # Only match cdevN, not cdevN_trip_point and similar files.
            if not entry.name[4:].isdigit():
                continue
            t = self._read_optional_node(entry.joinpath("type"))
            if t:
                types.append(t)
        return tuple(sorted(types))

    @property
    def stable_source(self):
        return (
            self.of_node_path
            or self.firmware_node_path
            or self.device_path
            or "|".join(self.cdev_types)
            or self.type
        )

    @property
    def stable_id(self):
        stable_data = "{}|{}".format(self.type, self.stable_source)
        return hashlib.sha1(stable_data.encode()).hexdigest()[:12]


def _load_snapshot(snapshot_path):
    entries = {}
    for line in Path(snapshot_path).read_text().splitlines():
        if not line:
            continue
        stable_id, name, zone_type, stable_source = line.split("\t", 3)
        entries[stable_id] = {
            "name": name,
            "type": zone_type,
            "stable_source": stable_source,
        }
    return entries


def _reconcile_legacy_id_upgrades(
    before_entries, after_entries, missing_ids, new_ids
):
    """Best-effort mapping for stable_id algorithm upgrades.

    This is intended for snapshots produced before/after stable_id strategy 
    changes where the thermal zone identity did not actually change.
    """
    after_by_name_type = {}
    for stable_id in new_ids:
        entry = after_entries[stable_id]
        key = (entry["name"], entry["type"])
        after_by_name_type.setdefault(key, []).append(stable_id)

    upgraded = []
    missing_remaining = []
    new_remaining = set(new_ids)

    for stable_id in missing_ids:
        before = before_entries[stable_id]
        key = (before["name"], before["type"])
        matches = after_by_name_type.get(key, [])
        if len(matches) != 1:
            missing_remaining.append(stable_id)
            continue

        upgraded_id = matches[0]
        if upgraded_id not in new_remaining:
            missing_remaining.append(stable_id)
            continue

        upgraded.append(
            (stable_id, upgraded_id, before, after_entries[upgraded_id])
        )
        new_remaining.remove(upgraded_id)

    return upgraded, sorted(missing_remaining), sorted(new_remaining)


def resolve_thermal_zone_name(stable_id, zone_type=None):
    for thermal in sorted(Path(SYS_THERMAL_PATH).glob("thermal_zone*")):
        node = ThermalMonitor(thermal.name)
        if node.stable_id != stable_id:
            continue
        if zone_type is not None and node.type != zone_type:
            continue
        return node.name

    return None


def check_temperature(current, initial):
    logging.info("Initial value: %s, current value: %s", initial, current)
    return int(current) != 0 and current != initial


def ignore_temp_check_enabled(zone_type):
    value = os.getenv("TZ_IGNORE_TEMP_CHECK", "").strip()
    if not value:
        return False

    if value.lower() == "all":
        return True

    ignored_types = {entry.strip() for entry in value.split("|")}
    return zone_type in ignored_types


def check_temperature_readable(target_name, thermal_op):
    current_value = thermal_op.temperature
    logging.info(
        "# TZ_IGNORE_TEMP_CHECK matches %s, readable temperature is %s",
        thermal_op.type,
        current_value,
    )
    logging.info(
        "# Temperature readability check for %s (%s) thermal passed",
        target_name,
        thermal_op.type,
    )


def monitor_temperature_change(target_name, thermal_op, duration, cmd):
    initial_value = thermal_op.temperature

    result = False
    proc = None
    try:
        proc = subprocess.Popen(shlex.split(cmd))
    except Exception:
        # Bypass any error while issue command through Popen
        # Due to the command here is trying to increase system loading
        pass

    for _ in range(duration):
        cur_temp = thermal_op.temperature
        result = check_temperature(cur_temp, initial_value)
        if result:
            logging.info(
                "# The temperature of %s (%s) thermal has been altered",
                target_name,
                thermal_op.type,
            )
            break
        time.sleep(1)
    if proc and proc.poll() is None:
        # kill the subprocess if it is still alive
        proc.kill()

    if result is False:
        logging.error(
            "# The temperature of the %s (%s) thermal remains consistently at %s",
            target_name,
            thermal_op.type,
            initial_value,
        )
        raise SystemExit(1)


def thermal_monitor_test(args):
    target_name = args.name
    if target_name is None and args.stable_id is not None:
        target_name = resolve_thermal_zone_name(
            args.stable_id, zone_type=args.zone_type
        )
        if target_name is None:
            raise SystemExit(
                "Error: Unable to resolve thermal zone for "
                "stable_id={}".format(args.stable_id)
            )

    if args.extra_commands == "stress-ng":
        cmd = (
            "stress-ng --cpu 0 --io 4 --vm 2 " "--vm-bytes 128M --timeout {}s"
        ).format(args.duration)
    else:
        cmd = args.extra_commands

    thermal_op = ThermalMonitor(target_name)
    ignore_temp_check = ignore_temp_check_enabled(thermal_op.type)
    logging.info(
        "# Monitor the temperature of %s (%s) thermal around %s seconds",
        target_name,
        thermal_op.type,
        args.duration,
    )
    if thermal_op.mode == "disabled":
        raise SystemExit(
            "Error: The {}-{} thermal is disabled".format(
                thermal_op.name, thermal_op.type
            )
        )

    if ignore_temp_check:
        check_temperature_readable(target_name, thermal_op)
        return

    monitor_temperature_change(
        target_name,
        thermal_op,
        args.duration,
        cmd,
    )


def dump_thermal_zones(args):

    for thermal in sorted(Path(SYS_THERMAL_PATH).glob("thermal_zone*")):
        node = ThermalMonitor(thermal.name)
        print(
            (
                "name: {}\nmode: {}\ntype: {}\nstable_id: {}\n"
                "sysfs_path: {}\ndevice_path: {}\nof_node_path: {}\n"
                "firmware_node_path: {}\ncdev_types: {}\n"
            ).format(
                node.name,
                node.mode,
                node.type,
                node.stable_id,
                node.sysfs_path,
                node.device_path,
                node.of_node_path,
                node.firmware_node_path,
                "|".join(node.cdev_types),
            )
        )


def snapshot_thermal_zones(args):
    rows = []
    for thermal in sorted(Path(SYS_THERMAL_PATH).glob("thermal_zone*")):
        node = ThermalMonitor(thermal.name)
        rows.append(
            "{}\t{}\t{}\t{}".format(
                node.stable_id,
                node.name,
                node.type,
                node.stable_source,
            )
        )

    snapshot = "\n".join(rows) + "\n"
    if args.output is None:
        print(snapshot, end="")
    else:
        Path(args.output).write_text(snapshot)


def compare_thermal_snapshots(args):
    before_entries = _load_snapshot(args.before)
    after_entries = _load_snapshot(args.after)

    before_ids = set(before_entries)
    after_ids = set(after_entries)
    common_ids = sorted(before_ids & after_ids)
    missing_ids = sorted(before_ids - after_ids)
    new_ids = sorted(after_ids - before_ids)

    stable_id_upgraded = []
    if args.allow_legacy_id_upgrade:
        stable_id_upgraded, missing_ids, new_ids = (
            _reconcile_legacy_id_upgrades(
                before_entries,
                after_entries,
                missing_ids,
                new_ids,
            )
        )

    renumbered = []
    identity_changed = []
    for stable_id in common_ids:
        before = before_entries[stable_id]
        after = after_entries[stable_id]
        if before["name"] != after["name"]:
            renumbered.append((stable_id, before, after))
        if (
            before["type"] != after["type"]
            or before["stable_source"] != after["stable_source"]
        ):
            identity_changed.append((stable_id, before, after))

    print(
        (
            "summary: before={} after={} missing={} new={} "
            "stable_id_upgraded={} identity_changed={} renumbered={}"
        ).format(
            len(before_ids),
            len(after_ids),
            len(missing_ids),
            len(new_ids),
            len(stable_id_upgraded),
            len(identity_changed),
            len(renumbered),
        )
    )

    for old_id, new_id, before, after in stable_id_upgraded:
        print(
            (
                "stable_id_upgraded: type={} {} -> {} name={} "
                "stable_source={} -> {}"
            ).format(
                before["type"],
                old_id,
                new_id,
                before["name"],
                before["stable_source"],
                after["stable_source"],
            )
        )

    for stable_id, before, after in renumbered:
        print(
            "renumbered: type={} stable_id={} {} -> {}".format(
                before["type"],
                stable_id,
                before["name"],
                after["name"],
            )
        )

    for stable_id, before, after in identity_changed:
        print(
            "identity_changed: stable_id={} {}|{} -> {}|{}".format(
                stable_id,
                before["type"],
                before["stable_source"],
                after["type"],
                after["stable_source"],
            )
        )

    for stable_id in missing_ids:
        before = before_entries[stable_id]
        print(
            "missing_after: type={} stable_id={} name={}".format(
                before["type"],
                stable_id,
                before["name"],
            )
        )

    for stable_id in new_ids:
        after = after_entries[stable_id]
        print(
            "new_after: type={} stable_id={} name={}".format(
                after["type"],
                stable_id,
                after["name"],
            )
        )

    if args.fail_on_diff and (
        missing_ids
        or new_ids
        or stable_id_upgraded
        or identity_changed
        or renumbered
    ):
        raise SystemExit(1)


def register_arguments():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="Thermal temperature Tests",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Turn on debug level output for extra info during test run.",
    )

    sub_parsers = parser.add_subparsers(
        help="Thermal test type", dest="test_type", required=True
    )

    monitor_parser = sub_parsers.add_parser("monitor")
    zone_selector = monitor_parser.add_mutually_exclusive_group(required=True)
    zone_selector.add_argument("-n", "--name", type=str)
    zone_selector.add_argument("--stable-id", type=str)
    monitor_parser.add_argument(
        "--zone-type",
        type=str,
        default=None,
        help="Use with --stable-id to further disambiguate zones",
    )
    monitor_parser.add_argument(
        "-d",
        "--duration",
        type=int,
        default=60,
        help="the time period to monitor thermal temperature",
    )
    monitor_parser.add_argument(
        "--extra-commands",
        type=str,
        default="stress-ng",
        help=(
            "the command is for increase the system loading, "
            "will apply stress-ng by default"
        ),
    )
    monitor_parser.set_defaults(test_type=thermal_monitor_test)

    dump_parser = sub_parsers.add_parser("dump")
    dump_parser.set_defaults(test_type=dump_thermal_zones)

    snapshot_parser = sub_parsers.add_parser("snapshot")
    snapshot_parser.add_argument(
        "-o",
        "--output",
        type=str,
        default=None,
        help="Write snapshot to a TSV file",
    )
    snapshot_parser.set_defaults(test_type=snapshot_thermal_zones)

    compare_parser = sub_parsers.add_parser("compare")
    compare_parser.add_argument("--before", required=True, type=str)
    compare_parser.add_argument("--after", required=True, type=str)
    compare_parser.add_argument(
        "--allow-legacy-id-upgrade",
        action="store_true",
        help=(
            "Best-effort compatibility mode for snapshot comparison across "
            "stable_id algorithm upgrades"
        ),
    )
    compare_parser.add_argument(
        "--fail-on-diff",
        action="store_true",
        help="Exit with status 1 when compare detects any differences",
    )
    compare_parser.set_defaults(test_type=compare_thermal_snapshots)

    args = parser.parse_args()
    return args


def main():
    args = register_arguments()
    logger = init_logger()
    if args.debug:
        logger.setLevel(logging.DEBUG)

    args.test_type(args)


if __name__ == "__main__":
    main()
