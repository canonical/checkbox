# This file is part of Checkbox.
#
# Copyright 2013-2026 Canonical Ltd.
# Written by:
#   Massimiliano Girardi <massimiliano.girardi@canonical.com>
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
"""
plainbox.impl.secure.providers.test_custom_frontend
===================================================

Test definitions for plainbox.impl.secure.providers.custom_frontend module
"""

from collections import defaultdict
from pathlib import Path
from textwrap import dedent
from unittest import TestCase
from unittest.mock import Mock, MagicMock, patch

from plainbox.impl.secure.providers import custom_frontend
from plainbox.impl.secure.providers.custom_frontend import (
    custom_frontend_roots,
    parse_extra_path_environment_file,
    extra_snap_environment,
    extra_PYTHONPATH,
    extra_PATH,
    extra_LD_LIBRARY_PATH,
)


def _path_mock(value):
    path = Path(value)
    m = MagicMock(spec=Path)
    m.exists.return_value = True
    m.__str__.return_value = str(path)
    m.__truediv__.side_effect = lambda other: _path_mock(path / other)
    return m


class CustomFrontendTests(TestCase):

    @patch.object(custom_frontend, "CUSTOM_FRONTEND_LOCATION", None)
    def test_custom_frontend_roots_non_snap(self):
        self.assertEqual(custom_frontend_roots(), [])

    @patch.object(custom_frontend, "CUSTOM_FRONTEND_LOCATION")
    def test_custom_frontend_roots_file_not_found(self, location):
        location.iterdir.side_effect = FileNotFoundError
        self.assertEqual(custom_frontend_roots(), [])

    @patch.object(Path, "is_dir", new=Mock(return_value=True))
    @patch.object(custom_frontend, "CUSTOM_FRONTEND_LOCATION")
    def test_custom_frontend_roots_ok(self, location):
        dir_a = Path("/snap/checkbox24/x1/custom_frontends/custom_frontend")
        dir_b = Path("/snap/checkbox24/x1/custom_frontends/custom_frontend2")
        location.iterdir.return_value = [dir_a, dir_b]
        self.assertEqual(custom_frontend_roots(), [dir_a, dir_b])

    @patch.object(custom_frontend, "custom_frontend_roots")
    @patch("os.getenv", new=Mock(return_value="/snap/checkbox24/x1"))
    def test_extra_PYTHONPATH_custom_frontend(self, roots):
        roots.return_value = [
            _path_mock(
                "/snap/checkbox24/current/custom_fontends/custom_frontend"
            )
        ]
        self.assertGreater(len(extra_PYTHONPATH.__wrapped__()), 0)

    @patch("os.getenv", new=Mock(return_value=None))
    def test_extra_PYTHONPATH_none(self):
        self.assertFalse(extra_PYTHONPATH.__wrapped__())

    @patch.object(custom_frontend, "custom_frontend_roots")
    @patch("os.getenv", new=Mock(return_value="/snap/checkbox24/x1"))
    def test_extra_PATH_custom_frontend(self, roots):
        roots.return_value = [
            _path_mock(
                "/snap/checkbox24/current/custom_fontends/custom_frontend"
            )
        ]
        self.assertGreater(len(extra_PATH.__wrapped__()), 0)

    @patch("os.getenv", new=Mock(return_value=None))
    def test_extra_PATH_none(self):
        self.assertFalse(extra_PATH.__wrapped__())

    @patch.object(custom_frontend, "custom_frontend_roots")
    @patch("os.getenv", new=Mock(return_value="/snap/checkbox24/x1"))
    def test_extra_LD_LIBRARY_PATH_custom_frontend(self, roots):
        roots.return_value = [
            _path_mock(
                "/snap/checkbox24/current/custom_fontends/custom_frontend"
            )
        ]
        self.assertGreater(len(extra_LD_LIBRARY_PATH.__wrapped__()), 0)

    @patch("os.getenv", new=Mock(return_value=None))
    def test_extra_LD_LIBRARY_PATH_none(self):
        self.assertFalse(extra_LD_LIBRARY_PATH.__wrapped__())

    def test_parse_extra_path_environment_file(self):
        extra_envvar_file = dedent("""# some comment
        LD_LIBRARY_PATH+=some_path
          # can also be indented
          LD_LIBRARY_PATH += /some other path starts slash
        PATH+=extra/path/location
        malformed lines are ignored
        """)

        with patch(
            "pathlib.Path.read_text",
            return_value=extra_envvar_file,
        ):
            path = Path("/snap/checkbox24/custom_frontends/custom_frontend")
            extra_env = parse_extra_path_environment_file(path)

        self.assertEqual(set(extra_env), {"LD_LIBRARY_PATH", "PATH"})
        self.assertEqual(
            extra_env["PATH"],
            [
                "/snap/checkbox24/custom_frontends/custom_frontend/extra/path/location"
            ],
        )
        self.assertEqual(
            extra_env["LD_LIBRARY_PATH"],
            [
                "/snap/checkbox24/custom_frontends/custom_frontend/some_path",
                "/snap/checkbox24/custom_frontends/custom_frontend/some other path starts slash",
            ],
        )

    @patch("os.getenv")
    def test_extra_snap_environment_not_snap(self, getenv):
        getenv.return_value = None
        self.assertFalse(extra_snap_environment.__wrapped__())

    @patch.object(custom_frontend, "custom_frontend_roots")
    @patch.object(custom_frontend, "parse_extra_path_environment_file")
    @patch("os.getenv")
    def test_extra_snap_environment_snap(self, getenv, parse_file, roots):
        getenv.return_value = "/snap/checkbox24/current"
        roots.return_value = [MagicMock()]
        parse_file.side_effect = [
            defaultdict(
                list,
                {
                    "LD_LIBRARY_PATH": [
                        "/snap/checkbox24/current/some",
                        "/snap/checkbox24/current/other",
                    ]
                },
            ),
            defaultdict(
                list,
                {
                    "LD_LIBRARY_PATH": [
                        "/snap/checkbox24/current/custom_frontends/custom_frontend/some",
                    ],
                    "PATH": [
                        "/snap/custom_frontend/random/bin/path",
                    ],
                },
            ),
        ]
        # Note the order, custom frontend variables have precedence
        self.assertEqual(
            extra_snap_environment.__wrapped__(),
            {
                "LD_LIBRARY_PATH": [
                    "/snap/checkbox24/current/custom_frontends/custom_frontend/some",
                    "/snap/checkbox24/current/some",
                    "/snap/checkbox24/current/other",
                ],
                "PATH": [
                    "/snap/custom_frontend/random/bin/path",
                ],
            },
        )
