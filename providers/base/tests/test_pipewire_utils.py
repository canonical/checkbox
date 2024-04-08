# Copyright 2023 Canonical Ltd.
# Written by:
#   Hanhsuan Lee <hanhsuan.lee@canonical.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3,
# as published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

# There are some issue with assertLog for python version lower than 3.10,
# https://github.com/python/cpython/commit/6fdfcec5b11f44f27aae3d53ddeb004150ae1f61
# Therefore, please don't add new test cases of assertLog.

import unittest
import sys
from unittest.mock import MagicMock, patch
sys.modules["gi"] = MagicMock()
sys.modules["gi.repository"] = MagicMock()
from pipewire_utils import *


class GetPwTypeTests(unittest.TestCase):

    def test_succ(self):
        pt = PipewireTest()

        # return Output
        self.assertEqual("Output",
                         pt._get_pw_type("sinks"))
        self.assertEqual("Output",
                         pt._get_pw_type("Sinks"))
        self.assertEqual("Output",
                         pt._get_pw_type("Sink"))

        # return Input
        self.assertEqual("Input",
                         pt._get_pw_type("sources"))
        self.assertEqual("Input",
                         pt._get_pw_type("Sources"))
        self.assertEqual("Input",
                         pt._get_pw_type("Source"))

        # return UNKNOWN CLASS
        self.assertEqual("UNKNOWN CLASS",
                         pt._get_pw_type("xxxx"))


class GeneratePwMediaClassTests(unittest.TestCase):

    def test_succ(self):
        pt = PipewireTest()

        # return Audio/Sink
        self.assertEqual("Audio/Sink",
                         pt.generate_pw_media_class("audio", "sink"))
        self.assertEqual("Audio/Sink",
                         pt.generate_pw_media_class("audio", "Sink"))
        self.assertEqual("Audio/Sink",
                         pt.generate_pw_media_class("Audio", "sink"))
        self.assertEqual("Audio/Sink",
                         pt.generate_pw_media_class("Audio", "Sink"))
        self.assertEqual("Audio/Sink",
                         pt.generate_pw_media_class("Audio", "Sinks"))

        # return Audio/Source
        self.assertEqual("Audio/Source",
                         pt.generate_pw_media_class("audio", "source"))
        self.assertEqual("Audio/Source",
                         pt.generate_pw_media_class("audio", "Source"))
        self.assertEqual("Audio/Source",
                         pt.generate_pw_media_class("Audio", "source"))
        self.assertEqual("Audio/Source",
                         pt.generate_pw_media_class("Audio", "Source"))
        self.assertEqual("Audio/Source",
                         pt.generate_pw_media_class("Audio", "Sources"))

        # return Video/Sink
        self.assertEqual("Video/Sink",
                         pt.generate_pw_media_class("video", "sink"))
        self.assertEqual("Video/Sink",
                         pt.generate_pw_media_class("video", "Sink"))
        self.assertEqual("Video/Sink",
                         pt.generate_pw_media_class("Video", "sink"))
        self.assertEqual("Video/Sink",
                         pt.generate_pw_media_class("Video", "Sink"))
        self.assertEqual("Video/Sink",
                         pt.generate_pw_media_class("Video", "Sinks"))

        # return Video/Source
        self.assertEqual("Video/Source",
                         pt.generate_pw_media_class("video", "source"))
        self.assertEqual("Video/Source",
                         pt.generate_pw_media_class("video", "Source"))
        self.assertEqual("Video/Source",
                         pt.generate_pw_media_class("Video", "source"))
        self.assertEqual("Video/Source",
                         pt.generate_pw_media_class("Video", "Source"))
        self.assertEqual("Video/Source",
                         pt.generate_pw_media_class("Video", "Sources"))

    def test_fail(self):
        pt = PipewireTest()

        # return UNKNOWN TYPE
        wrong_type1 = "videog"
        wrong_type2 = "xxxx"
        self.assertEqual("UNKNOWN TYPE",
                         pt.generate_pw_media_class(wrong_type1,
                                                    "source"))
        self.assertEqual("UNKNOWN TYPE",
                         pt.generate_pw_media_class(wrong_type2,
                                                    "sources"))

        # example code for testing log output in python 3.10 and above
        # with self.assertLogs("root", level="INFO") as cm:
        #     wrong_type1 = "videog"
        #     wrong_type2 = "xxxx"
        #     self.assertEqual("UNKNOWN TYPE",
        #                      pt.generate_pw_media_class(wrong_type1,
        #                                                 "source"))
        #     self.assertEqual("UNKNOWN TYPE",
        #                      pt.generate_pw_media_class(wrong_type2,
        #                                                 "sources"))
        #     # check log output
        #     self.assertEqual(cm.output,
        #                      ["INFO:root:Media type:[{}] is unknown"
        #                       .format(wrong_type1),
        #                       "INFO:root:Media type:[{}] is unknown"
        #                       .format(wrong_type2)])

        # return UNKNOWN CLASS
        wrong_class1 = "sourceg"
        wrong_class2 = "sinkf"
        self.assertEqual("UNKNOWN CLASS",
                         pt.generate_pw_media_class("video",
                                                    wrong_class1))
        self.assertEqual("UNKNOWN CLASS",
                         pt.generate_pw_media_class("video",
                                                    wrong_class2))


