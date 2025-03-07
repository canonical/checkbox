#!/usr/bin/env python3

import unittest
from unittest.mock import patch
import mouse_keyboard


class TestMouse(unittest.TestCase):
    def test_main_successful(self):
        mouse_keyboard.main()

    @patch("mouse_keyboard.rand_mouse_moves", side_effect=Exception())
    def test_main_failure(self):
        mouse_keyboard.main()
