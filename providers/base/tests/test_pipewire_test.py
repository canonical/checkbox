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

import unittest
import sys
from unittest.mock import MagicMock
from unittest.mock import Mock, patch, mock_open, call
try:
    sys.modules["gi"] = MagicMock()
    sys.modules["gi.repository"] = MagicMock()
    from pipewire_test import *
except ImportError:
    sys.exit(127)


def sorting(item):
    # use to sort JSON object
    if isinstance(item, dict):
        return sorted((key, sorting(values)) for key, values in item.items())
    if isinstance(item, list):
        return sorted(sorting(x) for x in item)
    else:
        return item


class PIDControllerTests(unittest.TestCase):

    def test_input_change(self):
        pc = PIDController(kp=0.7, ki=.01, kd=0.01,
                           setpoint=REC_LEVEL_RANGE[0])
        self.assertEqual(0.7, pc.kp)
        self.assertEqual(0.01, pc.ki)
        self.assertEqual(0.01, pc.kd)
        self.assertEqual(0, pc._integral)
        self.assertEqual(0, pc._previous_error)
        self.assertEqual(0, pc._change_limit)
        self.assertAlmostEqual(-2.403, pc.input_change(1, 0.10))

    def test_set_change_limit(self):
        pc = PIDController(kp=0.7, ki=.01, kd=0.01,
                           setpoint=REC_LEVEL_RANGE[0])
        pc.set_change_limit(0.5)
        self.assertEqual(0.5, pc._change_limit)
        self.assertAlmostEqual(-0.5, pc.input_change(1, 0.10))


class VolumeControllerTests(unittest.TestCase):

    def test_set_volume(self):
        vc = VolumeController(type='input', logger=None)
        self.assertEqual('input', vc.type)
        self.assertEqual(None, vc._volume)
        self.assertEqual(None, vc.identifier)
        self.assertEqual(None, vc.logger)

    @patch("pipewire_test.VolumeController._wpctl_output")
    def test_set_get_mute_volume(self, mock_wpctl):
        vc = VolumeController(type='input', logger=None)

        # over range
        self.assertEqual(False, vc.set_volume(101))
        self.assertEqual(False, vc.set_volume(-1))

        mock_wpctl.return_value = None

        # set correctly
        self.assertEqual(True, vc.set_volume(5))
        self.assertEqual(5, vc._volume)

        # get correctly
        self.assertEqual(5, vc.get_volume())

        # mute
        self.assertEqual(True, vc.mute(True))
        self.assertEqual(True, vc.mute(False))

    @patch("subprocess.check_output")
    def test_wpctl_output_succ(self, mock_checkout):
        vc = VolumeController(type='input', logger=None)
        mock_checkout.return_value = None
        vc.set_volume(5)
        mock_checkout.assert_called_with(['wpctl',
                                          'set-volume',
                                          '@DEFAULT_AUDIO_SOURCE@',
                                          '5%'],
                                         universal_newlines=True)
        vc.mute(True)
        mock_checkout.assert_called_with(['wpctl',
                                          'set-mute',
                                          '@DEFAULT_AUDIO_SOURCE@',
                                          '1'],
                                         universal_newlines=True)

    @patch("subprocess.check_output")
    def test_wpctl_output_fail(self, mock_checkout):
        vc = VolumeController(type='input', logger=MagicMock())
        mock_checkout.side_effect = subprocess.CalledProcessError(2, "echo")
        with self.assertRaises(SystemExit) as cm:
            vc.set_volume(5)
        self.assertEqual(cm.exception.code, 1)

        mock_checkout.side_effect = FileNotFoundError
        with self.assertRaises(SystemExit) as cm:
            vc.set_volume(5)
        self.assertEqual(cm.exception.code, 1)


