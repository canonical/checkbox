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

from __future__ import division, print_function
import argparse
import collections
import json
import logging
import math
import re
import subprocess
import sys
import time

try:
    import gi

    gi.require_version("GLib", "2.0")
    gi.require_version("Gst", "1.0")
    from gi.repository import GObject
    from gi.repository import Gst
    from gi.repository import GLib

    Gst.init(None)  # This has to be done very early so it can find elements
except ImportError:
    print(
        "Can't import module: %s. it may not be available for this"
        "version of Python, which is: " % sys.exc_info()[1],
        file=sys.stderr,
    )
    print((sys.version), file=sys.stderr)
    sys.exit(127)


# Frequency bands for FFT
BINS = 256
# How often to take a sample and do FFT on it.
FFT_INTERVAL = 100000000  # In nanoseconds, so this is every 1/10th second
# Sampling frequency. The effective maximum frequency we can analyze is
# half of this (see Nyquist's theorem)
SAMPLING_FREQUENCY = 44100
# The default test frequency is in the middle of the band that contains 5000Hz
# This frequency was determined experimentally to be high enough but more
# reliable than others we tried.
DEFAULT_TEST_FREQUENCY = 5035
# only sample a signal when peak level is in this range (in dB attenuation,
# 0 means no attenuation (and horrible clipping).
REC_LEVEL_RANGE = (-2.0, -12.0)
# For our test signal to be considered present, it has to be this much higher
# than the base level (minimum magnitude). This is in dB.
MAGNITUDE_THRESHOLD = 2.5
# Volume for the sample tone (in %)
PLAY_VOLUME = 70


class PIDController(object):
    """A Proportional-Integrative-Derivative controller (PID) controls a
    process's output to try to maintain a desired output value (known as
    'setpoint', by continually adjusting the process's input.

    It does so by calculating the "error" (difference between output and
    setpoint) and attempting to minimize it manipulating the input.

    The desired change to the input is calculated based on error and three
    constants (kp, ki and kd).  These values can be interpreted in terms of
    time: P depends on the present error, I on the accumulation of past errors,
    and D is a prediction of future errors, based on current rate of change.
    The weighted sum of these three actions is used to adjust the process via a
    control element.

    In practice, kp, ki and kd are process-dependent and usually have to
    be tweaked by hand, but once reasonable constants are arrived at, they
    can apply to a particular process without further modification.

    """

    def __init__(self, kp, ki, kd, setpoint=0):
        """Creates a PID controller with given constants and setpoint.

        Arguments:
        kp, ki, kd: PID constants, see class description.
        setpoint: desired output value; calls to input_change with
                  a process output reading will return a desired change
                  to the input to attempt matching output to this value.
        """
        self.setpoint = setpoint
        self.kp = kp
        self.ki = ki
        self.kd = kd
        self._integral = 0
        self._previous_error = 0
        self._change_limit = 0

    def input_change(self, process_feedback, dt):
        """Calculates desired input value change.

        Based on process feedback and time interval (dt).
        """
        error = self.setpoint - process_feedback
        self._integral = self._integral + (error * dt)
        derivative = (error - self._previous_error) / dt
        self._previous_error = error
        input_change = (
            (self.kp * error)
            + (self.ki * self._integral)
            + (self.kd * derivative)
        )
        if self._change_limit and abs(input_change) > abs(self._change_limit):
            sign = input_change / abs(input_change)
            input_change = sign * self._change_limit
        return input_change

    def set_change_limit(self, limit):
        """Ensures that input value changes are lower than limit.

        Setting limit of zero disables this.
        """
        self._change_limit = limit