class DetectDeviceTests(unittest.TestCase):

    # Correct Node
    sink_audio_node = """
                       [{
                        "id": 29,
                        "type": "PipeWire:Interface:Node",
                        "version": 3,
                        "permissions": [ "r", "w", "x", "m" ],
                        "info": {
                          "max-input-ports": 0,
                          "max-output-ports": 0,
                          "change-mask": [ "input-ports",
                                           "output-ports",
                                           "state", "props",
                                           "params" ],
                          "n-input-ports": 0,
                          "n-output-ports": 0,
                          "state": "suspended",
                          "error": null,
                          "props": {
                            "media.class": "Audio/Sink",
                            "factory.name": "support.node.driver",
                            "node.name": "Freewheel-Driver",
                            "priority.driver": 19000,
                            "node.group": "pipewire.freewheel",
                            "node.freewheel": true,
                            "factory.id": 10,
                            "clock.quantum-limit": 8192,
                            "node.driver": true,
                            "object.id": 29,
                            "object.serial": 29
                          },
                          "params": {
                          }
                        }
                      }]"""

    source_audio_node = """
                         [{
                           "id": 30,
                           "type": "PipeWire:Interface:Node",
                           "version": 3,
                           "permissions": [ "r", "w", "x", "m" ],
                           "info": {
                             "max-input-ports": 0,
                             "max-output-ports": 0,
                             "change-mask": [ "input-ports",
                                              "output-ports",
                                              "state", "props",
                                              "params" ],
                             "n-input-ports": 0,
                             "n-output-ports": 0,
                             "state": "suspended",
                             "error": null,
                             "props": {
                               "media.class": "Audio/Source",
                               "factory.name": "support.node.driver",
                               "node.name": "Freewheel-Driver",
                               "priority.driver": 19000,
                               "node.group": "pipewire.freewheel",
                               "node.freewheel": true,
                               "factory.id": 10,
                               "clock.quantum-limit": 8192,
                               "node.driver": true,
                               "object.id": 29,
                               "object.serial": 29
                             },
                             "params": {
                             }
                           }
                         }]"""

    @patch("subprocess.check_output")
    def test_succ(self, mock_checkout):
        pt = PipewireTest()

        # detect audio sink succ
        mock_checkout.return_value = self.sink_audio_node
        self.assertEqual(PipewireTestError.NO_ERROR,
                         pt.detect_device("audio", "sink"))

        # detect audio source succ
        mock_checkout.return_value = self.source_audio_node
        self.assertEqual(PipewireTestError.NO_ERROR,
                         pt.detect_device("audio", "source"))

    @patch("subprocess.check_output")
    def test_fail(self, mock_checkout):
        pt = PipewireTest()

        # detect audio sink fail
        mock_checkout.return_value = self.source_audio_node
        self.assertEqual(PipewireTestError.NOT_DETECTED,
                         pt.detect_device("audio", "sink"))

        # detect audio source fail
        mock_checkout.return_value = self.sink_audio_node
        self.assertEqual(PipewireTestError.NOT_DETECTED,
                         pt.detect_device("audio", "source"))

        # wrong media class
        mock_checkout.return_value = self.sink_audio_node
        self.assertEqual(PipewireTestError.NOT_DETECTED,
                         pt.detect_device("xxx", "ooo"))


