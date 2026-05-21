#!/usr/bin/env python3
#
# This file is part of Checkbox.
#
# Copyright 2026 Canonical Ltd.
#
# Authors:
#   Zhongning Li <zhongning.li@canonical.com>
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

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

_mock_slugify = MagicMock(side_effect=lambda x: x)
sys.modules.setdefault("checkbox_support", MagicMock())
sys.modules.setdefault("checkbox_support.helpers", MagicMock())
sys.modules.setdefault(
    "checkbox_support.helpers.slugify", MagicMock(slugify=_mock_slugify)
)

import detect_vrr  # noqa: E402


def _null_ptr():
    """Return a MagicMock that evaluates as falsy (simulates a NULL pointer)."""
    ptr = MagicMock()
    ptr.__bool__ = MagicMock(return_value=False)
    return ptr


def _ptr(contents):
    """Return a MagicMock that evaluates as truthy with the given .contents."""
    ptr = MagicMock()
    ptr.__bool__ = MagicMock(return_value=True)
    ptr.contents = contents
    return ptr


def _make_res(connector_ids):
    """Build a mock drmModeRes with the given list of connector IDs."""
    res = MagicMock()
    res.count_connectors = len(connector_ids)
    res.connectors = connector_ids
    return res


def _make_conn(connection=1, props=None, prop_values=None):
    """Build a mock drmModeConnector."""
    conn = MagicMock()
    conn.connection = connection
    props = props or []
    conn.count_props = len(props)
    conn.props = props
    conn.prop_values = prop_values or []
    return conn


def _make_prop(name):
    """Build a mock drmModePropertyRes with the given property name."""
    prop = MagicMock()
    prop.name.decode.return_value = name
    return prop