class VolumeController(object):
    pw_types = {"input": "SOURCE", "output": "SINK"}

    def __init__(self, type, logger=None):
        """Initializes the volume controller.

        Arguments:
        type: either input or output

        """
        self.type = type
        self._volume = None
        self.identifier = None
        self.logger = logger

    def set_volume(self, volume):
        if not 0 <= volume <= 100:
            return False
        command = [
            "wpctl",
            "set-volume",
            "@DEFAULT_AUDIO_%s@" % (self.pw_types[self.type]),
            str(int(volume)) + "%",
        ]
        self._wpctl_output(command)
        self._volume = volume
        return True

    def get_volume(self):
        return self._volume

    def mute(self, mute):
        mute = str(int(mute))
        command = [
            "wpctl",
            "set-mute",
            "@DEFAULT_AUDIO_%s@" % (self.pw_types[self.type]),
            mute,
        ]
        self._wpctl_output(command)
        return True

    def _wpctl_output(self, command):
        # This method mainly calls wpctl (hence the name). Since wpctl may
        # return a failure if the audio layer is not yet initialized, we will
        # try running a few times in case of failure. All our invocations of
        # wpctl should be "idempotent" so repeating them should not have
        # any bad effects.
        for attempt in range(0, 3):
            try:
                return subprocess.check_output(
                    command, universal_newlines=True
                )
            except subprocess.CalledProcessError:
                time.sleep(5)
            except FileNotFoundError:
                break
        self.logger.error("Fail to execute: {}".format(command))
        sys.exit(1)


class FileDumper(object):
    def write_to_file(self, filename, data):
        try:
            with open(filename, "w") as f:
                for i in data:
                    print(i, file=f)
            return_value = True
        except (TypeError, IOError) as e:
            logging.error(repr(e))
            return_value = False
        return return_value


class SpectrumAnalyzer(object):
    def __init__(self, points, sampling_frequency=44100, wanted_samples=50):
        self.spectrum = [0] * points
        self.number_of_samples = 0
        self.wanted_samples = wanted_samples
        self.sampling_frequency = sampling_frequency
        # Frequencies should contain *real* frequency which is half of
        # the sampling frequency
        self.frequencies = [
            ((sampling_frequency / 2.0) / points) * i for i in range(points)
        ]

    def _average(self):
        return sum(self.spectrum) / len(self.spectrum)

    def sample(self, sample):
        if len(sample) != len(self.spectrum):
            return
        self.spectrum = [
            ((old * self.number_of_samples) + new)
            / (self.number_of_samples + 1)
            for old, new in zip(self.spectrum, sample)
        ]
        self.number_of_samples += 1

    def frequencies_with_peak_magnitude(self, threshold=1.0):
        # First establish the base level
        per_magnitude_bins = collections.defaultdict(int)
        for magnitude in self.spectrum:
            per_magnitude_bins[magnitude] += 1
        base_level = max(
            per_magnitude_bins, key=lambda x: per_magnitude_bins[x]
        )
        # Now return all values that are higher (more positive)
        # than base_level + threshold
        peaks = []
        for i in range(1, len(self.spectrum) - 1):
            first_index = i - 1
            last_index = i + 1
            if (
                self.spectrum[first_index] < self.spectrum[i]
                and self.spectrum[last_index] < self.spectrum[i]
                and self.spectrum[i] > base_level + threshold
            ):
                peaks.append(i)

        return peaks

    def frequency_band_for(self, frequency):
        """Convenience function to tell me which band
        a frequency is contained in
        """
        # Note that actual frequencies are half of what the sampling
        # frequency would tell us. If SF is 44100 then maximum actual
        # frequency is 22050, and if I have 10 frequency bins each will
        # contain only 2205 Hz, not 4410 Hz.
        max_frequency = self.sampling_frequency / 2
        if frequency > max_frequency or frequency < 0:
            return None
        band = float(frequency) / (max_frequency / len(self.spectrum))
        return int(math.ceil(band)) - 1

    def frequencies_for_band(self, band):
        """Convenience function to tell me the delimiting frequencies
        for a band
        """
        if band >= len(self.spectrum) or band < 0:
            return None
        lower = self.frequencies[band]
        upper = lower + ((self.sampling_frequency / 2.0) / len(self.spectrum))
        return (lower, upper)

    def sampling_complete(self):
        return self.number_of_samples >= self.wanted_samples