class SelectDeviceTests(unittest.TestCase):

    # Correct Node
    sink_audio_node = """
                       [{
                        "id": 29,
                        "type": "PipeWire:Interface:Node",
                        "version": 3,
                        "permissions": [ "r", "w", "x", "m" ],
                        "info": {
                          "max-input-ports": 0,
                          "max-output-ports": 0,
                          "change-mask": [ "input-ports",
                                           "output-ports",
                                           "state", "props",
                                           "params" ],
                          "n-input-ports": 0,
                          "n-output-ports": 0,
                          "state": "suspended",
                          "error": null,
                          "props": {
                            "media.class": "Audio/Sink",
                            "factory.name": "support.node.driver",
                            "node.name": "demo-hdmi",
                            "node.description": "unit test",
                            "priority.driver": 19000,
                            "node.group": "pipewire.freewheel",
                            "node.freewheel": true,
                            "factory.id": 10,
                            "clock.quantum-limit": 8192,
                            "node.driver": true,
                            "object.id": 29,
                            "object.serial": 29
                          },
                          "params": {
                          }
                        }
                      }]"""

    @patch("subprocess.check_output")
    def test_wrong_pw_dump(self, mock_checkout):
        pt = PipewireTest()

        mock_checkout.return_value = "xxxx"
        self.assertEqual(PipewireTestError.NO_AVAILABLE_PORT,
                         pt.select_device("video", "sink", "hdmi"))

    @patch("subprocess.check_output")
    def test_no_available_node(self, mock_checkout):
        pt = PipewireTest()

        # parameters error
        self.assertEqual(PipewireTestError.NO_AVAILABLE_PORT,
                         pt.select_device("xxx", "sink", "hdmi"))
        self.assertEqual(PipewireTestError.NO_AVAILABLE_PORT,
                         pt.select_device("video", "xxx", "hdmi"))

        mock_checkout.return_value = self.sink_audio_node
        self.assertEqual(PipewireTestError.NO_AVAILABLE_PORT,
                         pt.select_device("video", "sink", "hdmi"))

    @patch("builtins.input")
    @patch("subprocess.check_output")
    def test_succ(self, mock_checkout, mock_input):
        mock_checkout.return_value = self.sink_audio_node
        mock_input.side_effect = ["t", 29]
        pt = PipewireTest()
        self.assertEqual(PipewireTestError.NO_ERROR,
                         pt.select_device("audio", "sink", "hdmi"))

    @patch("builtins.input")
    @patch("subprocess.check_output")
    def test_exit(self, mock_checkout, mock_input):
        mock_checkout.return_value = self.sink_audio_node
        mock_input.side_effect = ["t", "-1"]
        pt = PipewireTest()
        self.assertEqual(PipewireTestError.NO_ERROR,
                         pt.select_device("audio", "sink", "hdmi"))


