#!/usr/bin/env python3

import unittest
from unittest.mock import patch, MagicMock
import sys
sys.modules["evdev"] = MagicMock()
from mouse_keyboard import *


class TestMouse(unittest.TestCase):
    def test_main_successful(self):
        main()

    @patch("mouse_keyboard.rand_mouse_moves", side_effect=Exception())
    def test_main_failure(self, mock_mouse):
        main()