class GStreamerMessageHandler(object):
    def __init__(
        self,
        rec_level_range,
        logger,
        volumecontroller,
        pidcontroller,
        spectrum_analyzer,
    ):
        """Initializes the message handler. It knows how to handle
        spectrum and level gstreamer messages.

        Arguments:
        rec_level_range: tuple with acceptable recording level
                         ranges
        logger: logging object with debug, info, error methods.
        volumecontroller: an instance of VolumeController to use
                          to adjust RECORDING level
        pidcontroller: a PID controller instance which helps control
                       volume
        spectrum_analyzer: instance of SpectrumAnalyzer to collect
                           data from spectrum messages

        """
        self.current_level = sys.maxsize
        self.logger = logger
        self.pid_controller = pidcontroller
        self.rec_level_range = rec_level_range
        self.spectrum_analyzer = spectrum_analyzer
        self.volume_controller = volumecontroller

    def set_quit_method(self, method):
        """Method that will be called when sampling is complete."""
        self._quit_method = method

    def bus_message_handler(self, bus, message):
        if message.type == Gst.MessageType.ELEMENT:
            message_name = message.get_structure().get_name()
            if message_name == "spectrum":
                # TODO: Due to an upstream bug, a structure's get_value method
                # doesn't work if the value in question is an array (as is the
                # case with the magnitudes).
                # https://bugzilla.gnome.org/show_bug.cgi?id=693168
                # We have to resort to parsing the string representation of the
                # structure. It's an ugly hack but it works.
                # Ideally we'd be able to say this to get fft_magnitudes:
                # message.get_structure.get_value('magnitude').
                # If an upstream fix ever makes it into gstreamer,
                # remember to remove this hack and the parse_spectrum method
                struct_string = message.get_structure().to_string()
                structure = parse_spectrum_message_structure(struct_string)
                fft_magnitudes = structure["magnitude"]
                self.spectrum_method(self.spectrum_analyzer, fft_magnitudes)

            if message_name == "level":
                # peak_value is our process feedback
                # It's returned as an array, so I need the first (and only)
                # element
                peak_value = message.get_structure().get_value("peak")[0]
                self.level_method(
                    peak_value, self.pid_controller, self.volume_controller
                )

    # Adjust recording level
    def level_method(self, level, pid_controller, volume_controller):
        # If volume controller doesn't return a valid volume,
        # we can't control it :(
        current_volume = volume_controller.get_volume()
        if current_volume is None:
            self.logger.error(
                "Unable to control recording volume. "
                "Test results may be wrong"
            )
            return
        self.current_level = level
        change = pid_controller.input_change(level, 0.10)
        if self.logger:
            self.logger.debug(
                "Peak level: %(peak_level).2f, "
                "volume: %(volume)d%%, Volume change: %(change)f%%"
                % {
                    "peak_level": level,
                    "change": change,
                    "volume": current_volume,
                }
            )
        volume_controller.set_volume(current_volume + change)

    # Only sample if level is within the threshold
    def spectrum_method(self, analyzer, spectrum):
        if (
            self.rec_level_range[1] <= self.current_level
            or self.current_level <= self.rec_level_range[0]
        ):
            self.logger.debug(
                "Sampling, recorded %d samples" % analyzer.number_of_samples
            )
            analyzer.sample(spectrum)
        if analyzer.sampling_complete() and self._quit_method:
            self.logger.info("Sampling complete, ending process")
            self._quit_method()


class GstAudioObject(object):
    def __init__(self):
        self.class_name = self.__class__.__name__

    def _set_state(self, state, description):
        self.pipeline.set_state(state)
        message = "%s: %s" % (self.class_name, description)
        if self.logger:
            self.logger.info(message)

    def start(self):
        self._set_state(Gst.State.PLAYING, "Starting")

    def stop(self):
        self._set_state(Gst.State.NULL, "Stopping")


