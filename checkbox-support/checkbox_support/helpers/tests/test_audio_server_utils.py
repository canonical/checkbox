import json
import subprocess
import textwrap
import unittest
from unittest.mock import Mock, patch

from checkbox_support.helpers.audio_server_utils import (
    AudioServer,
    AudioServerUtils,
    Node,
    NodeType,
    PipewireUtils,
    PulseaudioUtils,
)


class NodeTests(unittest.TestCase):
    """Test cases for the Node class."""

    def test_node_creation(self):
        """Test basic Node instantiation."""
        node = Node(
            device_id="dev1",
            profile_id="prof1",
            name="test_node",
            id="123",
            description="Test Node",
        )
        self.assertEqual(node.device_id, "dev1")
        self.assertEqual(node.profile_id, "prof1")
        self.assertEqual(node.name, "test_node")
        self.assertEqual(node.id, "123")
        self.assertEqual(node.description, "Test Node")


class AudioServerUtilsTests(unittest.TestCase):
    """Test cases for the AudioServerUtils factory class."""

    @patch(
        "checkbox_support.helpers.audio_server_utils.subprocess.check_output"
    )
    def test_get_server_pipewire(self, mock_check_output):
        """Test detection of PipeWire audio server."""

        def systemctl(*args, **kwargs) -> bool:
            if "pipewire" not in args[0]:
                raise subprocess.CalledProcessError(1, "")

        mock_check_output.side_effect = systemctl
        server = AudioServerUtils.get_server()
        self.assertEqual(server, AudioServer.PIPEWIRE)

    @patch(
        "checkbox_support.helpers.audio_server_utils.subprocess.check_output"
    )
    def test_get_server_pulseaudio(self, mock_check_output):
        """Test detection of PulseAudio audio server."""

        def systemctl(*args, **kwargs) -> bool:
            if "pulseaudio" not in args[0]:
                raise subprocess.CalledProcessError(1, "")

        mock_check_output.side_effect = systemctl
        server = AudioServerUtils.get_server()
        self.assertEqual(server, AudioServer.PULSEAUDIO)

    @patch(
        "checkbox_support.helpers.audio_server_utils.subprocess.check_output"
    )
    def test_get_server_none(self, mock_check_output):
        """Test OSError when no audio server is running."""
        mock_check_output.side_effect = subprocess.CalledProcessError(1, "")
        with self.assertRaises(OSError):
            AudioServerUtils.get_server()

    @patch(
        "checkbox_support.helpers.audio_server_utils.AudioServerUtils.get_server"
    )
    def test_factory_returns_pipewire_utils(self, mock_get_server):
        """Test factory returns PipewireUtils instance."""
        mock_get_server.return_value = AudioServer.PIPEWIRE
        audio = AudioServerUtils()
        self.assertIsInstance(audio, PipewireUtils)

    @patch(
        "checkbox_support.helpers.audio_server_utils.AudioServerUtils.get_server"
    )
    def test_factory_returns_pulseaudio_server_utils(self, mock_get_server):
        """Test factory returns PulseaudioUtils instance."""
        mock_get_server.return_value = AudioServer.PULSEAUDIO
        audio = AudioServerUtils()
        self.assertIsInstance(audio, PulseaudioUtils)