class TestGetVrrCapableMonitors(unittest.TestCase):
    """Tests for get_vrr_capable_monitors()."""

    def setUp(self):
        # Each test gets a fresh mock drm object.
        self.mock_drm = MagicMock()
        detect_vrr.drm = self.mock_drm

    def tearDown(self):
        detect_vrr.drm = None

    def _call(self, path="/dev/dri/card0"):
        """Call get_vrr_capable_monitors with a mocked file open."""
        mock_file = MagicMock()
        mock_file.__enter__ = MagicMock(return_value=mock_file)
        mock_file.__exit__ = MagicMock(return_value=False)
        mock_file.fileno.return_value = 5
        with patch.object(Path, "open", return_value=mock_file):
            return detect_vrr.get_vrr_capable_monitors(Path(path))

    def test_raises_systemexit_when_drm_not_initialized(self):
        detect_vrr.drm = None
        with self.assertRaises(SystemExit):
            detect_vrr.get_vrr_capable_monitors(Path("/dev/dri/card0"))

    def test_raises_runtime_error_when_get_resources_returns_null(self):
        self.mock_drm.drmModeGetResources.return_value = _null_ptr()
        with self.assertRaises(RuntimeError):
            self._call()

    def test_returns_false_when_no_connectors(self):
        self.mock_drm.drmModeGetResources.return_value = _ptr(_make_res([]))
        result = self._call()
        self.assertFalse(result)
        self.mock_drm.drmModeFreeResources.assert_called_once()

    def test_returns_false_for_disconnected_connector(self):
        conn = _make_conn(connection=0)  # 0 = disconnected
        self.mock_drm.drmModeGetResources.return_value = _ptr(_make_res([10]))
        self.mock_drm.drmModeGetConnector.return_value = _ptr(conn)

        result = self._call()

        self.assertFalse(result)
        # drmModeFreeConnector is not called when the connector is skipped
        self.mock_drm.drmModeFreeConnector.assert_not_called()

    def test_skips_null_connector_pointer(self):
        self.mock_drm.drmModeGetResources.return_value = _ptr(_make_res([10]))
        self.mock_drm.drmModeGetConnector.return_value = _null_ptr()

        result = self._call()

        self.assertFalse(result)
        # drmModeFreeConnector must NOT be called for a NULL pointer
        self.mock_drm.drmModeFreeConnector.assert_not_called()

    def test_returns_false_when_connector_has_no_props(self):
        conn = _make_conn(connection=1, props=[], prop_values=[])
        self.mock_drm.drmModeGetResources.return_value = _ptr(_make_res([10]))
        self.mock_drm.drmModeGetConnector.return_value = _ptr(conn)

        result = self._call()

        self.assertFalse(result)

    def test_skips_null_property_pointer(self):
        conn = _make_conn(connection=1, props=[100], prop_values=[0])
        self.mock_drm.drmModeGetResources.return_value = _ptr(_make_res([10]))
        self.mock_drm.drmModeGetConnector.return_value = _ptr(conn)
        self.mock_drm.drmModeGetProperty.return_value = _null_ptr()

        result = self._call()

        self.assertFalse(result)
        self.mock_drm.drmModeFreeProperty.assert_not_called()

    def test_returns_false_when_vrr_capable_is_zero(self):
        prop = _make_prop("vrr_capable")
        conn = _make_conn(connection=1, props=[100], prop_values=[0])
        self.mock_drm.drmModeGetResources.return_value = _ptr(_make_res([10]))
        self.mock_drm.drmModeGetConnector.return_value = _ptr(conn)
        self.mock_drm.drmModeGetProperty.return_value = _ptr(prop)

        result = self._call()

        self.assertFalse(result)

    def test_returns_true_when_vrr_capable_is_one(self):
        prop = _make_prop("vrr_capable")
        conn = _make_conn(connection=1, props=[100], prop_values=[1])
        self.mock_drm.drmModeGetResources.return_value = _ptr(_make_res([10]))
        self.mock_drm.drmModeGetConnector.return_value = _ptr(conn)
        self.mock_drm.drmModeGetProperty.return_value = _ptr(prop)

        result = self._call()

        self.assertTrue(result)

    def test_prints_info_when_vrr_capable(self):
        prop = _make_prop("vrr_capable")
        conn = _make_conn(connection=1, props=[100], prop_values=[1])
        conn.connector_id = 42
        self.mock_drm.drmModeGetResources.return_value = _ptr(_make_res([42]))
        self.mock_drm.drmModeGetConnector.return_value = _ptr(conn)
        self.mock_drm.drmModeGetProperty.return_value = _ptr(prop)

        with patch("builtins.print") as mock_print:
            self._call("/dev/dri/card0")

        mock_print.assert_any_call("vrr_supported: True")

    def test_returns_false_for_unrelated_property(self):
        prop = _make_prop("brightness")
        conn = _make_conn(connection=1, props=[100], prop_values=[1])
        self.mock_drm.drmModeGetResources.return_value = _ptr(_make_res([10]))
        self.mock_drm.drmModeGetConnector.return_value = _ptr(conn)
        self.mock_drm.drmModeGetProperty.return_value = _ptr(prop)

        result = self._call()

        self.assertFalse(result)

    def test_returns_true_with_multiple_connectors_one_vrr_capable(self):
        non_vrr_prop = _make_prop("brightness")
        vrr_prop = _make_prop("vrr_capable")

        # connector 10: connected, property "brightness" = 0 (not VRR)
        conn_a = _make_conn(connection=1, props=[100], prop_values=[0])
        # connector 20: connected, property "vrr_capable" = 1
        conn_b = _make_conn(connection=1, props=[200], prop_values=[1])

        res = _make_res([10, 20])
        self.mock_drm.drmModeGetResources.return_value = _ptr(res)

        def get_connector(fd, conn_id):
            return _ptr(conn_a) if conn_id == 10 else _ptr(conn_b)

        def get_property(fd, prop_id):
            return _ptr(non_vrr_prop) if prop_id == 100 else _ptr(vrr_prop)

        self.mock_drm.drmModeGetConnector.side_effect = get_connector
        self.mock_drm.drmModeGetProperty.side_effect = get_property

        result = self._call()

        self.assertTrue(result)

    def test_drm_free_calls_are_made(self):
        prop = _make_prop("vrr_capable")
        conn = _make_conn(connection=1, props=[100], prop_values=[1])
        res_ptr_mock = _ptr(_make_res([10]))
        conn_ptr_mock = _ptr(conn)
        prop_ptr_mock = _ptr(prop)

        self.mock_drm.drmModeGetResources.return_value = res_ptr_mock
        self.mock_drm.drmModeGetConnector.return_value = conn_ptr_mock
        self.mock_drm.drmModeGetProperty.return_value = prop_ptr_mock

        self._call()

        self.mock_drm.drmModeFreeProperty.assert_called_once_with(prop_ptr_mock)
        self.mock_drm.drmModeFreeConnector.assert_called_once_with(conn_ptr_mock)
        self.mock_drm.drmModeFreeResources.assert_called_once_with(res_ptr_mock)


