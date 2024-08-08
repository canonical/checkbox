"""This module provides test cases for the desktop_session module."""

import os
import unittest
from unittest.mock import call, patch

import desktop_session


class DesktopSessionTests(unittest.TestCase):
    """Tests for the desktop_session module."""

    @patch("builtins.print")
    def test_resources_server(self, mock_print):
        """Test the result faking a server session."""

        server_session = {
            "XDG_SESSION_TYPE": "tty",
        }
        with patch.dict(os.environ, server_session, clear=True):
            desktop_session.resources()

        mock_print.assert_has_calls(
            [
                call("desktop_session: False"),
                call("session_type: tty"),
            ]
        )

    @patch("builtins.print")
    def test_resources_desktop(self, mock_print):
        """Test the result faking a desktop session."""

        server_session = {
            "XDG_SESSION_TYPE": "wayland",
            "XDG_CURRENT_DESKTOP": "hyprland",
        }
        with patch.dict(os.environ, server_session, clear=True):
            desktop_session.resources()

        mock_print.assert_has_calls(
            [
                call("desktop_session: True"),
                call("session_type: wayland"),
            ]
        )
