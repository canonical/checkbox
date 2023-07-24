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

import os


def get_audio_cards():
    """Retrieve audio card information."""
    audio_cards = []
    PCM_FILE = '/proc/asound/pcm'
    if os.path.exists(PCM_FILE):
        with open(PCM_FILE, 'r') as f:
            data = f.read()
            for line in data:
                info = [device_line.strip() for device_line in line.split(':')]
                ids = info[0].split('-')
                card_id = ids[0]
                device_id = ids[1]
                device_name = info[1]
                capabilities = info[3:]
                audio_cards.append({
                    'Card': card_id,
                    'Device': device_id,
                    'Name': device_name,
                    'Playback': ("supported" if any(cap.startswith('playback')
                                 for cap in capabilities) else "unsupported"),
                    'Capture': ("supported" if any(cap.startswith('capture')
                                for cap in capabilities) else "unsupported")

                })
    return audio_cards


def print_audio_cards(cards):
    """Print audio card information."""
    for card in cards:
        print(f"card: {card['Card']}")
        print(f"device: {card['Device']}")
        print(f"name: {card['Name']}")
        if card['Playback']:
            print("playback: 1")
        if card['Capture']:
            print("capture: 1")


def main():
    cards = get_audio_cards()

    if cards:
        print_audio_cards(cards)


if __name__ == "__main__":
    main()
