#!/usr/bin/env python3
# This file is part of Checkbox.
#
# Copyright 2023 Canonical Ltd.
# Written by:
#   Hanhsuan Lee <hanhsuan.lee@canonical.com>
#
# Checkbox is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3,
# as published by the Free Software Foundation.
#
# Checkbox is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Checkbox.  If not, see <http://www.gnu.org/licenses/>.

import argparse
import difflib
import json
import logging
import re
import shlex
import subprocess
import sys
import time
from enum import IntEnum
import typing as t

import gi

gi.require_version("Gst", "1.0")
gi.require_version("GLib", "2.0")
from gi.repository import (
    GLib,  # noqa: E402
    Gst,  # noqa: E402
)


class PipewireTestError(IntEnum):
    """
    A class used to define PipewireTest Error code

    :attr NO_ERROR: process success
    :type NO_ERROR: int

    :attr NOT_DETECTED: couldn't find specific device
    :type NOT_DETECTED: int

    :attr NO_AVAILABLE_PORT: couldn't find available port
    :type NO_AVAILABLE_PORT: int

    :attr NO_SPECIFIC_DEVICE: couldn't find specific device
    :type NO_SPECIFIC_DEVICE: int

    :attr PIPELINE_PROCESS_FAIL: gst pipeline process failed
    :type PIPELINE_PROCESS_FAIL: int

    :attr NO_CHANGE_DETECTED: couldn't detect audio setting is changed
    :type NO_CHANGE_DETECTED: int
    """

    NO_ERROR = 0
    NOT_DETECTED = -1
    NO_AVAILABLE_PORT = -2
    NO_SPECIFIC_DEVICE = -3
    PIPELINE_PROCESS_FAIL = -4
    NO_CHANGE_DETECTED = -5
    NOT_REAL_DEVICE = -6


