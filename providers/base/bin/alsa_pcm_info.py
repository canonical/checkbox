#!/usr/bin/env python3
# Copyright 2015 Canonical Ltd.
# All rights reserved.
#
# Written by:
#    Authors: Jonathan Cave <jonathan.cave@canonical.com>

"""
Script to print some simple information from the /proc/asound/pcm file. Used
in lieu of working alsa-utils.
"""

import os

PCM_FILE = '/proc/asound/pcm'

if os.path.exists(PCM_FILE):
    with open(PCM_FILE, 'r') as f:
        for line in f:
            t = [device_line.strip() for device_line in line.split(':')]
            # 0 = Card and device id
            ids = t[0].split('-')
            print("Card: {}".format(ids[0]))
            print("Device: {}".format(ids[1]))
            # 1 = Name of device
            print("Name: {}".format(t[1]))
            # 2 = Name of device again ?!
            # 3+ = Some number of capabilties
            for cap in t[3:]:
                if cap.startswith('playback'):
                    print("Playback: 1")
                if cap.startswith('capture'):
                    print("Capture: 1")
            print()
