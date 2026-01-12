# This file is part of Checkbox.
#
# Copyright 2025 Canonical Ltd.
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
"""
A set of libraries to work with PulseAudio and Pipewire
without having to understand much about them.

Usage:
    Use `iter_sinks()` or `iter_sources()` to iterate through available audio
    nodes. Call `set_sink()` or `set_source()` within the iteration to set a
    node as the system default and make it active.

    Example:
        audio = AudioServerUtils()
        for node in audio.iter_sinks():
            # Set this node as default to test it
            audio.set_sink(node)
            # Adjust volume
            audio.set_volume(node, 0.8)
            # Now play audio to test...

References:
    - https://gitlab.freedesktop.org/pipewire/pipewire/-/wikis/Migrate-PulseAudio
"""

import abc
import argparse
import json
import logging
import subprocess
import time
from enum import Enum
from typing import Dict, Generator, List, Optional

logger = logging.getLogger(__name__)


class Node(object):
    """Represents an audio node (sink or source)."""

    def __init__(
        self,
        device_id: str,
        profile_id: Optional[str],
        name: str,
        id: str,
        description: Optional[str],
    ) -> None:
        self.device_id = device_id
        self.profile_id = profile_id
        self.name = name  # this might change after switching profile
        self.id = id  # this might change after switching profile
        self.description = description


class AudioServer(Enum):
    PULSEAUDIO = 0
    PIPEWIRE = 1


class NodeType(Enum):
    SINK = 0
    SOURCE = 1


class AudioServerUtils:
    def __new__(cls, *args, **kwargs):
        if cls is AudioServerUtils:
            server = cls.get_server()
            logger.info(
                "Detected audio server is %s", server.name.capitalize()
            )
            if server == AudioServer.PIPEWIRE:
                cls = PipewireUtils
            elif server == AudioServer.PULSEAUDIO:
                cls = PulseaudioUtils
        else:
            logger.warning("Avoid creating an AudioServer sub-class directly.")
        return super().__new__(cls)

    @staticmethod
    def get_server() -> AudioServer:
        for server in AudioServer:
            try:
                name = server.name.lower()
                subprocess.check_output(
                    ["systemctl", "--user", "status", name]
                )
                return server
            except subprocess.CalledProcessError:
                continue
        raise OSError("Cannot find a running audio server")

    @abc.abstractmethod
    def list_sinks(self) -> List[Node]:
        """
        Get a lightweight list of available sinks without activating profiles.
        """

    @abc.abstractmethod
    def list_sources(self) -> List[Node]:
        """
        Get a lightweight list of available sources without activating profiles.
        """

    @abc.abstractmethod
    def iter_sinks(self) -> Generator[Node, None, None]:
        """
        Iterate over available sinks, automatically activating each profile.
        The yielded node is already active and ready to use.
        """

    @abc.abstractmethod
    def iter_sources(self) -> Generator[Node, None, None]:
        """
        Iterate over available sources, automatically activating each profile.
        The yielded node is already active and ready to use.
        """

    @abc.abstractmethod
    def set_sink(self, sink: Node) -> None:
        """
        Set the target sink as default output.
        Node should already be active (e.g., from iter_sinks()).
        """

    @abc.abstractmethod
    def set_source(self, source: Node) -> None:
        """
        Set the target source as default input.
        Node should already be active (e.g., from iter_sources()).
        """

    @abc.abstractmethod
    def set_volume(self, node: Node, volume: float) -> None:
        """
        Set the volume [0, 1] of the target node (sink or source).
        """