class FileDumperTests(unittest.TestCase):

    def test_write_to_file(self):
        open_mock = mock_open()
        with patch("pipewire_test.open",
                   open_mock, create=True):
            self.assertEqual(True,
                             FileDumper().write_to_file("test.txt",
                                                        "test-data"))
            open_mock.assert_called_with("test.txt", "w")
            open_mock.return_value.write.assert_has_calls([call("t"),
                                                           call("\n"),
                                                           call("e"),
                                                           call("\n"),
                                                           call("s"),
                                                           call("\n"),
                                                           call("t"),
                                                           call("\n"),
                                                           call("-"),
                                                           call("\n"),
                                                           call("d"),
                                                           call("\n"),
                                                           call("a"),
                                                           call("\n"),
                                                           call("t"),
                                                           call("\n"),
                                                           call("a"),
                                                           call("\n")])

    def test_write_to_file_except(self):
        open_mock = mock_open()
        with patch("pipewire_test.open",
                   open_mock, create=True):
            open_mock.side_effect = TypeError
            self.assertEqual(False,
                             FileDumper().write_to_file("test.txt",
                                                        "test-data"))
            open_mock.side_effect = IOError
            self.assertEqual(False,
                             FileDumper().write_to_file("test.txt",
                                                        "test-data"))


class SpectrumAnalyzerTests(unittest.TestCase):

    def test_init(self):
        sa = SpectrumAnalyzer(points=256)
        self.assertEqual([0] * 256, sa.spectrum)
        self.assertEqual(0, sa.number_of_samples)
        self.assertEqual(50, sa.wanted_samples)
        self.assertEqual(44100, sa.sampling_frequency)
        self.assertEqual([((44100 / 2.0) / 256) * i
                          for i in range(256)], sa.frequencies)

    def test_average(self):
        sa = SpectrumAnalyzer(points=256)
        self.assertEqual(0, sa._average())

    def test_sample(self):
        sa = SpectrumAnalyzer(points=256)
        sa.sample(sa.spectrum)
        self.assertEqual([0] * 256, sa.spectrum)
        self.assertEqual(1, sa.number_of_samples)

        # data type error
        self.assertEqual(None, sa.sample(""))

    def test_frequencies_with_peak_magnitude(self):
        sa = SpectrumAnalyzer(points=256)
        self.assertEqual([], sa.frequencies_with_peak_magnitude())

    def test_frequency_band_for(self):
        sa = SpectrumAnalyzer(points=256)
        self.assertEqual(2, sa.frequency_band_for(220))

        # frequency > max_frequency
        self.assertEqual(None, sa.frequency_band_for(22000000))

        # frequency < 0
        self.assertEqual(None, sa.frequency_band_for(-1))

    def test_frequencies_for_band(self):
        sa = SpectrumAnalyzer(points=256)
        self.assertEqual((18949.21875, 19035.3515625),
                         sa.frequencies_for_band(220))

        # band >= len(self.spectrum)
        self.assertEqual(None, sa.frequencies_for_band(280))

        # band < 0
        self.assertEqual(None, sa.frequencies_for_band(-1))

    def test_sampling_complete(self):

        # true
        sa = SpectrumAnalyzer(points=256, wanted_samples=0)
        self.assertEqual(True, sa.sampling_complete())

        # false
        sa = SpectrumAnalyzer(points=256)
        self.assertEqual(False, sa.sampling_complete())