class GstPipeLineTests(unittest.TestCase):

    # Correct Device
    device = """
              [{
               "id": 29,
               "type": "PipeWire:Interface:Device",
               "version": 3,
               "permissions": [ "r", "w", "x", "m" ],
               "info": {
                 "max-input-ports": 0,
                 "max-output-ports": 0,
                 "change-mask": [ "input-ports",
                                  "output-ports",
                                  "state", "props",
                                  "params" ],
                 "n-input-ports": 0,
                 "n-output-ports": 0,
                 "state": "suspended",
                 "error": null,
                 "props": {
                   "media.class": "Audio/Device",
                   "factory.name": "support.node.driver",
                   "node.name": "Freewheel-Driver",
                   "node.description": "unit test",
                   "priority.driver": 19000,
                   "node.group": "pipewire.freewheel",
                   "node.freewheel": true,
                   "factory.id": 10,
                   "clock.quantum-limit": 8192,
                   "node.driver": true,
                   "object.id": 29,
                   "object.serial": 29
                 },
                 "params": {
                     "Route": [{
                         "name": "hdmi_demo_output",
                         "available": "yes",
                         "description": "hdmi demo output",
                         "direction": "Output"
                     }]
                 }
               }
              }]"""

    @patch("subprocess.check_output")
    def test_wrong_gst_pipeline_device(self, mock_checkout):
        pt = PipewireTest()

        mock_checkout.return_value = self.device
        self.assertEqual(PipewireTestError.NO_SPECIFIC_DEVICE,
                         pt.gst_pipeline("pipe", 10, "qoo"))

    @patch("time.sleep")
    @patch("subprocess.check_output")
    def test_gst_pipeline(self, mock_checkout, _):
        pt = PipewireTest()

        mock_checkout.return_value = self.device
        self.assertEqual(PipewireTestError.NO_ERROR,
                         pt.gst_pipeline("audiotestsrc wave=sine freq=512"
                                         " ! audioconvert ! audioresample"
                                         " ! autoaudiosink", 2, "hdmi"))


class MonitorActivePortTests(unittest.TestCase):

    # Correct Device
    before_device = """
                     [{
                       "id": 29,
                       "type": "PipeWire:Interface:Device",
                       "version": 3,
                       "permissions": [ "r", "w", "x", "m" ],
                       "info": {
                         "max-input-ports": 0,
                         "max-output-ports": 0,
                         "change-mask": [ "input-ports",
                                          "output-ports",
                                          "state", "props",
                                          "params" ],
                         "n-input-ports": 0,
                         "n-output-ports": 0,
                         "state": "suspended",
                         "error": null,
                         "props": {
                           "media.class": "Audio/Device",
                           "factory.name": "support.node.driver",
                           "node.name": "Freewheel-Driver",
                           "node.description": "unit test",
                           "priority.driver": 19000,
                           "node.group": "pipewire.freewheel",
                           "node.freewheel": true,
                           "factory.id": 10,
                           "clock.quantum-limit": 8192,
                           "node.driver": true,
                           "object.id": 29,
                           "object.serial": 29
                         },
                         "params": {
                             "Route": [{
                                 "name": "hdmi_demo_output",
                                 "available": "yes",
                                 "direction": "Output",
                                 "description": "hdmi demo output"
                             }]
                         }
                       }
                      }]"""

    # Correct Device
    after_device = """
                    [{
                      "id": 29,
                      "type": "PipeWire:Interface:Device",
                      "version": 3,
                      "permissions": [ "r", "w", "x", "m" ],
                      "info": {
                        "max-input-ports": 0,
                        "max-output-ports": 0,
                        "change-mask": [ "input-ports",
                                         "output-ports",
                                         "state", "props",
                                         "params" ],
                        "n-input-ports": 0,
                        "n-output-ports": 0,
                        "state": "suspended",
                        "error": null,
                        "props": {
                          "media.class": "Audio/Device",
                          "factory.name": "support.node.driver",
                          "node.name": "Freewheel-Driver",
                          "node.description": "unit test",
                          "priority.driver": 19000,
                          "node.group": "pipewire.freewheel",
                          "node.freewheel": true,
                          "factory.id": 10,
                          "clock.quantum-limit": 8192,
                          "node.driver": true,
                          "object.id": 29,
                          "object.serial": 29
                        },
                        "params": {
                            "Route": [{
                                "name": "hdmi_after_output",
                                "available": "yes",
                                "direction": "Output",
                                "description": "hdmi after output"
                            }]
                        }
                      }
                     }]"""

    @patch("time.sleep")
    @patch("subprocess.check_output")
    def test_couldnt_detect_change(self, mock_checkout, _):
        pt = PipewireTest()

        mock_checkout.return_value = self.before_device
        self.assertEqual(PipewireTestError.NO_CHANGE_DETECTED,
                         pt.monitor_active_port_change(2, "sink"))

    @patch("subprocess.check_output")
    def test_could_detect_change(self, mock_checkout):
        pt = PipewireTest()

        mock_checkout.side_effect = [self.before_device, self.after_device]
        self.assertEqual(PipewireTestError.NO_ERROR,
                         pt.monitor_active_port_change(2, "sink"))