class TestMain(unittest.TestCase):
    """Tests for main()."""

    def setUp(self):
        detect_vrr.drm = None

    def tearDown(self):
        detect_vrr.drm = None

    def test_raises_import_error_when_libdrm_not_found(self):
        with patch("ctypes.util.find_library", return_value=None):
            with self.assertRaises(ImportError):
                detect_vrr.main()

    def test_raises_systemexit_when_no_vrr_capable_card(self):
        card0 = MagicMock(spec=Path)
        card0.__str__ = MagicMock(return_value="/dev/dri/card0")
        card0.name = "card0"

        with (
            patch("ctypes.util.find_library", return_value="libdrm.so.2"),
            patch("ctypes.CDLL") as mock_cdll,
            patch("os.path.basename", return_value="card0"),
            patch.object(Path, "iterdir", return_value=iter([card0])),
            patch("detect_vrr.get_vrr_capable_monitors", return_value=False),
        ):
            mock_cdll.return_value = MagicMock()
            with self.assertRaises(SystemExit) as cm:
                detect_vrr.main()

        self.assertIn("VRR", str(cm.exception))

    def test_exits_cleanly_when_at_least_one_vrr_capable_card(self):
        card0 = MagicMock(spec=Path)
        card0.__str__ = MagicMock(return_value="/dev/dri/card0")
        card0.name = "card0"

        with (
            patch("ctypes.util.find_library", return_value="libdrm.so.2"),
            patch("ctypes.CDLL") as mock_cdll,
            patch("os.path.basename", return_value="card0"),
            patch.object(Path, "iterdir", return_value=iter([card0])),
            patch("detect_vrr.get_vrr_capable_monitors", return_value=True),
        ):
            mock_cdll.return_value = MagicMock()
            # Should not raise
            detect_vrr.main()

    def test_skips_non_card_entries_in_dri_dir(self):
        render0 = MagicMock(spec=Path)
        render0.__str__ = MagicMock(return_value="/dev/dri/renderD128")

        with (
            patch("ctypes.util.find_library", return_value="libdrm.so.2"),
            patch("ctypes.CDLL"),
            patch("os.path.basename", return_value="renderD128"),
            patch.object(Path, "iterdir", return_value=iter([render0])),
            patch("detect_vrr.get_vrr_capable_monitors") as mock_get_vrr,
        ):
            with self.assertRaises(SystemExit):
                detect_vrr.main()

        mock_get_vrr.assert_not_called()

    def test_initializes_drm_restype_after_load(self):
        """main() must set the restype for the three DRM getter functions."""
        import ctypes

        card0 = MagicMock(spec=Path)
        card0.__str__ = MagicMock(return_value="/dev/dri/card0")

        mock_lib = MagicMock()

        with (
            patch("ctypes.util.find_library", return_value="libdrm.so.2"),
            patch("ctypes.CDLL", return_value=mock_lib),
            patch("os.path.basename", return_value="card0"),
            patch.object(Path, "iterdir", return_value=iter([card0])),
            patch("detect_vrr.get_vrr_capable_monitors", return_value=True),
        ):
            detect_vrr.main()

        self.assertEqual(
            mock_lib.drmModeGetResources.restype,
            ctypes.POINTER(detect_vrr.drmModeRes),
        )
        self.assertEqual(
            mock_lib.drmModeGetConnector.restype,
            ctypes.POINTER(detect_vrr.drmModeConnector),
        )
        self.assertEqual(
            mock_lib.drmModeGetProperty.restype,
            ctypes.POINTER(detect_vrr.drmModePropertyRes),
        )


if __name__ == "__main__":
    unittest.main()
