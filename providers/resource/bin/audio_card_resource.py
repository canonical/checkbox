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


def get_audio_cards():
    """Retrieve audio card information."""
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
        playback = has_capability('playback', capabilities)
        capture = has_capability('capture', capabilities)
        audio_cards.append({
                            'card': card_id,
                            'device': device_id,
                            'name': device_name,
                            'playback': playback,
                            'capture': capture
                        })

    return audio_cards


def has_capability(capability_prefix: str, capabilities: list) -> bool:
    return any(capability.startswith(capability_prefix)
               for capability in capabilities)


def print_audio_cards(cards):
    """Print audio card information."""
    for card in cards:
        print("card: {}".format(card["card"]))
        print("device: {}".format(card["device"]))
        print("name: {}".format(card["name"]))
        if card["playback"]:
            print("playback: supported")
        else:
            print("playback: unsupported")
        if card["capture"]:
            print("capture: supported")
        else:
            print("capture: unsupported")
        print()


def main():
    cards = get_audio_cards()

    if cards:
        print_audio_cards(cards)


if __name__ == "__main__":
    main()