class GoThroughPortTests(unittest.TestCase):

    # Correct Device
    device = """[{
                 "id": 29,
                 "type": "PipeWire:Interface:Device",
                 "version": 3,
                 "permissions": [ "r", "w", "x", "m" ],
                 "info": {
                   "max-input-ports": 0,
                   "max-output-ports": 0,
                   "change-mask": [ "input-ports",
                                    "output-ports",
                                    "state", "props",
                                    "params" ],
                   "n-input-ports": 0,
                   "n-output-ports": 0,
                   "state": "suspended",
                   "error": null,
                   "props": {
                     "media.class": "Audio/Device",
                     "factory.name": "support.node.driver",
                     "node.name": "Freewheel-Driver",
                     "node.description": "unit test",
                     "priority.driver": 19000,
                     "node.group": "pipewire.freewheel",
                     "node.freewheel": true,
                     "factory.id": 10,
                     "clock.quantum-limit": 8192,
                     "node.driver": true,
                     "object.id": 29,
                     "object.serial": 29
                   },
                   "params": {
                       "EnumRoute": [{
                           "name": "hdmi_demo_output",
                           "available": "yes",
                           "direction": "Output",
                           "description": "hdmi demo output"
                       }]
                   }
                 }
                }]"""

    @patch("builtins.input")
    @patch("subprocess.check_output")
    def test_though(self, mock_checkout, mock_input):
        pt = PipewireTest()

        mock_checkout.return_value = self.device
        mock_input.side_effect = ["yes", "yes"]
        self.assertEqual(None, pt.go_through_ports("echo test", "sink"))


class ShowDefaultDeviceTests(unittest.TestCase):

    def test_device_type_error(self):
        pt = PipewireTest()

        with self.assertRaises(ValueError):
            pt.show_default_device("XXX")

    @patch("subprocess.check_output")
    def test_video_sink_not_call(self, mock_check):
        pt = PipewireTest()

        mock_check.side_effect = ["node.description=xxx",
                                  "node.description=ooo"]
        pt.show_default_device("VIDEO")
        mock_check.assert_called_with(["wpctl", "inspect",
                                       "@DEFAULT_VIDEO_SOURCE@"],
                                      universal_newlines=True)

    @patch("subprocess.check_output")
    def test_audio(self, mock_check):
        pt = PipewireTest()

        mock_check.side_effect = ["node.description=xxx",
                                  "node.description=ooo"]
        pt.show_default_device("AUDIO")
        mock_check.assert_called_with(["wpctl", "inspect",
                                       "@DEFAULT_AUDIO_SINK@"],
                                      universal_newlines=True)