class GStreamerMessageHandlerTests(unittest.TestCase):
    analyzer = SpectrumAnalyzer(points=256)
    vc = VolumeController(type='input', logger=MagicMock())
    pc = PIDController(kp=0.7, ki=.01, kd=0.01,
                       setpoint=REC_LEVEL_RANGE[0])
    gmh = GStreamerMessageHandler(rec_level_range=REC_LEVEL_RANGE,
                                  logger=MagicMock(),
                                  volumecontroller=vc,
                                  pidcontroller=pc,
                                  spectrum_analyzer=analyzer)

    def test_bus_message_handler_type_error(self):
        struct = Gst.Structure().new_from_string("test")
        message = Gst.Message().new_element(None, struct)
        bus = Gst.Bus()
        self.gmh.bus_message_handler(bus, message)
        self.assertEqual(0, self.analyzer.number_of_samples)
        self.assertEqual(None, self.vc._volume)

    def test_bus_message_handler_name_error(self):
        struct = Gst.Structure().new_from_string("test")
        message = Gst.Message().new_element(None, struct)
        message.type = Gst.MessageType.ELEMENT
        bus = Gst.Bus()
        self.gmh.bus_message_handler(bus, message)
        self.assertEqual(0, self.analyzer.number_of_samples)
        self.assertEqual(None, self.vc._volume)

    def test_level_method_none(self):
        self.gmh.level_method(1, self.pc, self.vc)
        self.assertEqual(None, self.vc._volume)

    @patch("pipewire_test.VolumeController._wpctl_output")
    def test_level_method_zore(self, mock_wpctl):
        self.vc.set_volume(0)
        self.gmh.level_method(1, self.pc, self.vc)
        self.assertEqual(0, self.vc._volume)

    def test_spectrum_method(self):
        self.gmh.spectrum_method(self.analyzer, [-0, -10])
        self.assertEqual(0, self.analyzer.number_of_samples)

    @patch("pipewire_test.parse_spectrum_message_structure")
    def test_bus_message_handler_spectrum(self, mock_parse_spectrum_message):
        self_mock = MagicMock()

        message_mock = MagicMock()
        message_mock.type = Gst.MessageType.ELEMENT
        message_mock.get_structure().get_name.return_value = "spectrum"

        mock_parse_spectrum_message.return_value = {
            "magnitude": 1
        }

        GStreamerMessageHandler.bus_message_handler(self_mock,
                                                    MagicMock(),
                                                    message_mock)

        self.assertTrue(self_mock.spectrum_method.called)

    def test_bus_message_handler_level(self):
        self_mock = MagicMock()

        message_mock = MagicMock()
        message_mock.type = Gst.MessageType.ELEMENT
        message_mock.get_structure().get_name.return_value = "level"
        message_mock.get_structure().get_value.return_value = [0]

        GStreamerMessageHandler.bus_message_handler(self_mock,
                                                    MagicMock(),
                                                    message_mock)

        self.assertTrue(self_mock.level_method.called)


class GstAudioObjectTests(unittest.TestCase):

    def test_init(self):
        gao = GstAudioObject()
        self.assertEqual("GstAudioObject", gao.class_name)


class ParseSpectrumMessageStructureTests(unittest.TestCase):
    ss = "spectrum, endtime=(guint64)5000000000,"\
         " timestamp=(guint64)4900000000,"\
         " stream-time=(guint64)4900000000,"\
         " running-time=(guint64)4900000000,"\
         " duration=(guint64)100000000,"\
         " magnitude=(float){ -60, -60 };"
    ans = '{"endtime": 5000000000, "timestamp": 4900000000,'\
          ' "stream-time": 4900000000, "running-time": 4900000000,'\
          ' "duration": 100000000, "magnitude": [-60, -60]}'

    def test_succ(self):
        json_string = parse_spectrum_message_structure(self.ss)
        self.assertEqual(sorting(json.loads(self.ans)),
                         sorting(json_string))

    def test_non_josn(self):
        self.assertEqual(None, parse_spectrum_message_structure("test"))


class ProcessArgumentsTests(unittest.TestCase):

    args = [
            "-t", "10",
            "-a", "audio",
            "-f", "8",
            "-u", "u"
           ]

    def test_succ(self):
        rv = process_arguments(self.args)
        self.assertEqual(rv.test_duration, 10)
        self.assertEqual(rv.audio, "audio")
        self.assertEqual(rv.quiet, False)
        self.assertEqual(rv.debug, False)
        self.assertEqual(rv.frequency, 8)
        self.assertEqual(rv.spectrum, "u")


class RunTestTests(unittest.TestCase):

    @patch("pipewire_test.VolumeController._wpctl_output")
    def test_succ(self, mock_wpctl):
        self.assertEqual(1, run_test(process_arguments([])))

    @patch("pipewire_test.SpectrumAnalyzer.frequencies_for_band")
    @patch("pipewire_test.SpectrumAnalyzer.frequencies_with_peak_magnitude")
    @patch("pipewire_test.SpectrumAnalyzer.frequency_band_for")
    @patch("pipewire_test.VolumeController._wpctl_output")
    def test_with_bands(self, mock_wpctl, mock_band, mock_peak, mock_rb):
        mock_rb.return_value = (1, 2)
        mock_band.return_value = 5035
        mock_peak.return_value = [5035]
        self.assertEqual(0, run_test(process_arguments(["--debug"])))

    @patch("pipewire_test.VolumeController._wpctl_output")
    def test_with_spectrum(self, mock_wpctl):
        self.assertEqual(1,
                         run_test(process_arguments(["-u", "8", "--quiet"])))
