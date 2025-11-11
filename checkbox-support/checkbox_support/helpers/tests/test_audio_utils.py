import json
import subprocess
import unittest
from unittest.mock import MagicMock, Mock, patch

from checkbox_support.helpers.audio_utils import (
    AudioUtils,
    Node,
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


class AudioUtilsTests(unittest.TestCase):
    """Test cases for the AudioUtils factory class."""

    @patch("checkbox_support.helpers.audio_utils.subprocess.check_call")
    def test_get_server_pipewire(self, mock_check_call):
        """Test detection of PipeWire audio server."""

        mock_check_call.side_effect = [None, subprocess.CalledProcessError(1, "")]
        server = AudioUtils.get_server()
        self.assertEqual(server, "pipewire")

    @patch("checkbox_support.helpers.audio_utils.subprocess.check_call")
    def test_get_server_pulseaudio(self, mock_check_call):
        """Test detection of PulseAudio audio server."""

        mock_check_call.side_effect = [subprocess.CalledProcessError(1, ""), None]
        server = AudioUtils.get_server()
        self.assertEqual(server, "pulseaudio")

    @patch("checkbox_support.helpers.audio_utils.subprocess.check_call")
    def test_get_server_none(self, mock_check_call):
        """Test OSError when no audio server is running."""
        mock_check_call.side_effect = subprocess.CalledProcessError(1, "")
        with self.assertRaises(OSError):
            AudioUtils.get_server()

    @patch("checkbox_support.helpers.audio_utils.AudioUtils.get_server")
    def test_factory_returns_pipewire_utils(self, mock_get_server):
        """Test factory returns PipewireUtils instance."""
        mock_get_server.return_value = "pipewire"
        audio = AudioUtils()
        self.assertIsInstance(audio, PipewireUtils)

    @patch("checkbox_support.helpers.audio_utils.AudioUtils.get_server")
    def test_factory_returns_pulseaudio_utils(self, mock_get_server):
        """Test factory returns PulseaudioUtils instance."""
        mock_get_server.return_value = "pulseaudio"
        audio = AudioUtils()
        self.assertIsInstance(audio, PulseaudioUtils)


class PipewireUtilsTests(unittest.TestCase):
    """Test cases for the PipewireUtils class."""

    def setUp(self):
        """Set up test fixtures."""
        self.pipewire = PipewireUtils()

    @patch("checkbox_support.helpers.audio_utils.subprocess.check_output")
    def test_load_pw_dump_success(self, mock_check_output):
        """Test successful pw-dump load."""
        mock_check_output.return_value = b'[{"id": 1, "type": "test"}]'
        result = self.pipewire._load_pw_dump()
        self.assertEqual(result, [{"id": 1, "type": "test"}])

    @patch("time.sleep", Mock())
    @patch("checkbox_support.helpers.audio_utils.subprocess.check_output")
    def test_load_pw_dump_retry(self, mock_check_output):
        """Test pw-dump retry on failure."""
        mock_check_output.side_effect = [
            subprocess.CalledProcessError(1, ""),
            json.JSONDecodeError("", "", 0),
            b'[{"id": 2, "type": "test3"}]',
        ]
        result = self.pipewire._load_pw_dump()
        self.assertEqual(result, [{"id": 2, "type": "test3"}])

    @patch("time.sleep", Mock())
    @patch("checkbox_support.helpers.audio_utils.subprocess.check_output")
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
        sinks = self.pipewire._get_audio_nodes("Sink")
        self.assertEqual({"1": sink}, sinks)

        # Sources
        sources = self.pipewire._get_audio_nodes("Source")
        self.assertEqual({"2": source}, sources)

    def test_list_sinks(self):
        """Test listing all available sinks."""
        raise NotImplementedError

    def test_iter_sinks(self):
        """Test iterating over sinks."""
        raise NotImplementedError

    def test_set_sink(self):
        """Test setting a sink as default."""
        raise NotImplementedError

    def test_set_volume(self):
        """Test setting volume on a node."""
        raise NotImplementedError


class PulseaudioUtilsTests(unittest.TestCase):
    """Test cases for the PulseaudioUtils class."""

    def setUp(self):
        """Set up test fixtures."""
        self.pulseaudio = PulseaudioUtils()

    @patch("checkbox_support.helpers.audio_utils.subprocess.check_output")
    def test_parse_pactl_list_sinks(self, mock_check_output):
        """Test parsing pactl list sinks output."""
        mock_check_output.return_value = b"""Sink #0
	Name: alsa_output.pci-0000_00_1f.3.analog-stereo
	Description: Built-in Audio Analog Stereo
	Index: 0
"""
        nodes = self.pulseaudio._parse_pactl_list("sinks")
        self.assertEqual(len(nodes), 1)
        self.assertEqual(nodes[0].name, "alsa_output.pci-0000_00_1f.3.analog-stereo")
        self.assertEqual(nodes[0].description, "Built-in Audio Analog Stereo")

    def test_list_sinks(self):
        """Test listing all available sinks."""
        raise NotImplementedError

    def test_iter_sinks(self):
        """Test iterating over sinks."""
        raise NotImplementedError

    def test_set_sink(self):
        """Test setting a sink as default."""
        raise NotImplementedError

    def test_set_volume(self):
        """Test setting volume on a node."""
        raise NotImplementedError


if __name__ == "__main__":
    unittest.main()