class SortWpctlStatusTests(unittest.TestCase):

    status = """
PipeWire 'pipewire-0' [0.3.79, u@u-Precision-5550, cookie:2611513056]
 └─ Clients:
      31. pipewire                        [0.3.79, u@u-Precision-5550, pid:135]
      33. WirePlumber                     [0.3.79, u@u-Precision-5550, pid:135]
      34. WirePlumber [export]            [0.3.79, u@u-Precision-5550, pid:135]
      48. GNOME Volume Control Media Keys [0.3.79, u@u-Precision-5550, pid:222]
      49. gnome-shell                     [0.3.79, u@u-Precision-5550, pid:197]
      50. GNOME Shell Volume Control      [0.3.79, u@u-Precision-5550, pid:197]
      51. xdg-desktop-portal              [0.3.79, u@u-Precision-5550, pid:215]
      52. Terminal                        [0.3.79, u@u-Precision-5550, pid:282]
      53. Mutter                          [0.3.79, u@u-Precision-5550, pid:197]
      67. wpctl                           [0.3.79, u@u-Precision-5550, pid:159]

Audio
 ├─ Devices:
 │      40. Built-in Audio                      [alsa]
 │      54. G435 Bluetooth Gaming Headset       [bluez5]
 │
 ├─ Sinks:
 │  *   59. G435 Bluetooth Gaming Headset       [vol: 0.62]
 │      62. Built-in Audio Analog Stereo        [vol: 0.50]
 │
 ├─ Sink endpoints:
 │
 ├─ Sources:
 │  *   47. Built-in Audio Analog Stereo        [vol: 0.10]
 │
 ├─ Source endpoints:
 │
 └─ Streams:

Video
 ├─ Devices:
 │
 ├─ Sinks:
 │
 ├─ Sink endpoints:
 │
 ├─ Sources:
 │
 ├─ Source endpoints:
 │
 └─ Streams:

Settings
 └─ Default Configured Node Names:
         0. Audio/Sink    Headphone_Jack_SA1023_2206153136-00.iec958-stereo
         1. Audio/Source  Headphone_Jack_SA1023_2206153136-00.mono-fallback.2
"""

    status_sorted = """
PipeWire 'pipewire-0' [0.3.79, u@u-Precision-5550, cookie:2611513056]
 └─ Clients:

     GNOME Shell Volume Control      [0.3.79, u@u-Precision-5550
     GNOME Volume Control Media Keys [0.3.79, u@u-Precision-5550
     Mutter                          [0.3.79, u@u-Precision-5550
     Terminal                        [0.3.79, u@u-Precision-5550
     WirePlumber                     [0.3.79, u@u-Precision-5550
     WirePlumber [export]            [0.3.79, u@u-Precision-5550
     gnome-shell                     [0.3.79, u@u-Precision-5550
     pipewire                        [0.3.79, u@u-Precision-5550
     wpctl                           [0.3.79, u@u-Precision-5550
     xdg-desktop-portal              [0.3.79, u@u-Precision-5550
Audio
 ├─ Devices:
 │
 │     Built-in Audio                      [alsa]
 │     G435 Bluetooth Gaming Headset       [bluez5]
 ├─ Sinks:
 │
 │     Built-in Audio Analog Stereo        [vol: 0.50]
 │  *  G435 Bluetooth Gaming Headset       [vol: 0.62]
 ├─ Sink endpoints:
 │
 ├─ Sources:
 │
 │  *  Built-in Audio Analog Stereo        [vol: 0.10]
 ├─ Source endpoints:
 │
 └─ Streams:

Video
 ├─ Devices:
 │
 ├─ Sinks:
 │
 ├─ Sink endpoints:
 │
 ├─ Sources:
 │
 ├─ Source endpoints:
 │
 └─ Streams:

Settings
 └─ Default Configured Node Names:
        Audio/Sink    Headphone_Jack_SA1023_2206153136-00.iec958-stereo
        Audio/Source  Headphone_Jack_SA1023_2206153136-00.mono-fallback.2
"""

    def test_sort(self):
        pt = PipewireTest()
        rv = pt._sort_wpctl_status(self.status.splitlines())
        self.assertEqual(rv, self.status_sorted.splitlines())


