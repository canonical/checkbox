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

import unittest
from io import StringIO
from unittest.mock import Mock, patch, mock_open
from audio_card_resource import get_audio_cards


class GetAudioCardsTests(unittest.TestCase):
    def test_get_audio_card_info(self):
        with patch("os.path.exists") as mock_path:
            mock_path.return_value = True
            test_input = "00-00: HDA Analog (*) : : playback 1\n00-01: HDA Digital (*) : : capture 1s"
            expected_audio_card1 = {
                "card": "00",
                "device": "00",
                "name": "HDA Analog (*)",
                "playback": True,
                "capture": False,
            }
            expected_audio_card2 = {
                "card": "00",
                "device": "01",
                "name": "HDA Digital (*)",
                "playback": False,
                "capture": True,
            }
            with patch("builtins.open", new=mock_open(read_data=test_input)):
                audio_cards = get_audio_cards()
                self.assertEqual(audio_cards[0], expected_audio_card1)
                self.assertEqual(audio_cards[1], expected_audio_card2)