class PipewireTest:
    """
    A class used to test pipewire functions

    """

    logger = logging.getLogger()

    def _get_pw_type(self, media_class: str) -> str:
        """
        convert sink to Output and source to Input

        :param media_class: sink(s) or source(s)
        :type media_class: str

        :returns: "Output", "Input" or "UNKNOWN CLASS"
        :"rtype": str
        """
        if media_class.lower() in ["sink", "sinks"]:
            return "Output"
        elif media_class.lower() in ["source", "sources"]:
            return "Input"
        else:
            self.logger.info("Media class:[{}] is unknown".format(media_class))
            return "UNKNOWN CLASS"

    def _get_pw_dump(
        self, p_type: 't.Literal["Device", "Node"]'
    ) -> "list[dict[str, t.Any]]":
        """
        Use to convert the json output of pw-dump to dict object

        :param p_type: pipewire object type, such as "Node"
        :type p_type: str

        :returns: pw-dump in dict data structure
        :"rtype": dict
        """
        pw_dump = subprocess.check_output(
            "pw-dump {}".format(p_type), shell=True, universal_newlines=True
        )
        try:
            return json.loads(pw_dump)
        except (json.decoder.JSONDecodeError, TypeError):
            self.logger.error("pw-dump {} failed !!!".format(p_type))
            return []

    def generate_pw_media_class(self, media_type, media_class) -> str:
        """
        Combine media_type and media_class to pw-dump format,
        such as "Audio/Sink".

        :param media_type: For now only support Audio or Video
        :type media_type: str

        :param media_class: For now only support Sinks* or Sources*
        :type media_class: str

        :returns: pipewire style media.class or "UNKNOWN CLASS"
        :"rtype": str
        """
        if media_type.lower() == "audio":
            mtype = "Audio"
        elif media_type.lower() == "video":
            mtype = "Video"
        else:
            self.logger.info("Media type:[{}] is unknown".format(media_type))
            return "UNKNOWN TYPE"

        if media_class.lower() in ["sink", "sinks"]:
            return "{}/Sink".format(mtype)
        elif media_class.lower() in ["source", "sources"]:
            return "{}/Source".format(mtype)
        else:
            self.logger.info("Media class:[{}] is unknown".format(media_class))
            return "UNKNOWN CLASS"

    def detect_device(self, media_type, media_class) -> int:
        """
        detect specific device is on this system or not.
        This function parse output of pw-dump to check, the device type
        equals PipeWire:Interface:Node and media.class equals args.

        :param media_type: For now only support Audio or Video
        :type media_type: str

        :param media_class: For now only support Sinks* or Sources*
        :type media_class: str

        :returns: "NOT_DETECTED" or "NO_ERROR"
        :"rtype": int
        """
        mclass = self.generate_pw_media_class(media_type, media_class)
        if mclass in ["UNKNOWN CLASS", "UNKNOWN TYPE"]:
            return PipewireTestError.NOT_DETECTED
        clients = self._get_pw_dump("Node")

        detected_flag = False
        for client in clients:
            props = client["info"]["props"]
            if mclass == props.get("media.class"):
                self.logger.info(
                    "device id:[{}] media.class:[{}] node.name:[{}]".format(
                        client["id"], mclass, props.get("node.name")
                    )
                )
                detected_flag = True
        if detected_flag:
            return PipewireTestError.NO_ERROR
        self.logger.info("media.class:[{}] couldn't find".format(mclass))
        return PipewireTestError.NOT_DETECTED

    def select_device(self, media_type, media_class, device):
        """
        Set desired device as default
        This function parse output of pw-dump to find, the device type
        equals PipeWire:Interface:Node and media.class equals args.

        :param media_type: For now only support Audio or Video
        :type media_type: str

        :param media_class: For now only support Sinks* or Sources*
        :type media_class: str

        :param device: device type, such as hdmi, usb and bluez etc.
        :type device: str
        """
        mclass = self.generate_pw_media_class(media_type, media_class)
        if mclass in ["UNKNOWN CLASS", "UNKNOWN TYPE"]:
            return PipewireTestError.NO_AVAILABLE_PORT
        clients = self._get_pw_dump("Node")

        available_nodes = {}
        for client in clients:
            props = client["info"]["props"]
            name = props.get("node.name")
            if mclass == props.get("media.class") and device in name:
                available_nodes[client["id"]] = client

        if len(available_nodes) < 1:
            self.logger.error("No available {} found".format(mclass))
            return PipewireTestError.NO_AVAILABLE_PORT
        self.logger.info("Available {}:".format(mclass))
        for i in available_nodes:
            n = available_nodes[i]
            desc = n["info"]["props"].get("node.description")
            self.logger.info("Id:[{}], device:[{}]".format(n["id"], desc))

        chosen = False
        node_id = None
        while not chosen:
            self.logger.info(
                "Which {} would you like to test? -1 means don't change".format(
                    mclass
                )
            )
            self.logger.info("    {} id:".format(mclass))
            node_id = input()
            try:
                chosen = int(node_id) in available_nodes
            except ValueError:
                chosen = False
            if chosen:
                cmd = "wpctl set-default {}".format(node_id)
                subprocess.check_output(
                    cmd, shell=True, universal_newlines=True
                )
            elif node_id == "-1":
                chosen = True
            else:
                self.logger.info("    [{}] isn't existed!".format(node_id))
        return PipewireTestError.NO_ERROR

    def _check_state(self, device) -> bool:
        """
        Checks whether the sink is available for the given device.
        This function parse output of pw-dump to find the device type
        equals PipeWire:Interface:Device and media.class equals Audio/Device.
        For pipewire, the active port will be listed under info.params.Route.
        Therefore, you could check this object to know the state of it.

        :param device: device you would like to check
        :type device: str
        """
        clients = self._get_pw_dump("Device")
        try:
            for client in clients:
                mclass = client["info"]["props"].get("media.class")
                if mclass == "Audio/Device":
                    for route in client["info"]["params"]["Route"]:
                        name = route["name"]
                        available = route["available"]
                        if (
                            device.lower() in name.lower()
                            and "output" in route["direction"].lower()
                            and available in ["unknown", "yes"]
                        ):
                            self.logger.info("[ Audio sink ]".center(80, "="))
                            self.logger.info(
                                "Device: [{}] available: [{}]".format(
                                    route["description"], available
                                )
                            )
                            return True
            raise ValueError(
                "No available output device for {}".format(device)
            )
        except (IndexError, ValueError) as e:
            logging.error(repr(e))
            return False

    def gst_pipeline(self, pipe, timeout, device) -> int:
        """
        Simple GStreamer pipeline player

        :param pipe: Quoted GStreamer pipeline to launch
        :type pipe: str

        :param timeout: Timeout for running the pipeline
        :type timeout: int

        :param device: device type, such as hdmi etc.
        :type device: str
        """
        if device:
            if not self._check_state(device):
                return PipewireTestError.NO_SPECIFIC_DEVICE

        Gst.init(None)
        try:
            self.logger.info(
                "Attempting to initialize Gstreamer pipeline: {}".format(pipe)
            )
            element = Gst.parse_launch(pipe)
        except GLib.GError as error:
            self.logger.info("Specified pipeline couldn't be processed.")
            self.logger.info(
                "Error when processing pipeline: {}".format(error)
            )
            # Exit harmlessly
            return PipewireTestError.PIPELINE_PROCESS_FAIL
        self.logger.info("Pipeline initialized, now starting playback.")
        element.set_state(Gst.State.PLAYING)

        if timeout:
            time.sleep(timeout)

        element.set_state(Gst.State.NULL)

        return PipewireTestError.NO_ERROR

    def _get_audio_config(self, mode):
        """
        Get simple audio configuration
        This function parse output of pw-dump to find the device type
        equals PipeWire:Interface:Device and media.class equals Audio/Device.
        For pipewire, the active port will be listed under info.params.Route.
        Therefore, you could check this object to know the state of it.

        :param mode: sink or source
        :type mode: str
        """
        clients = self._get_pw_dump("Device")
        cfg = set()  # type: set[tuple[str, str, str]]
        for client in clients:
            active_ports = None
            mclass = client["info"]["props"].get("media.class")
            if mclass == "Audio/Device":
                active_ports = client["info"]["params"]["Route"]
            if active_ports:
                for p in active_ports:
                    if p["direction"] == self._get_pw_type(mode):
                        cfg.add(
                            (
                                "{} #{}".format(mode, client["id"]),
                                p["name"],
                                p["available"],
                            )
                        )
        return cfg

    def monitor_active_port_change(self, timeout, mode) -> int:
        """
        Monitoring Audio active port changing
        This script checks if the active port on either sinks
        (speakers or headphones) or sources (microphones, webcams)
        is changed after an appropriate device is plugged into the DUT.
        The script is fully automatic and either times out after or
        returns as soon as the change is detected.

        :param timeout: Timeout after which the script fails
        :type timeout: int

        :param mode: Monitor either sinks or sources
        :type mode: str
        """
        initial_cfg = self._get_audio_config(mode)
        self.logger.info("Starting with config: {}".format(initial_cfg))
        self.logger.info(
            "You have {} seconds to plug the item in".format(timeout)
        )

        for _ in range(int(timeout)):
            new_cfg = self._get_audio_config(mode)
            if new_cfg != initial_cfg:
                self.logger.info("Now using config: {}".format(new_cfg))
                self.logger.info("It seems to work!")
                return PipewireTestError.NO_ERROR
            time.sleep(1)
        self.logger.info("Couldn't detect active port change!")
        return PipewireTestError.NO_CHANGE_DETECTED

    def go_through_ports(self, cmd: str, mode: 't.Literal["source", "sink"]'):
        """
        Go through available ports for testing
        This script checks if the ports on either sinks
        (speakers or headphones) or sources (microphones, webcams)
        is available and working on the DUT.

        :param cmd: command for testing
        :type cmd: str

        :param mode: Monitor either sinks or sources
        :type mode: str
        """
        clients = self._get_pw_dump("Device")
        for client in clients:
            ports = []
            mclass = client["info"]["props"].get("media.class")
            if mclass == "Audio/Device":
                ports = client["info"]["params"]["EnumRoute"]
                assert type(ports) is list

            for p in ports:
                chosen = None
                if p["direction"] == self._get_pw_type(mode) and p[
                    "available"
                ] in [
                    "yes",
                    "unknown",
                ]:
                    while chosen != "yes":
                        self.logger.info(
                            "Please select [{}] for "
                            "testing (if selected, "
                            "please enter 'yes')".format(p["description"])
                        )

                        chosen = input()
                    checked = None
                    while checked != "yes":
                        # check_call will print to stdout for us
                        subprocess.check_call(cmd, shell=True)
                        self.logger.info(
                            "Is working ?  please enter 'yes' to leave"
                        )
                        checked = input()

    def iter_audio_sinks(self, cmd: "list[str]"):
        """Execute the cmd for each audio sink discovered by pipewire

        :param cmd: the command to run
        """

        tested_ids = set()  # type: set[int]
        nothing_failed = True
        audio_sink_ids = list(self._find_available_audio_sinks().items())
        N = len(audio_sink_ids)

        if N == 0:
            raise SystemExit("No audio sinks are available for this test")

        while True:
            try:
                for i, (node_id, node_description) in enumerate(
                    audio_sink_ids
                ):
                    print(
                        "({}) - '{}' {}".format(
                            i,
                            node_description,
                            ("- Tested" if node_id in tested_ids else ""),
                        )
                    )
                _input = input(
                    "Choose an audio sink to test [0-{}]".format(N - 1)
                    + ", or type 'q' to quit: "
                )
                if _input == "q":
                    if len(tested_ids) == N:
                        if nothing_failed:
                            print(
                                "[ OK ] Quitting with return code 0.",
                                "All {} audio sinks have been tested".format(
                                    N
                                ),
                            )
                            return
                        else:
                            raise SystemExit(
                                "[ ERR ] Some of the speakers failed the test"
                            )
                    else:
                        raise SystemExit(
                            "[ ERR ] Only {} audio sinks were tested, ".format(
                                len(tested_ids)
                            )
                            + "but expected {}".format(N)
                        )

                idx = int(_input)
                subprocess.check_call(
                    ["wpctl", "set-default", str(audio_sink_ids[idx][0])]
                )
            except (ValueError, IndexError):
                # this would loop at input() until a valid index is selected
                print(
                    "Please select an index from 0 to", N - 1, file=sys.stderr
                )
                continue

            node_id, node_description = audio_sink_ids[idx]

            TIMEOUT = 60
            try:
                print("=" * 80, flush=True)
                print(
                    "Testing '{}', id={}, command={}, {}s timeout".format(
                        node_description, node_id, cmd, TIMEOUT
                    )
                )
                # don't let this fail, just go to the next sink
                subprocess.run(cmd, timeout=TIMEOUT, check=True)
            except subprocess.TimeoutExpired:
                print(
                    "[ ERR ]",
                    cmd,
                    "did not finish in {}s".format(TIMEOUT),
                    file=sys.stderr,
                )
                nothing_failed = False
            except subprocess.CalledProcessError as e:
                print("[ ERR ]",e, file=sys.stderr)
                nothing_failed = False
            finally:
                tested_ids.add(audio_sink_ids[idx][0])
                print("=" * 80, flush=True)
                print(
                    "Progress: {}/{} audio sinks tested".format(
                        len(tested_ids), N
                    )
                )

    def _find_available_audio_sinks(self) -> "dict[int, str]":
        """
        Finds the list of audio "devices" as shown in gnome's control center

        :return: Returns a set of IDs that can be consumed by wpctl.
                 The values are human readable names.
                 These IDs are the "ID" to use as shown in `wpctl --help`
        """
        testable_node_ids = {}  # type: dict[int, str]
        pw_audio_devices = [
            device
            for device in self._get_pw_dump("Device")
            if device["info"]["props"].get("media.class") == "Audio/Device"
        ]
        pw_sink_nodes = [
            node
            for node in self._get_pw_dump("Node")
            if node["info"]["props"].get("media.class") == "Audio/Sink"
        ]

        for node in pw_sink_nodes:
            # IDs of these "nodes" can be passed to wpctl set-default
            node_id = int(node["id"])
            device_id = int(node["info"]["props"]["device.id"])

            device = None  # type: dict[str, t.Any] | None
            for dev in pw_audio_devices:
                if dev["id"] == device_id:
                    device = dev
                    break

            if not device:
                print("Could not find device", device_id, file=sys.stderr)
                continue

            # now check if the device has at least 1 available route
            enum_routes = device["info"]["params"]["EnumRoute"]

            if not isinstance(enum_routes, list):
                raise TypeError(
                    "EnumRoute of device {} is not a list, got {}".format(
                        device_id, type(enum_routes)
                    )
                )

            for route in enum_routes:
                # try to match the device to this node
                if (
                    route["devices"][0]  # this is an array with just 1 value
                    != node["info"]["props"]["card.profile.device"]
                ):
                    continue
                if route["direction"] != "Output":
                    print(
                        "Skipping '{}'".format(route["description"]),
                        "because it's not a sink",
                    )
                    continue
                if route["available"] not in ("yes", "unknown"):
                    print(
                        "Skipping '{}'".format(route["description"]),
                        "because it's unavailable",
                    )
                    continue

                # correct direction + at least 1 available route => testable
                testable_node_ids[node_id] = "{} - {}".format(
                    route["description"],
                    device["info"]["props"].get("device.product.name", ""),
                )
        return testable_node_ids

    def _get_node_description(self, properties) -> "str | None":
        """
        Get node description from the output of wpctl inspect

        :param properties: output of wpctl inspect
        :type properties: str

        :returns: the node description
        :rtype: str
        """
        try:
            for line in properties.splitlines():
                if "node.description" in line:
                    return line.split("=")[1]
        except IndexError as e:
            raise RuntimeError("properties format error {}".format(repr(e)))

    def show_default_device(self, device_type):
        """
        show the default device

        :param device_type: audio or video
        :type device_type: str
        """
        device_type = device_type.upper()
        if device_type not in ["AUDIO", "VIDEO"]:
            raise ValueError("Only support 'video' and 'audio'")
        sink_cmd = [
            "wpctl",
            "inspect",
            "@DEFAULT_{}_SINK@".format(device_type),
        ]
        source_cmd = [
            "wpctl",
            "inspect",
            "@DEFAULT_{}_SOURCE@".format(device_type),
        ]
        self.logger.info("Default input device:")
        try:
            source = subprocess.check_output(
                source_cmd, universal_newlines=True
            )
            self.logger.info(self._get_node_description(source))
            if device_type == "AUDIO":
                self.logger.info("Default output device:")
                sink = subprocess.check_output(
                    sink_cmd, universal_newlines=True
                )
                self.logger.info(self._get_node_description(sink))
            self.logger.info(
                "If these are not you would like to test,"
                " please change them before testing"
            )
        except subprocess.CalledProcessError as e:
            raise RuntimeError("Show default device error {}".format(repr(e)))

    def _sort_wpctl_status(self, lines: "list[str]") -> "list[str]":
        """
        This method will sort wpctl status for sub-items under catalog only

        :param lines: the wpctl status you would like to sort

        :returns: sorted wpctl status
        """
        catalog = [
            " └─ Clients:",
            " ├─ Devices:",
            " ├─ Sinks:",
            " ├─ Sink endpoints:",
            " ├─ Sources:",
            " ├─ Source endpoints:",
            " └─ Streams:",
            " └─ Default Configured Node Names:",
        ]
        sorted_lines = []
        sub_items = []
        for line in lines:
            clean_line = re.sub(", pid:.*| [0-9]+\\. ", "", line)
            # only sort needed items
            if clean_line in catalog:
                # found next catalog, append sorted sub_items
                [sorted_lines.append(item) for item in sorted(sub_items)]
                # clean up after append
                sub_items = []
                sorted_lines.append(clean_line)
            else:
                sub_items.append(clean_line)
        [sorted_lines.append(item) for item in sorted(sub_items)]
        return sorted_lines

    def compare_wpctl_status(self, status_1: str, status_2: str):
        """
        This method will sort wpctl status for sub-items under catalog only

        :param status_1: path to first wpctl status

        :param status_2: path to second wpctl status
        """
        with open(status_1, "r") as s1, open(status_2, "r") as s2:
            status_1_lines = s1.readlines()
            status_2_lines = s2.readlines()
            sorted_status_1 = self._sort_wpctl_status(status_1_lines)
            sorted_status_2 = self._sort_wpctl_status(status_2_lines)
            delta = difflib.unified_diff(sorted_status_1, sorted_status_2, n=0)
            diff = "".join(delta)
            if diff:
                self.logger.info("The first status:\n")
                self.logger.info("".join(status_1_lines))
                self.logger.info("And the second status:\n")
                self.logger.info("".join(status_2_lines))
                self.logger.info(
                    "Differ in the following lines (after sorting):"
                )
                self.logger.info(diff)
                raise SystemExit("The two status don't match !!!")

    def default_device_is_real(
        self,
        device: 't.Literal["audio-source", "audio-sink", "video-source"]',
    ) -> bool:
        """
        Checks whether the default device is a real device in contrast to a
        virtual or dummy device

        E.g. "Dummy Output"

        :param device: audio src/snk or video src
        :return: True if the default device is real
        """
        device_type, direction = device.split("-")
        wpctl_status_out = subprocess.check_output(
            [
                "wpctl",
                "inspect",
                "@DEFAULT_{}_{}@".format(
                    device_type.upper(), direction.upper()
                ),
            ],
            universal_newlines=True,
        )
        # the first line should look like this:
        # id 103, type PipeWire:Interface:Node
        # split at comma, take [0] -> 'id 103' -> split, take [-1] -> '103'
        # also use int() to check if we actually got a number
        default_device_id = int(
            wpctl_status_out.split(",", maxsplit=1)[0].strip().split()[-1]
        )
        pw_dump_out = subprocess.check_output(
            ["pw-dump", str(default_device_id)], universal_newlines=True
        )

        if not pw_dump_out:
            raise SystemExit(
                "'pw-dump {}' returned nothing, but {} was listed as the default {} {}".format(
                    default_device_id,
                    default_device_id,
                    device_type,
                    direction,
                )
            )

        pw_dump_json = json.loads(pw_dump_out)
        if type(pw_dump_json) is not list or len(pw_dump_json) < 1:
            raise SystemExit(
                "'pw-dump {}' did not return a valid list, got {}".format(
                    default_device_id, pw_dump_out
                )
            )

        # sometimes pw-dump returns extra elements in pw_dump_json
        # even if we specify the exact ID
        real = None  # type: dict[str, t.Any] | None
        for elem in pw_dump_json:
            if type(elem) is dict and elem.get("id") == default_device_id:
                real = elem
                break

        if real is None:
            raise SystemExit(
                "Pipewire did not return a JSON with id={}, got {}".format(
                    default_device_id, pw_dump_out
                )
            )

        node_props = real["info"]["props"]  # type: dict[str, t.Any]
        node_description = str(node_props["node.description"])

        if node_props.get("node.virtual") is True:
            # note that v4l2loopback devices do not appear as virtual
            # since the v4l2 device is what's actually virtual
            # not the pipewire node

            # this also catches the "Dummy Output" device that will appear
            # as both input and output when the OS doesn't recognize the
            # sound system at all
            print(
                "Default {} {} '{}' (id={}) is a virtual device".format(
                    device_type,
                    direction,
                    node_description,
                    default_device_id,
                ),
                'because it\'s marked as "node.virtual"',
                file=sys.stderr,
            )
            return False  # explicit virtual device

        print(
            "OK! Default {} {} '{}' (id={}) is a real device".format(
                device_type,
                direction,
                node_description,
                default_device_id,
            )
        )
        return True

    def _args_parsing(self, args=sys.argv[1:]):
        parser = argparse.ArgumentParser(
            prog="Pipewire validator",
            description="using for pipewire to valid system functions",
        )

        subparsers = parser.add_subparsers(dest="test_type")
        subparsers.required = True

        # Add parser for detecting audio/video function
        parser_detect = subparsers.add_parser(
            "detect", help="Detect audio/video devices on this system"
        )
        parser_detect.add_argument(
            "-t",
            "--type",
            type=str,
            default="Audio",
            help="device type such as Audio or Video (default: %(default)s)",
        )
        parser_detect.add_argument(
            "-c",
            "--clazz",
            type=str,
            default="Sink",
            help="device type such as Sink or Source (default: %(default)s)",
        )

        # Add parser for selecting audio/video function
        parser_select = subparsers.add_parser(
            "select", help="Select audio/video devices on this system"
        )
        parser_select.add_argument(
            "-t",
            "--type",
            type=str,
            default="Audio",
            help="device type such as Audio or Video (default: %(default)s)",
        )
        parser_select.add_argument(
            "-c",
            "--clazz",
            type=str,
            default="Sink",
            help="device type such as Sink or Source (default: %(default)s)",
        )
        parser_select.add_argument(
            "-d",
            "--device",
            type=str,
            default="",
            help="device type such as hdmi or bluez (default: %(default)s)",
        )

        # Add parser for gst pipeline function(Audio only)
        parser_gst = subparsers.add_parser(
            "gst", help="Simple GStreamer pipeline player"
        )
        parser_gst.add_argument(
            "PIPELINE", help="Quoted GStreamer pipeline to launch"
        )
        parser_gst.add_argument(
            "-t",
            "--timeout",
            type=int,
            required=True,
            help="Timeout for running the pipeline",
        )
        parser_gst.add_argument(
            "-d", "--device", type=str, help="Device to check for status"
        )

        # Add parser for monitor function(Audio only)
        parser_monitor = subparsers.add_parser(
            "monitor", help="Monitoring Audio active port changing"
        )
        parser_monitor.add_argument(
            "-t",
            "--timeout",
            type=int,
            required=True,
            help="Timeout after which the script fails",
        )
        parser_monitor.add_argument(
            "-m", "--mode", type=str, help="Monitor either sinks or sources"
        )

        # Add parser for go through function
        parser_through = subparsers.add_parser(
            "through", help="Go through available ports for testing"
        )
        parser_through.add_argument(
            "-c",
            "--command",
            type=str,
            required=True,
            help="command for testing",
        )
        parser_through.add_argument(
            "-m", "--mode", type=str, help="Either sinks or sources"
        )

        parser_iter_sink = subparsers.add_parser(
            "iter-audio-sinks", help="Iterate all available audio sinks"
        )
        parser_iter_sink.add_argument(
            "-c",
            "--command",
            type=str,
            required=True,
            help="command for testing",
        )

        # Add parser for show default device function
        parser_show = subparsers.add_parser(
            "show", help="show the default device"
        )
        parser_show.add_argument(
            "-t", "--type", type=str, required=True, help="VIDEO or AUDIO"
        )

        # Add parser for compare wpctl status function
        parser_compare = subparsers.add_parser(
            "compare_wpctl_status", help="compare wpctl status"
        )
        parser_compare.add_argument(
            "-s1",
            "--status_1",
            type=str,
            required=True,
            help="path to first output of wpctl status",
        )
        parser_compare.add_argument(
            "-s2",
            "--status_2",
            type=str,
            required=True,
            help="path to second output of wpctl status",
        )

        parser_is_real = subparsers.add_parser(
            "default_device_is_real",
            help="Check if the *default* audio source/sink or video source "
            + "is a real, non-virtual/dummy node",
        )
        parser_is_real.add_argument(
            "-d",
            "--device",
            type=str,
            required=True,
            choices=["audio-source", "audio-sink", "video-source"],
            help="Device type, audio source/sink or video source.",
        )

        return parser.parse_args(args)

    def function_select(self, args):
        if args.test_type == "detect":
            # detect_device("audio", "sink")
            return self.detect_device(args.type, args.clazz)
        elif args.test_type == "select":
            # select_device("audio", "sink", "hdmi")
            return self.select_device(args.type, args.clazz, args.device)
        elif args.test_type == "gst":
            # gst_pipeline(PIPELINE, "30", "hdmi")
            return self.gst_pipeline(args.PIPELINE, args.timeout, args.device)
        elif args.test_type == "monitor":
            # monitor_active_port_change("30", "sink")
            return self.monitor_active_port_change(args.timeout, args.mode)
        elif args.test_type == "through":
            # go_through_ports("speaker-test -c 2 -l 1 -t wav", "sink")
            return self.go_through_ports(args.command, args.mode)
        elif args.test_type == "show":
            # show_default_device("AUDIO")
            return self.show_default_device(args.type)
        elif args.test_type == "compare_wpctl_status":
            # compare_wpctl_status(STATUS_1, STATUS_2)
            return self.compare_wpctl_status(args.status_1, args.status_2)
        elif args.test_type == "default_device_is_real":
            if self.default_device_is_real(args.device):
                return PipewireTestError.NO_ERROR
            else:
                return PipewireTestError.NOT_REAL_DEVICE
        elif args.test_type == "iter-audio-sinks":
            return self.iter_audio_sinks(shlex.split(args.command))


def main():
    pw = PipewireTest()

    # create logger formatter
    log_formatter = logging.Formatter(fmt="%(message)s")

    # set log level
    pw.logger.setLevel(logging.INFO)

    # create console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(log_formatter)

    # Add console handler to logger
    pw.logger.addHandler(console_handler)
    sys.exit(pw.function_select(pw._args_parsing()))


if __name__ == "__main__":
    main()