class CompareWpctlStatusTests(unittest.TestCase):

    status_sorted = """
PipeWire 'pipewire-0' [0.3.79, u@u-Precision-5550, cookie:2611513056]
 └─ Clients:

     GNOME Shell Volume Control      [0.3.79, u@u-Precision-5550]
     GNOME Volume Control Media Keys [0.3.79, u@u-Precision-5550]
     Mutter                          [0.3.79, u@u-Precision-5550]
     Terminal                        [0.3.79, u@u-Precision-5550]
     WirePlumber                     [0.3.79, u@u-Precision-5550]
     WirePlumber [export]            [0.3.79, u@u-Precision-5550]
     gnome-shell                     [0.3.79, u@u-Precision-5550]
     pipewire                        [0.3.79, u@u-Precision-5550]
     wpctl                           [0.3.79, u@u-Precision-5550]
     xdg-desktop-portal              [0.3.79, u@u-Precision-5550]
Audio
 ├─ Devices:
 │
 │     Built-in Audio                      [alsa]
 │     G435 Bluetooth Gaming Headset       [bluez5]
 ├─ Sinks:
 │
 │     Built-in Audio Analog Stereo        [vol: 0.50]
 │  *  G435 Bluetooth Gaming Headset       [vol: 0.62]
 ├─ Sink endpoints:
 │
 ├─ Sources:
 │
 │  *  Built-in Audio Analog Stereo        [vol: 0.10]
 ├─ Source endpoints:
 │
 └─ Streams:

Video
 ├─ Devices:
 │
 ├─ Sinks:
 │
 ├─ Sink endpoints:
 │
 ├─ Sources:
 │
 ├─ Source endpoints:
 │
 └─ Streams:

Settings
 └─ Default Configured Node Names:
        Audio/Sink    Headphone_Jack_SA1023_2206153136-00.iec958-stereo
        Audio/Source  Headphone_Jack_SA1023_2206153136-00.mono-fallback.2
"""

    status_sorted_not_match = """
PipeWire 'pipewire-0' [0.3.79, u@u-Precision-5550, cookie:2611513056]
 └─ Clients:

     GNOME Shell Volume Control      [0.3.79, u@u-Precision-5550]
     GNOME Volume Control Media Keys [0.3.79, u@u-Precision-5550]
     Mutter                          [0.3.79, u@u-Precision-5550]
     Terminal                        [0.3.79, u@u-Precision-5550]
     WirePlumber                     [0.3.79, u@u-Precision-5550]
     WirePlumber [export]            [0.3.79, u@u-Precision-5550]
     gnome-shell                     [0.3.79, u@u-Precision-5550]
     pipewire                        [0.3.79, u@u-Precision-5550]
     wpctl                           [0.3.79, u@u-Precision-5550]
     zdg-desktop-portal              [0.3.79, u@u-Precision-5550]
Audio
 ├─ Devices:
 │
 │     Built-in Audio                      [alsa]
 │     G435 Bluetooth Gaming Headset       [bluez5]
 ├─ Sinks:
 │
 │     Built-in Audio Analog Stereo        [vol: 0.50]
 │  *  G435 Bluetooth Gaming Headset       [vol: 0.62]
 ├─ Sink endpoints:
 │
 ├─ Sources:
 │
 │  *  Built-in Audio Analog Stereo        [vol: 0.10]
 ├─ Source endpoints:
 │
 └─ Streams:

Video
 ├─ Devices:
 │
 ├─ Sinks:
 │
 ├─ Sink endpoints:
 │
 ├─ Sources:
 │
 ├─ Source endpoints:
 │
 └─ Streams:

Settings
 └─ Default Configured Node Names:
        Audio/Sink    Headphone_Jack_SA1023_2206153136-00.iec958-stereo
        Audio/Source  Headphone_Jack_SA1023_2206153136-00.mono-fallback.2
"""

    status_sorted_list = status_sorted.splitlines()
    status_sorted_not_match_list = status_sorted_not_match.splitlines()

    @patch("builtins.open", read_data=[])
    @patch("pipewire_utils.PipewireTest._sort_wpctl_status")
    def test_match(self, mock_wp_status, mock_open):
        pt = PipewireTest()
        mock_wp_status.side_effect = [self.status_sorted_list,
                                      self.status_sorted_list]
        rv = pt.compare_wpctl_status("s1", "s2")
        self.assertEqual(rv, None)

    @patch("builtins.open", read_data=[])
    @patch("pipewire_utils.PipewireTest._sort_wpctl_status")
    def test_not_match(self, mock_wp_status, mock_open):
        pt = PipewireTest()
        mock_wp_status.side_effect = [self.status_sorted_list,
                                      self.status_sorted_not_match_list]
        with self.assertRaises(SystemExit):
            pt.compare_wpctl_status("s1", "s2")