class PipewireUtils(AudioServerUtils):
    """
    PipeWire audio utility implementation.

    Device/Profile/Node hierarchy:

        Device: "alsa_card.pci-0000_00_1f.3"
        ├── Profile: "output:analog-stereo" (index: 0)
        │   ├── Node: "alsa_output.pci-0000_00_1f.3.analog-stereo" (Sink)
        │   └── Node: "alsa_output.pci-0000_00_1f.4.analog-stereo" (Sink)
        ├── Profile: "output:hdmi-stereo" (index: 1)
        │   └── Node: "alsa_output.pci-0000_00_1f.3.hdmi-stereo" (Sink)
        └── Profile: "input:analog-stereo" (index: 2)
            └── Node: "alsa_input.pci-0000_00_1f.3.analog-stereo" (Source)
    """

    def _load_pw_dump(self):
        exc = RuntimeError

        # Multiple attempts because it might be unstable after switching card
        for _ in range(3):
            try:
                try:
                    result = subprocess.check_output(
                        ["pw-dump"], universal_newlines=True
                    )
                    return json.loads(result)
                except subprocess.CalledProcessError as e:
                    raise RuntimeError("Failed to run pw-dump: {}".format(e))
                except json.JSONDecodeError as e:
                    raise RuntimeError(
                        "Failed to parse pw-dump output: {}".format(e)
                    )
            except RuntimeError as e:
                exc = e
                time.sleep(1)
        raise exc

    def _get_audio_devices(self):
        return {
            str(obj["id"]): obj
            for obj in self._load_pw_dump()
            if obj.get("type") == "PipeWire:Interface:Device"
            and obj["info"]["props"]["media.class"] == "Audio/Device"
        }

    def _get_audio_nodes(self, node_type: NodeType) -> Dict:
        return {
            str(obj["id"]): obj
            for obj in self._load_pw_dump()
            if obj.get("type") == "PipeWire:Interface:Node"
            and obj.get("info", {}).get("props", {}).get("media.class")
            == "Audio/{}".format(node_type.name.capitalize())
        }

    def _get_available_profiles(
        self, device: Dict, profile_type: NodeType
    ) -> Dict:
        def _check_class(profile, profile_type):
            profile_classes = profile.get("classes", [])
            if not profile_classes:
                return False

            classes = profile_classes[1:]
            for profile_class in classes:
                if (
                    "Audio/{}".format(profile_type.name.capitalize())
                    in profile_class
                ):
                    return True

            return False

        return {
            str(profile["index"]): profile
            for profile in device.get("info", {})
            .get("params", {})
            .get("EnumProfile", [])
            if profile.get("available") == "yes"
            and _check_class(profile, profile_type)
        }

    def _list_nodes_of_type(self, target: NodeType) -> List[Node]:
        """List all nodes by using the iterator and collecting them into a list."""
        return list(self._iter_nodes_of_type(target))

    def _iter_nodes_of_type(
        self, target: NodeType
    ) -> Generator[Node, None, None]:
        """Iterator that activates each profile and yields ready-to-use nodes."""
        devices = self._get_audio_devices()
        logger.debug("Found %s available audio device(s)", len(devices))

        for device_id, device in devices.items():
            device_name = device["info"]["props"]["device.name"]
            profiles = self._get_available_profiles(device, target)
            logger.debug(
                "Found %s available profile(s) for device %s",
                len(profiles),
                device_name,
            )

            for profile_id, profile in profiles.items():
                # Set the device profile to make pipewire create Nodes
                self._set_card_profile(device_id, profile_id)

                audio_nodes = self._get_audio_nodes(target)
                logger.debug(
                    "Found %s available node(s) for device %s@%s",
                    len(audio_nodes),
                    device_name,
                    profile["name"],
                )

                for node_id, node in audio_nodes.items():
                    name = (
                        node.get("info", {}).get("props", {}).get("node.name")
                    )
                    description = (
                        node.get("info", {})
                        .get("props", {})
                        .get("node.description")
                    )
                    node_obj = Node(
                        device_id, profile_id, name, node_id, description
                    )
                    yield node_obj

    def _set_card_profile(self, device_id: str, profile_id: str) -> None:
        try:
            cmd = [
                "pw-cli",
                "s",
                device_id,
                "Profile",
                "{{ index: {} }}".format(profile_id),
            ]
            logger.debug("[shell] %s", " ".join(cmd))
            subprocess.check_output(cmd)
        except subprocess.CalledProcessError:
            error = "Cannot set profile '{}' on device '{}'".format(
                profile_id, device_id
            )
            raise RuntimeError(error)

    def _set_default_audio_node(self, node_id: str) -> None:
        cmd = ["wpctl", "set-default", node_id]
        logger.debug("[shell] %s", " ".join(cmd))
        subprocess.check_output(cmd)

    def _set_node_of_type(self, node: Node, target: str) -> None:
        self._set_card_profile(node.device_id, node.profile_id)

        nodes = self._get_audio_nodes(target)

        def match(node_id: str, node_name: str, obj) -> bool:
            return (
                obj.get("info", {}).get("props", {}).get("node.id", "")
                == node_id
                and obj.get("info", {}).get("props", {}).get("node.name", "")
                == node_name
            )

        try:
            next(
                obj for obj in nodes.values() if match(node.id, node.name, obj)
            )
        except StopIteration:
            # handle cases where the node name include an index
            # i.e. alsa_output.pci-0000_00_1f.3.analog-stereo.10
            stripped_name = node.name.rsplit(".", 1)[0]
            try:
                new_node = next(
                    obj
                    for obj in nodes.values()
                    if obj.get("info", {})
                    .get("props", {})
                    .get("node.name", "")
                    .rsplit(".", 1)[0]
                    == stripped_name
                )
                node.id = str(new_node["info"]["props"]["node.id"])
                node.name = new_node["info"]["props"]["node.name"]
            except StopIteration:
                raise RuntimeError(
                    "Node '{}' (id: {}) not found after setting profile '{}' on device '{}'".format(
                        node.name, node.id, node.profile_id, node.device_id
                    )
                )

        self._set_default_audio_node(node.id)

    def list_sinks(self) -> List[Node]:
        return self._list_nodes_of_type(NodeType.SINK)

    def list_sources(self) -> List[Node]:
        return self._list_nodes_of_type(NodeType.SOURCE)

    def iter_sinks(self) -> Generator[Node, None, None]:
        return self._iter_nodes_of_type(NodeType.SINK)

    def iter_sources(self) -> Generator[Node, None, None]:
        return self._iter_nodes_of_type(NodeType.SOURCE)

    def set_sink(self, sink: Node) -> None:
        """
        Set sink as default output.

        Important: This method assumes the node's profile is already active
        (e.g., the node was obtained from iter_sinks()). If you need to set
        a sink obtained from list_sinks(), call iter_sinks() to activate it
        first, or activate the profile manually.

        Args:
            sink: The sink node to set as default

        Raises:
            RuntimeError: If the node cannot be set as default
        """
        logger.info("Setting sink %s", sink.name)
        try:
            self._set_default_audio_node(sink.id)
        except subprocess.CalledProcessError as e:
            raise RuntimeError(
                "Failed to set sink '{}' (id: {}). Node may not be active. "
                "Ensure the node was obtained from iter_sinks().".format(
                    sink.name, sink.id
                )
            ) from e

    def set_source(self, source: Node) -> None:
        """
        Set source as default input.

        Important: This method assumes the node's profile is already active
        (e.g., the node was obtained from iter_sources()). If you need to set
        a source obtained from list_sources(), call iter_sources() to activate
        it first, or activate the profile manually.

        Args:
            source: The source node to set as default

        Raises:
            RuntimeError: If the node cannot be set as default
        """
        logger.info("Setting source %s", source.name)
        try:
            self._set_default_audio_node(source.id)
        except subprocess.CalledProcessError as e:
            raise RuntimeError(
                "Failed to set source '{}' (id: {}). Node may not be active. "
                "Ensure the node was obtained from iter_sources().".format(
                    source.name, source.id
                )
            ) from e

    def set_volume(self, node: Node, volume: float) -> None:
        if not 0 <= volume <= 1.0:
            raise ValueError("Volume must be in range [0,1]")
        try:
            cmd = ["wpctl", "set-volume", str(node.id), str(volume)]
            logger.debug("[shell] %s", " ".join(cmd))
            subprocess.check_output(cmd)
        except subprocess.CalledProcessError as e:
            raise RuntimeError(
                "Cannot set volume of {} at {}".format(node.name, volume)
            ) from e


