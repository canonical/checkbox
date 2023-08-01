#!/usr/bin/env python3
#
# This file is part of Checkbox.
#
# Copyright 2023 Canonical Ltd.
#    Authors: Dio He <dio.he@canonical.com>
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

from collections import namedtuple


def get_audio_cards():
    """Retrieve audio card information."""
    AudioCard = namedtuple('AudioCard',
                           ['card', 'device', 'name', 'playback', 'capture'])
    audio_cards = []
    PCM_FILE = '/proc/asound/pcm'
    try:
        with open(PCM_FILE, 'r') as f:
            data = f.readlines()
    except OSError:
        print('Failed to access {}'.format(PCM_FILE))
        return []

    for line in data:
        info = [device_line.strip() for device_line in line.split(':')]
        ids = info[0].split('-')
        card_id = ids[0]
        device_id = ids[1]
        device_name = info[1]
        capabilities = info[3:]
        playback = ("supported" if has_capability('playback', capabilities)
                    else "unsupported")
        capture = ("supported" if has_capability('capture', capabilities)
                   else "unsupported")
        audio_cards.append(AudioCard(card=card_id,
                                     device=device_id,
                                     name=device_name,
                                     playback=playback,
                                     capture=capture))

    return audio_cards


def has_capability(capability_prefix: str, capabilities: list) -> bool:
    return any(capability.startswith(capability_prefix)
               for capability in capabilities)


def print_audio_cards(cards):
    """Print audio card information."""
    for card in cards:
        print("Card: {}".format(card.card))
        print("Device: {}".format(card.device))
        print("Name: {}".format(card.name))
        if card.playback == "supported":
            print("Playback: 1")
        if card.capture == "supported":
            print("Capture: 1")


def main():
    cards = get_audio_cards()

    if cards:
        print_audio_cards(cards)


if __name__ == "__main__":
    main()