class Player(GstAudioObject):
    def __init__(self, frequency=DEFAULT_TEST_FREQUENCY, logger=None):
        super(Player, self).__init__()
        self.pipeline_description = (
            "audiotestsrc wave=sine freq=%s "
            "! audioconvert "
            "! audioresample "
            "! autoaudiosink" % int(frequency)
        )
        self.logger = logger
        if self.logger:
            self.logger.debug(self.pipeline_description)
        self.pipeline = Gst.parse_launch(self.pipeline_description)


class Recorder(GstAudioObject):
    def __init__(
        self,
        output_file,
        bins=BINS,
        sampling_frequency=SAMPLING_FREQUENCY,
        fft_interval=FFT_INTERVAL,
        logger=None,
    ):
        super(Recorder, self).__init__()
        pipeline_description = """autoaudiosrc
        ! queue
        ! level message=true
        ! audioconvert
        ! audio/x-raw, channels=1, rate=(int)%(rate)s
        ! audioresample
        ! spectrum interval=%(fft_interval)s bands = %(bands)s
        ! wavenc
        ! filesink location=%(file)s""" % {
            "bands": bins,
            "rate": sampling_frequency,
            "fft_interval": fft_interval,
            "file": output_file,
        }
        self.logger = logger
        if self.logger:
            self.logger.debug(pipeline_description)
        self.pipeline = Gst.parse_launch(pipeline_description)

    def register_message_handler(self, handler_method):
        if self.logger:
            message = "Registering message handler: %s" % handler_method
            self.logger.debug(message)
        self.bus = self.pipeline.get_bus()
        self.bus.add_signal_watch()
        self.bus.connect("message", handler_method)


def parse_spectrum_message_structure(struct_string):
    # First let's jsonize this
    # This is the message name, which we don't need
    text = struct_string.replace("spectrum, ", "")
    # name/value separator in json is : and not =
    text = text.replace("=", ": ")
    # Mutate the {} array notation from the structure to
    # [] notation for json.
    text = text.replace("{", "[")
    text = text.replace("}", "]")
    # Remove a few stray semicolons that aren't needed
    text = text.replace(";", "")
    # Remove the data type fields, as json doesn't need them
    text = re.sub(r"\(.+?\)", "", text)
    # double-quote the identifiers
    text = re.sub(r"([\w-]+):", r'"\1":', text)
    # Wrap the whole thing in brackets
    text = "{" + text + "}"
    # Try to parse and return something sensible here, even if
    # the data was unparsable.
    try:
        return json.loads(text)
    except ValueError as e:
        logging.error(repr(e))
        return None


def process_arguments(args=sys.argv[1:]):
    description = """
        Plays a single frequency through the default output, then records on
        the default input device. Analyzes the recorded signal to test for
        presence of the played frequency, if present it exits with success.
    """
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument(
        "-t",
        "--time",
        dest="test_duration",
        action="store",
        default=30,
        type=int,
        help="""Maximum test duration, default %(default)s seconds.
                    It may exit sooner if it determines it has enough data.""",
    )
    parser.add_argument(
        "-a",
        "--audio",
        action="store",
        default="/dev/null",
        type=str,
        help="File to save recorded audio in .wav format",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        default=False,
        help="Be quiet, no output unless there's an error.",
    )
    parser.add_argument(
        "-d",
        "--debug",
        action="store_true",
        default=False,
        help="Debugging output",
    )
    parser.add_argument(
        "-f",
        "--frequency",
        action="store",
        default=DEFAULT_TEST_FREQUENCY,
        type=int,
        help="Frequency for test signal, default %(default)s Hz",
    )
    parser.add_argument(
        "-u",
        "--spectrum",
        action="store",
        type=str,
        help="""File to save spectrum information for plotting
                    (one frequency/magnitude pair per line)""",
    )
    return parser.parse_args(args)


