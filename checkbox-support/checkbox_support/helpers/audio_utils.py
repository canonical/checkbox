"""
A set of libraries to work with PulseAudio and Pipewire
without knowing much about them.

References:
    - https://gitlab.freedesktop.org/pipewire/pipewire/-/wikis/Migrate-PulseAudio
"""

import abc
import json
import logging
import subprocess
import time
from dataclasses import dataclass
from typing import List, Literal, Optional

logging.basicConfig(level=logging.DEBUG)


@dataclass()
class Node:
    device_id: str
    profile_id: Optional[str]
    name: str  # this might change after switching profile
    id: str  # this might change after switching profile
    description: Optional[str]


class AudioUtils:
    def __new__(cls, *args, **kwargs):
        server = cls.get_server()
        logging.getLogger().info("Detected audio server is %s", server)
        if server == "pipewire":
            return super().__new__(PipewireUtils)
        elif server == "pulseaudio":
            return super().__new__(PulseaudioUtils)
        else:
            raise RuntimeError("Unsupported audio server: {}".format(server))

    @staticmethod
    def get_server() -> str:
        for server in ["pipewire", "pulseaudio"]:
            try:
                subprocess.check_output(["systemctl", "--user", "status", server])
                return server
            except subprocess.CalledProcessError:
                continue
        raise OSError("Cannot find a running audio server")

    @abc.abstractmethod
    def get_sinks(self) -> List[Node]:
        """
        Get a list of available sinks.
        """

    @abc.abstractmethod
    def get_sources(self) -> List[Node]:
        """
        Get a list of available sources.
        """

    @abc.abstractmethod
    def set_sink(self, sink: Node):
        """
        Set the target sink as default output.
        """

    @abc.abstractmethod
    def set_source(self, source: Node):
        """
        Set the target source as default input.
        """

    @abc.abstractmethod
    def set_volume(self, node: Node, volume: float):
        """
        Set the volume [0, 1] of the target node (sink or source).
        """


class PipewireUtils(AudioUtils):
    def _load_pw_dump(self):
        exc = Exception
        for _ in range(3):
            try:
                try:
                    result = subprocess.check_output(["pw-dump"])
                    return json.loads(result)
                except subprocess.CalledProcessError as e:
                    raise RuntimeError(f"Failed to run pw-dump: {e}")
                except json.JSONDecodeError as e:
                    raise RuntimeError(f"Failed to parse pw-dump output: {e}")
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

    def _get_audio_nodes(self, node_type: Literal["Sink", "Source"]):
        return {
            str(obj["id"]): obj
            for obj in self._load_pw_dump()
            if obj.get("type") == "PipeWire:Interface:Node"
            and obj.get("info", {}).get("props", {}).get("media.class")
            == "Audio/{}".format(node_type)
        }

    def _get_available_profiles(self, device, profile_type: Literal["Sink", "Source"]):
        def _check_class(profile, profile_type):
            profile_classes = profile.get("classes", [])
            if not profile_classes:
                return False

            classes = profile_classes[1:]
            for profile_class in classes:
                if "Audio/{}".format(profile_type) in profile_class:
                    return True

            return False

        return {
            str(profile["index"]): profile
            for profile in device.get("info", {})
            .get("params", {})
            .get("EnumProfile", [])
            if profile.get("available") == "yes" and _check_class(profile, profile_type)
        }

    def _get_nodes_of_type(self, target: Literal["Sink", "Source"]) -> List[Node]:
        nodes = []

        devices = self._get_audio_devices()
        for device_id, device in devices.items():
            profiles = self._get_available_profiles(device, target)
            for profile_id, profile in profiles.items():
                # Set the device profile to make pipewire create Nodes
                self._set_card_profile(device_id, profile_id)

                audio_nodes = self._get_audio_nodes(target)
                for id, node in audio_nodes.items():
                    name = node.get("info", {}).get("props", {}).get("node.name")
                    description = (
                        node.get("info", {}).get("props", {}).get("node.description")
                    )
                    node = Node(device_id, profile_id, name, id, description)
                    nodes.append(node)

        return nodes

    def _set_card_profile(self, device_id: str, profile_id: str):
        try:
            cmd = ["pw-cli", "s", device_id, "Profile", f"{{ index: {profile_id} }}"]
            logging.getLogger().debug(" ".join(cmd))
            subprocess.check_output(cmd)
        except subprocess.CalledProcessError as e:
            error = "Cannot set profile '{}' on device '{}'".format(
                profile_id, device_id
            )
            raise RuntimeError(error) from e

    def _set_default_audio_node(self, name: str, node_type: Literal["Sink", "Source"]):
        cmd = [
            "pw-metadata",
            "0",
            "default.configured.audio.{}".format(node_type.lower()),
            "{{ name: {} }}".format(name),
        ]
        logging.getLogger().debug(" ".join(cmd))
        subprocess.check_output(cmd)

    def _set_node_of_type(self, node: Node, target: Literal["Sink", "Source"]):
        self._set_card_profile(node.device_id, node.profile_id)

        # Node name / ID might change after applying a profile
        nodes = self._get_audio_nodes(target)
        try:
            next(
                obj
                for obj in nodes.values()
                if obj.get("info", {}).get("props", {}).get("node.name", "")
                == node.name
            )
        except StopIteration:
            # handle cases where the node name include an index
            # i.e. alsa_output.pci-0000_00_1f.3.analog-stereo.10
            new_node = next(
                obj
                for obj in nodes.values()
                if obj.get("info", {})
                .get("props", {})
                .get("node.name", "")
                .rsplit(".", 1)[0]
                == node.name.rsplit(".", 1)[0]
            )
            node.id = str(new_node["id"])
            node.name = new_node.get("info", {}).get("props", {}).get("node.name")

        self._set_default_audio_node(node.name, target)

    def get_sinks(self) -> List[Node]:
        return self._get_nodes_of_type("Sink")

    def get_sources(self) -> List[Node]:
        return self._get_nodes_of_type("Source")

    def set_sink(self, sink: Node):
        logging.getLogger().info("Setting sink %s", sink)
        self._set_node_of_type(sink, "Sink")

    def set_source(self, source: Node):
        self._set_node_of_type(source, "Source")

    def set_volume(self, node: Node, volume: float):
        try:
            cmd = ["wpctl", "set-volume", str(node.id), "1.0"]
            logging.getLogger().debug(" ".join(cmd))
            subprocess.check_output(cmd)
        except subprocess.CalledProcessError as e:
            raise RuntimeError(
                "Cannot set volume of {} at {}".format(node.name, volume)
            ) from e