class PipewireUtilsTests(unittest.TestCase):
    """Test cases for the PipewireUtils class."""

    def setUp(self):
        """Set up test fixtures."""
        self.pipewire = PipewireUtils()

    @patch(
        "checkbox_support.helpers.audio_server_utils.subprocess.check_output"
    )
    def test_load_pw_dump_success(self, mock_check_output):
        """Test successful pw-dump load."""
        mock_check_output.return_value = '[{"id": 1, "type": "test"}]'
        result = self.pipewire._load_pw_dump()
        self.assertEqual(result, [{"id": 1, "type": "test"}])

    @patch("time.sleep", Mock())
    @patch(
        "checkbox_support.helpers.audio_server_utils.subprocess.check_output"
    )
    def test_load_pw_dump_retry(self, mock_check_output):
        """Test pw-dump retry on failure."""
        mock_check_output.side_effect = [
            subprocess.CalledProcessError(1, ""),
            json.JSONDecodeError("", "", 0),
            '[{"id": 2, "type": "test3"}]',
        ]
        result = self.pipewire._load_pw_dump()
        self.assertEqual(result, [{"id": 2, "type": "test3"}])

    @patch("time.sleep", Mock())
    @patch(
        "checkbox_support.helpers.audio_server_utils.subprocess.check_output"
    )
    def test_load_pw_dump_raises(self, mock_check_output):
        """Test pw-dump raises on multiple failures."""
        mock_check_output.side_effect = subprocess.CalledProcessError(1, "")
        with self.assertRaises(RuntimeError):
            self.pipewire._load_pw_dump()

    def test_get_audio_devices(self):
        """Test getting audio devices from pw-dump."""
        device = {
            "id": 1,
            "type": "PipeWire:Interface:Device",
            "info": {"props": {"media.class": "Audio/Device"}},
        }
        dump = [
            device,
            {
                "id": 2,
                "type": "PipeWire:Interface:Device",
                "info": {"props": {"media.class": "Video/Device"}},
            },
            {"id": 3},
        ]
        self.pipewire._load_pw_dump = Mock(return_value=dump)
        devices = self.pipewire._get_audio_devices()
        self.assertEqual({"1": device}, devices)

    def test_get_audio_nodes(self):
        """Test getting audio nodes by type."""
        sink = {
            "id": 1,
            "type": "PipeWire:Interface:Node",
            "info": {"props": {"media.class": "Audio/Sink"}},
        }
        source = {
            "id": 2,
            "type": "PipeWire:Interface:Node",
            "info": {"props": {"media.class": "Audio/Source"}},
        }
        dump = [
            sink,
            source,
            {"id": 3},
        ]
        self.pipewire._load_pw_dump = Mock(return_value=dump)

        # Sinks
        sinks = self.pipewire._get_audio_nodes(NodeType.SINK)
        self.assertEqual({"1": sink}, sinks)

        # Sources
        sources = self.pipewire._get_audio_nodes(NodeType.SOURCE)
        self.assertEqual({"2": source}, sources)

    def test_list_sinks(self):
        """Test listing all available sinks."""
        node1 = Node("dev1", "prof1", "sink1", "1", "Sink 1")
        node2 = Node("dev1", "prof2", "sink2", "2", "Sink 2")
        self.pipewire._iter_nodes_of_type = Mock(
            return_value=iter([node1, node2])
        )

        sinks = self.pipewire.list_sinks()

        self.assertEqual(len(sinks), 2)
        self.assertEqual(sinks[0], node1)
        self.assertEqual(sinks[1], node2)
        self.pipewire._iter_nodes_of_type.assert_called_once_with(
            NodeType.SINK
        )

    def test_list_sources(self):
        """Test listing all available sources."""
        node1 = Node("dev1", "prof1", "source1", "1", "Source 1")
        self.pipewire._iter_nodes_of_type = Mock(return_value=iter([node1]))

        sources = self.pipewire.list_sources()

        self.assertEqual(len(sources), 1)
        self.assertEqual(sources[0], node1)
        self.pipewire._iter_nodes_of_type.assert_called_once_with(
            NodeType.SOURCE
        )

    def test_iter_sinks(self):
        """Test iterating over sinks."""
        node1 = Node("dev1", "prof1", "sink1", "1", "Sink 1")
        node2 = Node("dev1", "prof2", "sink2", "2", "Sink 2")
        self.pipewire._iter_nodes_of_type = Mock(
            return_value=iter([node1, node2])
        )

        result = list(self.pipewire.iter_sinks())

        self.assertEqual(len(result), 2)
        self.assertEqual(result[0], node1)
        self.assertEqual(result[1], node2)

    def test_iter_sources(self):
        """Test iterating over sources."""
        node1 = Node("dev1", "prof1", "source1", "1", "Source 1")
        self.pipewire._iter_nodes_of_type = Mock(return_value=iter([node1]))

        result = list(self.pipewire.iter_sources())

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0], node1)

    @patch(
        "checkbox_support.helpers.audio_server_utils.subprocess.check_output"
    )
    def test_set_sink(self, mock_check_output):
        """Test setting a sink as default."""
        node = Node("dev1", "prof1", "sink1", "123", "Sink 1")

        self.pipewire.set_sink(node)

        mock_check_output.assert_called_once_with(
            ["wpctl", "set-default", "123"]
        )

    @patch(
        "checkbox_support.helpers.audio_server_utils.subprocess.check_output"
    )
    def test_set_sink_error(self, mock_check_output):
        """Test setting a sink raises RuntimeError on failure."""
        mock_check_output.side_effect = subprocess.CalledProcessError(
            1, "wpctl"
        )
        node = Node("dev1", "prof1", "sink1", "123", "Sink 1")

        with self.assertRaises(RuntimeError) as cm:
            self.pipewire.set_sink(node)

        self.assertIn("sink1", str(cm.exception))
        self.assertIn("123", str(cm.exception))

    @patch(
        "checkbox_support.helpers.audio_server_utils.subprocess.check_output"
    )
    def test_set_source(self, mock_check_output):
        """Test setting a source as default."""
        node = Node("dev1", "prof1", "source1", "456", "Source 1")

        self.pipewire.set_source(node)

        mock_check_output.assert_called_once_with(
            ["wpctl", "set-default", "456"]
        )

    @patch(
        "checkbox_support.helpers.audio_server_utils.subprocess.check_output"
    )
    def test_set_source_error(self, mock_check_output):
        """Test setting a source raises RuntimeError on failure."""
        mock_check_output.side_effect = subprocess.CalledProcessError(
            1, "wpctl"
        )
        node = Node("dev1", "prof1", "source1", "456", "Source 1")

        with self.assertRaises(RuntimeError) as cm:
            self.pipewire.set_source(node)

        self.assertIn("source1", str(cm.exception))
        self.assertIn("456", str(cm.exception))

    @patch(
        "checkbox_support.helpers.audio_server_utils.subprocess.check_output"
    )
    def test_set_volume(self, mock_check_output):
        """Test setting volume on a node."""
        node = Node("dev1", "prof1", "sink1", "123", "Sink 1")

        self.pipewire.set_volume(node, 0.8)

        mock_check_output.assert_called_once_with(
            ["wpctl", "set-volume", "123", "0.8"]
        )

    def test_set_volume_invalid(self):
        """Test volume validation raises ValueError."""
        node = Node("dev1", "prof1", "sink1", "123", "Sink 1")

        with self.assertRaises(ValueError):
            self.pipewire.set_volume(node, 1.2)

        with self.assertRaises(ValueError):
            self.pipewire.set_volume(node, -0.1)

    @patch(
        "checkbox_support.helpers.audio_server_utils.subprocess.check_output"
    )
    def test_set_card_profile(self, mock_check_output):
        """Test setting card profile."""
        self.pipewire._set_card_profile("42", "5")

        mock_check_output.assert_called_once_with(
            ["pw-cli", "s", "42", "Profile", "{ index: 5 }"]
        )

    @patch(
        "checkbox_support.helpers.audio_server_utils.subprocess.check_output"
    )
    def test_set_card_profile_error(self, mock_check_output):
        """Test setting card profile raises on error."""
        mock_check_output.side_effect = subprocess.CalledProcessError(1, "")

        with self.assertRaises(RuntimeError):
            self.pipewire._set_card_profile("42", "5")

    def test_get_available_profiles(self):
        """Test getting available profiles for a device."""
        sink = {"available": "yes", "index": 1, "classes": [0, ["Audio/Sink"]]}
        source = {
            "available": "yes",
            "index": 1,
            "classes": [0, ["Audio/Source"]],
        }
        device = {"info": {"params": {"EnumProfile": [sink, source, {}]}}}
        profiles = self.pipewire._get_available_profiles(device, NodeType.SINK)
        self.assertEqual({"1": sink}, profiles)

        profiles = self.pipewire._get_available_profiles(
            device, NodeType.SOURCE
        )
        self.assertEqual({"1": source}, profiles)

    def test_set_node_of_type(self):
        """Test setting a node by type and name."""

        node = Node("1", "2", "name", "id", "description")
        raw_node = {"info": {"props": {"node.id": "id", "node.name": "name"}}}
        self.pipewire._set_card_profile = Mock()
        self.pipewire._set_default_audio_node = Mock()
        self.pipewire._get_audio_nodes = Mock(return_value={"id": raw_node})

        self.pipewire._set_node_of_type(node, NodeType.SINK)

        self.pipewire._set_card_profile.assert_called_once_with("1", "2")
        self.pipewire._set_default_audio_node.assert_called_once_with("id")

    def test_set_node_of_type_ephemeral(self):
        """Test setting a node by type and name when name/id changed."""

        node = Node("1", "2", "name.5", "id", "description")
        raw_node = {
            "info": {"props": {"node.id": "new_id", "node.name": "name.6"}}
        }
        self.pipewire._set_card_profile = Mock()
        self.pipewire._set_default_audio_node = Mock()
        self.pipewire._get_audio_nodes = Mock(return_value={"id": raw_node})

        self.pipewire._set_node_of_type(node, NodeType.SINK)

        self.pipewire._set_card_profile.assert_called_once_with("1", "2")
        self.pipewire._set_default_audio_node.assert_called_once_with("new_id")

    def test_set_node_of_type_not_found(self):
        """Test setting a node that cannot be found raises RuntimeError."""

        node = Node("1", "2", "name", "id", "description")
        self.pipewire._set_card_profile = Mock()
        self.pipewire._get_audio_nodes = Mock(return_value={})

        with self.assertRaises(RuntimeError) as cm:
            self.pipewire._set_node_of_type(node, NodeType.SINK)

        self.assertIn("name", str(cm.exception))
        self.assertIn("id", str(cm.exception))
        self.assertIn("not found", str(cm.exception))