def run_test(args):

    # Setup logging
    level = logging.INFO
    if args.debug:
        level = logging.DEBUG
    if args.quiet:
        level = logging.ERROR
    logging.basicConfig(level=level)
    try:
        # Launches recording pipeline. I need to hook up into the gst
        # messages.
        recorder = Recorder(output_file=args.audio, logger=logging)
        # Just launches the playing pipeline
        player = Player(frequency=args.frequency, logger=logging)
    except GObject.GError as excp:
        logging.critical("Unable to initialize GStreamer pipelines: %s", excp)
        sys.exit(127)

    # This just receives a process feedback and tells me how much to change to
    # achieve the setpoint
    pidctrl = PIDController(
        kp=0.7, ki=0.01, kd=0.01, setpoint=REC_LEVEL_RANGE[0]
    )
    pidctrl.set_change_limit(5)
    # This  gathers spectrum data.
    analyzer = SpectrumAnalyzer(
        points=BINS, sampling_frequency=SAMPLING_FREQUENCY
    )

    recorder.volumecontroller = VolumeController(type="input", logger=logging)
    recorder.volumecontroller.set_volume(0)
    recorder.volumecontroller.mute(False)

    player.volumecontroller = VolumeController(type="output", logger=logging)
    player.volumecontroller.set_volume(PLAY_VOLUME)
    player.volumecontroller.mute(False)

    # This handles the messages from gstreamer and orchestrates
    # the passed volume controllers, pid controller and spectrum analyzer
    # accordingly.
    gmh = GStreamerMessageHandler(
        rec_level_range=REC_LEVEL_RANGE,
        logger=logging,
        volumecontroller=recorder.volumecontroller,
        pidcontroller=pidctrl,
        spectrum_analyzer=analyzer,
    )

    # I need to tell the recorder which method will handle messages.
    recorder.register_message_handler(gmh.bus_message_handler)

    # Create the loop and add a few triggers
    loop = GLib.MainLoop()
    GLib.timeout_add_seconds(0, player.start)
    GLib.timeout_add_seconds(0, recorder.start)
    GLib.timeout_add_seconds(args.test_duration, loop.quit)

    # Tell the gmh which method to call when enough samples are collected
    gmh.set_quit_method(loop.quit)

    loop.run()

    # When the loop ends, set things back to reasonable states
    player.stop()
    recorder.stop()
    player.volumecontroller.set_volume(50)
    recorder.volumecontroller.set_volume(10)

    # See if data gathering was successful.
    test_band = analyzer.frequency_band_for(args.frequency)
    candidate_bands = analyzer.frequencies_with_peak_magnitude(
        MAGNITUDE_THRESHOLD
    )
    for band in candidate_bands:
        logging.debug(
            "Band (%.2f,%.2f) contains a magnitude peak"
            % analyzer.frequencies_for_band(band)
        )
    if test_band in candidate_bands:
        freqs_for_band = analyzer.frequencies_for_band(test_band)
        logging.info(
            "PASS: Test frequency of %s in band (%.2f, %.2f) "
            "which contains a magnitude peak"
            % ((args.frequency,) + freqs_for_band)
        )
        return_value = 0
    else:
        logging.info(
            "FAIL: Test frequency of %s is not in one of the "
            "bands with magnitude peaks" % args.frequency
        )
        return_value = 1
    # Is the microphone broken?
    if len(set(analyzer.spectrum)) <= 1:
        logging.info(
            "WARNING: Microphone seems broken, didn't even "
            "record ambient noise"
        )

    if args.spectrum:
        logging.info("Saving spectrum data for plotting as %s" % args.spectrum)
        if not FileDumper().write_to_file(
            args.spectrum,
            [
                "%s,%s" % t
                for t in zip(analyzer.frequencies, analyzer.spectrum)
            ],
        ):
            logging.error(
                "Couldn't save spectrum data for plotting", file=sys.stderr
            )

    return return_value


def main():
    # Get arguments.
    args = process_arguments()

    return run_test(args)


if __name__ == "__main__":
    sys.exit(main())