class PulseaudioUtils(AudioServerUtils):
    def _parse_pactl_list(self, target_type: str) -> List[Node]:
        """Parse pactl list output to extract sink/source information."""
        try:
            output = subprocess.check_output(
                ["pactl", "list", target_type], universal_newlines=True
            )
        except subprocess.CalledProcessError as e:
            raise RuntimeError(
                "Failed to run pactl list {}: {}".format(target_type, e)
            )

        nodes = []
        current_item = {}

        lines = output.strip().split("\n")
        for line in lines:
            line = line.strip()

            if line.startswith("{} #".format(target_type.capitalize()[:-1])):
                # New sink/source entry
                if current_item:
                    nodes.append(self._create_node_from_pactl(current_item))
                current_item = {}

            elif line.startswith("Name: "):
                current_item["name"] = line.split("Name: ", 1)[1]

            elif line.startswith("Description: "):
                current_item["description"] = line.split("Description: ", 1)[1]

            elif "Index: " in line:
                current_item["index"] = line.split("Index: ", 1)[1]

        # Add the last item
        if current_item:
            nodes.append(self._create_node_from_pactl(current_item))

        return nodes

    def _create_node_from_pactl(self, item_data):
        """Create a Node object from pactl parsed data."""
        return Node(
            device_id=item_data.get("index", ""),
            profile_id=None,
            name=item_data.get("name", ""),
            id=item_data.get("index", ""),
            description=item_data.get("description", ""),
        )

    def list_sinks(self) -> List[Node]:
        """Get list of available audio sinks."""
        return self._parse_pactl_list("sinks")

    def list_sources(self) -> List[Node]:
        """Get list of available audio sources."""
        return self._parse_pactl_list("sources")

    def iter_sinks(self) -> Generator[Node, None, None]:
        """Iterate over available sinks. For PulseAudio, just yields all nodes."""
        for node in self._parse_pactl_list("sinks"):
            yield node

    def iter_sources(self) -> Generator[Node, None, None]:
        """Iterate over available sources. For PulseAudio, just yields all nodes."""
        for node in self._parse_pactl_list("sources"):
            yield node

    def set_sink(self, sink: Node) -> None:
        """
        Set the specified sink as default output.

        For PulseAudio, nodes from list_sinks() or iter_sinks() are both
        ready to use without additional activation.

        Args:
            sink: The sink node to set as default

        Raises:
            RuntimeError: If the node cannot be set as default
        """
        logger.info("Setting PulseAudio sink %s", sink.name)
        try:
            cmd = ["pactl", "set-default-sink", sink.name]
            logger.debug("[shell] %s", " ".join(cmd))
            subprocess.check_output(cmd)
        except subprocess.CalledProcessError as e:
            raise RuntimeError(
                "Failed to set sink '{}' as default: {}".format(sink.name, e)
            ) from e

    def set_source(self, source: Node) -> None:
        """
        Set the specified source as default input.

        For PulseAudio, nodes from list_sources() or iter_sources() are both
        ready to use without additional activation.

        Args:
            source: The source node to set as default

        Raises:
            RuntimeError: If the node cannot be set as default
        """
        logger.info("Setting PulseAudio source %s", source.name)
        try:
            cmd = ["pactl", "set-default-source", source.name]
            logger.debug("[shell] %s", " ".join(cmd))
            subprocess.check_output(cmd)
        except subprocess.CalledProcessError as e:
            raise RuntimeError(
                "Failed to set source '{}' as default: {}".format(
                    source.name, e
                )
            ) from e

    def set_volume(self, node: Node, volume: float) -> None:
        """Set volume for the specified node (sink or source)."""
        if not 0 <= volume <= 1.0:
            raise ValueError("Volume must be in range [0,1]")

        # Convert to percentage
        volume_percent = int(volume * 100)

        # Try to set volume using the node name first, fallback to index
        for node_id in [node.name, node.id]:
            try:
                cmd = [
                    "pactl",
                    "set-sink-volume",
                    node_id,
                    "{}%".format(volume_percent),
                ]
                logger.debug("[shell] %s", " ".join(cmd))
                subprocess.check_output(cmd)
                return
            except subprocess.CalledProcessError:
                # Try with set-source-volume
                try:
                    cmd = [
                        "pactl",
                        "set-source-volume",
                        node_id,
                        "{}%".format(volume_percent),
                    ]
                    logger.debug("[shell] %s", " ".join(cmd))
                    subprocess.check_output(cmd)
                    return
                except subprocess.CalledProcessError:
                    continue

        raise RuntimeError(
            "Cannot set volume of {} to {}".format(node.name, volume)
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Manage audio sinks and sources"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # List subcommands
    list_parser = subparsers.add_parser(
        "list", help="List available sinks or sources"
    )
    list_parser.add_argument(
        "type",
        choices=["sinks", "sources"],
        help="Type to list (sinks or sources)",
    )

    # Interactive iteration subcommand
    iter_parser = subparsers.add_parser(
        "iter", help="Iterate over sinks/sources and select one interactively"
    )
    iter_parser.add_argument(
        "type",
        choices=["sinks", "sources"],
        help="Type to iterate (sinks or sources)",
    )

    args = parser.parse_args()
    audio = AudioServerUtils()

    if args.command == "list":
        if args.type == "sinks":
            nodes = audio.list_sinks()
        else:
            nodes = audio.list_sources()

        for i, node in enumerate(nodes):
            print("{}: {} - {}".format(i, node.name, node.description))

    elif args.command == "iter":
        node_type = "sink" if args.type == "sinks" else "source"
        iterator = (
            audio.iter_sinks()
            if args.type == "sinks"
            else audio.iter_sources()
        )

        for i, node in enumerate(iterator):
            # Immediately set as default
            if args.type == "sinks":
                audio.set_sink(node)
            else:
                audio.set_source(node)

            print("\n[{}] Now active: {}".format(i, node.name))
            print("    Description: {}".format(node.description))

            choice = (
                input("Keep this one? (y to keep, n for next, q to quit): ")
                .strip()
                .lower()
            )

            if choice == "y":
                print("Kept {}: {}".format(node_type, node.name))
                break
            elif choice == "q":
                print("Cancelled")
                break
            # 'n' or anything else continues to next node