class PulseaudioUtils(AudioUtils):
    def _parse_pactl_list(self, target_type: Literal["sinks", "sources"]):
        """Parse pactl list output to extract sink/source information."""
        try:
            output = subprocess.check_output(["pactl", "list", target_type], text=True)
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Failed to run pactl list {target_type}: {e}")

        nodes = []
        current_item = {}

        lines = output.strip().split("\n")
        for line in lines:
            line = line.strip()

            if line.startswith(f"{target_type.capitalize()[:-1]} #"):
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

    def get_sinks(self) -> List[Node]:
        """Get list of available audio sinks."""
        return self._parse_pactl_list("sinks")

    def get_sources(self) -> List[Node]:
        """Get list of available audio sources."""
        return self._parse_pactl_list("sources")

    def set_sink(self, sink: Node):
        """Set the specified sink as default output."""
        try:
            cmd = ["pactl", "set-default-sink", sink.name]
            logging.getLogger().debug(" ".join(cmd))
            subprocess.check_output(cmd)
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Failed to set sink {sink.name} as default: {e}")

    def set_source(self, source: Node):
        """Set the specified source as default input."""
        logging.getLogger().info("Setting PulseAudio source %s", source)
        try:
            cmd = ["pactl", "set-default-source", source.name]
            logging.getLogger().debug(" ".join(cmd))
            subprocess.check_output(cmd)
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Failed to set source {source.name} as default: {e}")

    def set_volume(self, node: Node, volume: float):
        """Set volume for the specified node (sink or source)."""
        if not 0.0 <= volume <= 1.0:
            raise ValueError("Volume must be between 0.0 and 1.0")

        # Convert to percentage
        volume_percent = int(volume * 100)

        # Try to set volume using the node name first, fallback to index
        for node_id in [node.name, node.id]:
            try:
                cmd = ["pactl", "set-sink-volume", node_id, f"{volume_percent}%"]
                logging.getLogger().debug(" ".join(cmd))
                subprocess.check_output(cmd)
                return
            except subprocess.CalledProcessError:
                # Try with set-source-volume
                try:
                    cmd = ["pactl", "set-source-volume", node_id, f"{volume_percent}%"]
                    logging.getLogger().debug(" ".join(cmd))
                    subprocess.check_output(cmd)
                    return
                except subprocess.CalledProcessError:
                    continue

        raise RuntimeError(f"Cannot set volume of {node.name} to {volume}")


if __name__ == "__main__":
    audio = AudioUtils()

    target = ""
    while target not in ["sink", "source"]:
        target = input("What do you want to set, sink or source? ")

    if target == "sink":
        sinks = audio.get_sinks()
        for i, sink in enumerate(sinks):
            print(i, sink.description, sink.name)

        target = int(input("Which sink do you want to set? "))
        audio.set_sink(sinks[target])
    else:
        sources = audio.get_sources()
        for i, source in enumerate(sources):
            print(i, source.description, source.name)

        target = int(input("Which source do you want to set? "))
        audio.set_source(sources[target])