class ArgsParsingTests(unittest.TestCase):
    def test_success(self):
        pt = PipewireTest()

        # no argument, load default
        args = ["detect"]
        rv = pt._args_parsing(args)
        self.assertEqual(rv.type, "Audio")
        self.assertEqual(rv.clazz, "Sink")

        args = ["select"]
        rv = pt._args_parsing(args)
        self.assertEqual(rv.type, "Audio")
        self.assertEqual(rv.clazz, "Sink")
        self.assertEqual(rv.device, "")

        # set argument
        args = ["detect", "-t", "unit", "-c", "test"]
        rv = pt._args_parsing(args)
        self.assertEqual(rv.type, "unit")
        self.assertEqual(rv.clazz, "test")

        args = ["select", "-t", "unit", "-c", "test", "-d", "device"]
        rv = pt._args_parsing(args)
        self.assertEqual(rv.type, "unit")
        self.assertEqual(rv.clazz, "test")
        self.assertEqual(rv.device, "device")

        args = ["gst", "-t", "30", "-d", "device", "PIPELINE"]
        rv = pt._args_parsing(args)
        self.assertEqual(rv.timeout, 30)
        self.assertEqual(rv.PIPELINE, "PIPELINE")
        self.assertEqual(rv.device, "device")

        args = ["monitor", "-t", "30", "-m", "mode"]
        rv = pt._args_parsing(args)
        self.assertEqual(rv.timeout, 30)
        self.assertEqual(rv.mode, "mode")

        args = ["through", "-c", "echo", "-m", "mode"]
        rv = pt._args_parsing(args)
        self.assertEqual(rv.command, "echo")
        self.assertEqual(rv.mode, "mode")

        args = ["show", "-t", "AUDIO"]
        rv = pt._args_parsing(args)
        self.assertEqual(rv.type, "AUDIO")

        args = ["compare_wpctl_status", "-s1", "s1", "-s2", "s2"]
        rv = pt._args_parsing(args)
        self.assertEqual(rv.status_1, "s1")
        self.assertEqual(rv.status_2, "s2")


class FunctionSelectTests(unittest.TestCase):

    @patch("pipewire_utils.PipewireTest.detect_device", return_value=99)
    def test_detect(self, mock_detect):
        pt = PipewireTest()
        args = ["detect", "-t", "unit", "-c", "test"]
        rv = pt.function_select(pt._args_parsing(args))
        self.assertEqual(rv, 99)

    @patch("pipewire_utils.PipewireTest.select_device", return_value=88)
    def test_select(self, mock_select):
        pt = PipewireTest()
        args = ["select", "-t", "unit", "-c", "test"]
        rv = pt.function_select(pt._args_parsing(args))
        self.assertEqual(rv, 88)

    @patch("pipewire_utils.PipewireTest.gst_pipeline", return_value=77)
    def test_gst(self, mock_gst):
        pt = PipewireTest()
        args = ["gst", "-t", "30", "-d", "device", "PIPELINE"]
        rv = pt.function_select(pt._args_parsing(args))
        self.assertEqual(rv, 77)

    @patch("pipewire_utils.PipewireTest.monitor_active_port_change",
           return_value=66)
    def test_monitor(self, mock_monitor):
        pt = PipewireTest()
        args = ["monitor", "-t", "30", "-m", "mode"]
        rv = pt.function_select(pt._args_parsing(args))
        self.assertEqual(rv, 66)

    @patch("pipewire_utils.PipewireTest.go_through_ports", return_value=55)
    def test_through(self, mock_through):
        pt = PipewireTest()
        args = ["through", "-c", "echo", "-m", "mode"]
        rv = pt.function_select(pt._args_parsing(args))
        self.assertEqual(rv, 55)

    @patch("pipewire_utils.PipewireTest.show_default_device", return_value=44)
    def test_show_default_device(self, mock_show):
        pt = PipewireTest()
        args = ["show", "-t", "AUDIO"]
        rv = pt.function_select(pt._args_parsing(args))
        self.assertEqual(rv, 44)

    @patch("pipewire_utils.PipewireTest.compare_wpctl_status", return_value=0)
    def test_show_current_status(self, mock_status):
        pt = PipewireTest()
        args = ["compare_wpctl_status", "-s1", "s1", "-s2", "s2"]
        rv = pt.function_select(pt._args_parsing(args))
        self.assertEqual(rv, 0)