class PulseaudioUtilsTests(unittest.TestCase):
    """Test cases for the PulseaudioUtils class."""

    def setUp(self):
        """Set up test fixtures."""
        self.pulseaudio = PulseaudioUtils()

    @patch(
        "checkbox_support.helpers.audio_server_utils.subprocess.check_output"
    )
    def test_parse_pactl_list_sinks(self, mock_check_output):
        """Test parsing pactl list sinks output."""
        mock_check_output.return_value = textwrap.dedent("""\
            Sink #0
            	State: SUSPENDED
            	Name: alsa_output.pci-0000_00_1f.3.analog-stereo
            	Description: Built-in Audio Analog Stereo
            	Driver: module-alsa-card.c
            	Sample Specification: s16le 2ch 44100Hz
            	Channel Map: front-left,front-right
            	Owner Module: 7
            	Mute: no
            	Volume: front-left: 65536 / 100% / 0.00 dB
            	Index: 0
            """)
        nodes = self.pulseaudio._parse_pactl_list("sinks")
        self.assertEqual(len(nodes), 1)
        self.assertEqual(
            nodes[0].name, "alsa_output.pci-0000_00_1f.3.analog-stereo"
        )
        self.assertEqual(nodes[0].description, "Built-in Audio Analog Stereo")
        self.assertEqual(nodes[0].id, "0")

    @patch(
        "checkbox_support.helpers.audio_server_utils.subprocess.check_output"
    )
    def test_parse_pactl_list_multiple_sinks(self, mock_check_output):
        """Test parsing pactl output with multiple sinks."""
        mock_check_output.return_value = textwrap.dedent("""\
            Sink #0
            	State: SUSPENDED
            	Name: alsa_output.pci-0000_00_1f.3.analog-stereo
            	Description: Built-in Audio Analog Stereo
            	Driver: module-alsa-card.c
            	Sample Specification: s16le 2ch 44100Hz
            	Channel Map: front-left,front-right
            	Owner Module: 7
            	Mute: no
            	Volume: front-left: 65536 / 100%
            	Index: 0

            Sink #1
            	State: RUNNING
            	Name: alsa_output.usb-Generic_USB_Audio-00.analog-stereo
            	Description: USB Audio Analog Stereo
            	Driver: module-alsa-card.c
            	Sample Specification: s16le 2ch 48000Hz
            	Channel Map: front-left,front-right
            	Owner Module: 23
            	Mute: no
            	Volume: front-left: 45000 / 69%
            	Index: 1

            Sink #42
            	State: IDLE
            	Name: bluez_sink.AA_BB_CC_DD_EE_FF.a2dp_sink
            	Description: WH-1000XM4
            	Driver: module-bluez5-device.c
            	Sample Specification: s16le 2ch 44100Hz
            	Channel Map: front-left,front-right
            	Owner Module: 31
            	Mute: no
            	Volume: front-left: 32768 / 50%
            	Index: 42
            """)
        nodes = self.pulseaudio._parse_pactl_list("sinks")
        self.assertEqual(len(nodes), 3)

        self.assertEqual(
            nodes[0].name, "alsa_output.pci-0000_00_1f.3.analog-stereo"
        )
        self.assertEqual(nodes[0].description, "Built-in Audio Analog Stereo")
        self.assertEqual(nodes[0].id, "0")

        self.assertEqual(
            nodes[1].name, "alsa_output.usb-Generic_USB_Audio-00.analog-stereo"
        )
        self.assertEqual(nodes[1].description, "USB Audio Analog Stereo")
        self.assertEqual(nodes[1].id, "1")

        self.assertEqual(
            nodes[2].name, "bluez_sink.AA_BB_CC_DD_EE_FF.a2dp_sink"
        )
        self.assertEqual(nodes[2].description, "WH-1000XM4")
        self.assertEqual(nodes[2].id, "42")

    @patch(
        "checkbox_support.helpers.audio_server_utils.subprocess.check_output"
    )
    def test_parse_pactl_list_sources(self, mock_check_output):
        """Test parsing pactl list sources output."""
        mock_check_output.return_value = textwrap.dedent("""\
            Source #0
            	State: SUSPENDED
            	Name: alsa_input.pci-0000_00_1f.3.analog-stereo
            	Description: Built-in Audio Analog Stereo
            	Driver: module-alsa-card.c
            	Sample Specification: s16le 2ch 44100Hz
            	Channel Map: front-left,front-right
            	Owner Module: 7
            	Mute: no
            	Volume: front-left: 65536 / 100%
            	Index: 0

            Source #1
            	State: RUNNING
            	Name: alsa_output.pci-0000_00_1f.3.analog-stereo.monitor
            	Description: Monitor of Built-in Audio Analog Stereo
            	Driver: module-alsa-card.c
            	Sample Specification: s16le 2ch 44100Hz
            	Channel Map: front-left,front-right
            	Owner Module: 7
            	Mute: no
            	Volume: front-left: 65536 / 100%
            	Index: 1
            """)
        nodes = self.pulseaudio._parse_pactl_list("sources")
        self.assertEqual(len(nodes), 2)

        self.assertEqual(
            nodes[0].name, "alsa_input.pci-0000_00_1f.3.analog-stereo"
        )
        self.assertEqual(nodes[0].description, "Built-in Audio Analog Stereo")
        self.assertEqual(nodes[0].id, "0")

        self.assertEqual(
            nodes[1].name, "alsa_output.pci-0000_00_1f.3.analog-stereo.monitor"
        )
        self.assertEqual(
            nodes[1].description, "Monitor of Built-in Audio Analog Stereo"
        )
        self.assertEqual(nodes[1].id, "1")

    @patch(
        "checkbox_support.helpers.audio_server_utils.subprocess.check_output"
    )
    def test_parse_pactl_list_empty(self, mock_check_output):
        """Test parsing empty pactl output."""
        mock_check_output.return_value = ""
        nodes = self.pulseaudio._parse_pactl_list("sinks")
        self.assertEqual(len(nodes), 0)

    def test_list_sinks(self):
        """Test listing all available sinks."""
        node1 = Node("0", None, "sink1", "0", "Sink 1")
        self.pulseaudio._parse_pactl_list = Mock(return_value=[node1])

        sinks = self.pulseaudio.list_sinks()

        self.assertEqual(len(sinks), 1)
        self.assertEqual(sinks[0], node1)
        self.pulseaudio._parse_pactl_list.assert_called_once_with("sinks")

    def test_list_sources(self):
        """Test listing all available sources."""
        node1 = Node("0", None, "source1", "0", "Source 1")
        self.pulseaudio._parse_pactl_list = Mock(return_value=[node1])

        sources = self.pulseaudio.list_sources()

        self.assertEqual(len(sources), 1)
        self.assertEqual(sources[0], node1)
        self.pulseaudio._parse_pactl_list.assert_called_once_with("sources")

    def test_iter_sinks(self):
        """Test iterating over sinks."""
        node1 = Node("0", None, "sink1", "0", "Sink 1")
        node2 = Node("1", None, "sink2", "1", "Sink 2")
        self.pulseaudio._parse_pactl_list = Mock(return_value=[node1, node2])

        result = list(self.pulseaudio.iter_sinks())

        self.assertEqual(len(result), 2)
        self.assertEqual(result[0], node1)
        self.assertEqual(result[1], node2)

    def test_iter_sources(self):
        """Test iterating over sources."""
        node1 = Node("0", None, "source1", "0", "Source 1")
        self.pulseaudio._parse_pactl_list = Mock(return_value=[node1])

        result = list(self.pulseaudio.iter_sources())

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0], node1)

    @patch(
        "checkbox_support.helpers.audio_server_utils.subprocess.check_output"
    )
    def test_set_sink(self, mock_check_output):
        """Test setting a sink as default."""
        node = Node("0", None, "test_sink", "0", "Test Sink")

        self.pulseaudio.set_sink(node)

        mock_check_output.assert_called_once_with(
            ["pactl", "set-default-sink", "test_sink"]
        )

    @patch(
        "checkbox_support.helpers.audio_server_utils.subprocess.check_output"
    )
    def test_set_sink_error(self, mock_check_output):
        """Test setting a sink raises on error."""
        mock_check_output.side_effect = subprocess.CalledProcessError(1, "")
        node = Node("0", None, "test_sink", "0", "Test Sink")

        with self.assertRaises(RuntimeError):
            self.pulseaudio.set_sink(node)

    @patch(
        "checkbox_support.helpers.audio_server_utils.subprocess.check_output"
    )
    def test_set_source(self, mock_check_output):
        """Test setting a source as default."""
        node = Node("0", None, "test_source", "0", "Test Source")

        self.pulseaudio.set_source(node)

        mock_check_output.assert_called_once_with(
            ["pactl", "set-default-source", "test_source"]
        )

    @patch(
        "checkbox_support.helpers.audio_server_utils.subprocess.check_output"
    )
    def test_set_source_error(self, mock_check_output):
        """Test setting a source raises RuntimeError on error."""
        mock_check_output.side_effect = subprocess.CalledProcessError(
            1, "pactl"
        )
        node = Node("0", None, "test_source", "0", "Test Source")

        with self.assertRaises(RuntimeError):
            self.pulseaudio.set_source(node)

    @patch(
        "checkbox_support.helpers.audio_server_utils.subprocess.check_output"
    )
    def test_set_volume_sink(self, mock_check_output):
        """Test setting volume on a sink."""
        node = Node("0", None, "test_sink", "0", "Test Sink")

        self.pulseaudio.set_volume(node, 0.5)

        mock_check_output.assert_called_once_with(
            ["pactl", "set-sink-volume", "test_sink", "50%"]
        )

    def test_set_volume_invalid(self):
        """Test setting invalid volume raises ValueError."""
        node = Node("0", None, "test_sink", "0", "Test Sink")

        with self.assertRaises(ValueError):
            self.pulseaudio.set_volume(node, 1.5)

        with self.assertRaises(ValueError):
            self.pulseaudio.set_volume(node, -0.1)


