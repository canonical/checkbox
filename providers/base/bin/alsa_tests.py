#!/usr/bin/env python3
# Copyright 2016 Canonical Ltd.
# All rights reserved.
#
# Written by:
#    Authors: Maciej Kisielewski <maciej.kisielewski@canonical.com>


import alsaaudio
import argparse
import cmath
import contextlib
import math
import os
import struct
import sys
import threading

RATE = 44100
PERIOD = 441  # chunk size (in samples) that will be used when talking to alsa


def fft(x):
    N = len(x)
    if N <= 1:
        return x
    even = fft(x[0::2])
    odd = fft(x[1::2])
    T = [cmath.exp(-2j*cmath.pi*k/N) * odd[k] for k in range(N//2)]
    return ([even[k] + T[k] for k in range(N//2)] +
            [even[k] - T[k] for k in range(N//2)])


def sine(freq, length, period_len, amplitude=0.5):
    """
    Generate `period_len` samples of sine of `freq` frequency and `amplitude`.
    It generates at least `length` samples, totalling at next multiple of
    period_len. E.g. sine(440, 15, 10) will generate two 10-item lists of
    samples. Returns list of floats in the range of [-1.0 .. 1.0].
    """
    t = 0
    while t < length:
        sample = []
        for i in range(period_len):
            sample.append(
                amplitude * math.sin(2 * math.pi * ((t + i) / (RATE / freq))))
        yield sample
        t += period_len


class Player:
    def __init__(self, device=None):
        if not device:
            available_pcms = alsaaudio.pcms(alsaaudio.PCM_PLAYBACK)
            if not available_pcms:
                raise SystemExit('No PCMs detected')
            self.pcm = alsaaudio.PCM(device=available_pcms[0])
        else:
            self.pcm = alsaaudio.PCM(device=device)
        self.pcm.setchannels(1)
        self.pcm.setformat(alsaaudio.PCM_FORMAT_FLOAT_LE)
        self.pcm.setperiodsize(PERIOD)

    def play(self, chunk):
        assert(len(chunk) == PERIOD)
        # alsa expects bytes, so we need to repack the list of floats into a
        # bytes sequence
        buff = b''.join([struct.pack("<f", x) for x in chunk])
        self.pcm.write(buff)

    @contextlib.contextmanager
    def changed_volume(self):
        """Change volume to 50% and unmute the output while in the context"""
        available_mixers = alsaaudio.mixers()
        if not available_mixers:
            # no mixers available - silently ignore change_volume request
            yield
            return
        try:
            # get default mixer - this may fail on some systems
            mixer = alsaaudio.Mixer()
        except alsaaudio.ALSAAudioError:
            # pick the first mixer available
            mixer = alsaaudio.Mixer(available_mixers[0])
        stored_mute = mixer.getmute()
        stored_volume = mixer.getvolume()
        mixer.setmute(0)
        mixer.setvolume(50)
        yield
        # the getters returned lists of volumes/mutes per channel, setters
        # require scalars so we need to set it one by one
        for ch, mute in enumerate(stored_mute):
            mixer.setmute(mute, ch)
        for ch, vol in enumerate(stored_volume):
            mixer.setvolume(vol, ch)


class Recorder:
    def __init__(self):
        self.pcm = alsaaudio.PCM(alsaaudio.PCM_CAPTURE)
        self.pcm.setchannels(1)
        self.pcm.setformat(alsaaudio.PCM_FORMAT_FLOAT_LE)
        self.pcm.setperiodsize(PERIOD)

    def record(self, length):
        samples = []
        while len(samples) < length:
            raw = self.pcm.read()
            samples += [x[0] for x in struct.iter_unpack("<f", raw[1])]

        return samples


def playback_test(seconds, device):
    player = Player(device)
    with player.changed_volume():
        for chunk in sine(440, seconds * RATE, PERIOD):
            player.play(chunk)


def loopback_test(seconds, device, freq=455.5):
    def generator():
        player = Player(device)
        with player.changed_volume():
            for chunk in sine(freq, seconds * RATE, PERIOD):
                player.play(chunk)

    plr_thread = threading.Thread(target=generator)
    plr_thread.daemon = True
    plr_thread.start()

    rec = Recorder()
    samples = rec.record(seconds * RATE)

    # fft requires len(samples) to be a  power of 2.
    # let's trim samples to match that
    real_len = 2 ** math.floor(math.floor(math.log2(len(samples))))
    real_seconds = seconds * (real_len / len(samples))
    samples = samples[0:real_len]

    Y = fft(samples)
    freqs = [abs(y) for y in Y[:int(RATE/2)]]
    dominant = freqs.index(max(freqs)) / real_seconds
    print("Dominant frequency is {}, expected {}".format(dominant, freq))

    epsilon = 1.0
    if abs(dominant - freq) < epsilon:
        return 0
    else:
        return 1


def main():
    actions = {
        'playback': playback_test,
        'loopback': loopback_test,
    }
    parser = argparse.ArgumentParser(description='Sound testing using ALSA')
    parser.add_argument('action', metavar='ACTION', choices=actions.keys())
    parser.add_argument('--duration', type=int, default=5)
    parser.add_argument('--device', type=str)
    args = parser.parse_args()
    if args.device:
        device = args.device
    elif 'ALSADEVICE' in os.environ:
        device = os.environ['ALSADEVICE']
    else:
        device = None
    return(actions[args.action](args.duration, device))


if __name__ == '__main__':
    sys.exit(main())