class IntegrationTests(unittest.TestCase):
    """Integration tests from list to set sink/volume using both servers."""

    @patch(
        "checkbox_support.helpers.audio_server_utils.AudioServerUtils.get_server"
    )
    @patch(
        "checkbox_support.helpers.audio_server_utils.subprocess.check_output"
    )
    def test_pipewire_workflow(self, mock_check_output, mock_get_server):
        """Test PipeWire workflow: iterate sinks and set one as default."""
        mock_get_server.return_value = AudioServer.PIPEWIRE

        device = {
            "id": 100,
            "type": "PipeWire:Interface:Device",
            "info": {
                "props": {
                    "media.class": "Audio/Device",
                    "device.name": "alsa_card.pci-0000_00_1f.3",
                },
                "params": {
                    "EnumProfile": [
                        {
                            "index": 0,
                            "name": "output:analog-stereo",
                            "available": "yes",
                            "classes": [1, ["Audio/Sink"]],
                        },
                        {
                            "index": 1,
                            "name": "output:hdmi-stereo",
                            "available": "yes",
                            "classes": [1, ["Audio/Sink"]],
                        },
                    ]
                },
            },
        }
        analog_sink = {
            "id": 200,
            "type": "PipeWire:Interface:Node",
            "info": {
                "props": {
                    "media.class": "Audio/Sink",
                    "node.name": "analog-stereo",
                    "node.description": "Analog",
                    "node.id": "200",
                }
            },
        }
        hdmi_sink = {
            "id": 201,
            "type": "PipeWire:Interface:Node",
            "info": {
                "props": {
                    "media.class": "Audio/Sink",
                    "node.name": "hdmi-stereo",
                    "node.description": "HDMI",
                    "node.id": "201",
                }
            },
        }

        mock_check_output.side_effect = [
            json.dumps([device]),
            "",  # pw-cli set profile
            json.dumps([device, analog_sink]),
            "",  # pw-cli set profile
            json.dumps([device, hdmi_sink]),
            "",  # wpctl set-default
            "",  # wpctl set-volume
        ]

        audio = AudioServerUtils()
        self.assertIsInstance(audio, PipewireUtils)

        sinks = list(audio.iter_sinks())

        self.assertEqual(len(sinks), 2)
        self.assertEqual(sinks[0].name, "analog-stereo")
        self.assertEqual(sinks[0].description, "Analog")
        self.assertEqual(sinks[1].name, "hdmi-stereo")
        self.assertEqual(sinks[1].description, "HDMI")

        audio.set_sink(sinks[0])
        mock_check_output.assert_called_with(
            ["wpctl", "set-default", "200"]
        )

        audio.set_volume(sinks[0], 0.75)
        mock_check_output.assert_called_with(
            ["wpctl", "set-volume", "200", "0.75"]
        )

    @patch(
        "checkbox_support.helpers.audio_server_utils.AudioServerUtils.get_server"
    )
    @patch(
        "checkbox_support.helpers.audio_server_utils.subprocess.check_output"
    )
    def test_pulseaudio_workflow(self, mock_check_output, mock_get_server):
        """Test PulseAudio workflow: iterate sinks and set one as default."""
        mock_get_server.return_value = AudioServer.PULSEAUDIO

        pactl_output = textwrap.dedent("""\
            Sink #0
            	State: RUNNING
            	Name: alsa_output.pci-0000_00_1f.3.analog-stereo
            	Description: Built-in Audio Analog Stereo
            	Driver: module-alsa-card.c
            	Index: 0

            Sink #1
            	State: IDLE
            	Name: alsa_output.usb-audio.analog-stereo
            	Description: USB Audio
            	Driver: module-alsa-card.c
            	Index: 1
            """)

        def check_output_side_effect(cmd, **kwargs):
            if cmd == ["pactl", "list", "sinks"]:
                return pactl_output
            return ""

        mock_check_output.side_effect = check_output_side_effect

        audio = AudioServerUtils()
        self.assertIsInstance(audio, PulseaudioUtils)

        sinks = list(audio.iter_sinks())

        self.assertEqual(len(sinks), 2)
        self.assertEqual(
            sinks[0].name, "alsa_output.pci-0000_00_1f.3.analog-stereo"
        )
        self.assertEqual(sinks[0].description, "Built-in Audio Analog Stereo")
        self.assertEqual(sinks[1].name, "alsa_output.usb-audio.analog-stereo")
        self.assertEqual(sinks[1].description, "USB Audio")

        mock_check_output.side_effect = None

        audio.set_sink(sinks[0])
        mock_check_output.assert_called_with(
            ["pactl", "set-default-sink", "alsa_output.pci-0000_00_1f.3.analog-stereo"]
        )

        audio.set_volume(sinks[0], 0.75)
        mock_check_output.assert_called_with(
            ["pactl", "set-sink-volume", "alsa_output.pci-0000_00_1f.3.analog-stereo", "75%"]
        )
