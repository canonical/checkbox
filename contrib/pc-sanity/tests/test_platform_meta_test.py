"""
Tests for bin/platform_meta_test.py

Functions under test are imported directly and system calls are patched
with unittest.mock so no subprocess stubs or temporary PATH tricks are needed.
"""

import sys
import os
import unittest
from unittest.mock import patch, MagicMock

# Make bin/ importable.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "bin"))
import platform_meta_test as pmt  # noqa: E402

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_modaliases(pattern):
    """Return a fake 'apt-cache show' Modaliases line."""
    return f"Modaliases: meta({pattern})"


# Per-OEM configuration used by the patch helper.
# Keys mirror _OEM_CONFIGS in the module under test.
_OEM_TEST_CONFIG = {
    "somerville": {
        "dmi_value": "08AF",
        "codename": "jammy",
        "meta_pkg": "oem-somerville-beric-icl-meta",
        "modalias_match": lambda biosid: f"pci:*sv00001028sd0000{biosid}*",
        "modalias_mismatch": "pci:*sv00001028sd00000000*",
    },
    "stella": {
        "dmi_value": "0896",
        "codename": "jammy",
        "meta_pkg": "oem-stella-nymeria-meta",
        "modalias_match": lambda biosid: f"pci:*sv0000103csd0000{biosid}*",
        "modalias_mismatch": "pci:*sv0000103csd00000000*",
    },
    "sutton": {
        # bios_version raw value; biosid will be the first 3 chars "A01"
        "dmi_value": "A01XXX",
        "codename": "jammy",
        "meta_pkg": "oem-sutton.bachman-baara-meta",
        "modalias_match": lambda biosid: f"bvr{biosid}",
        "modalias_mismatch": "bvrZZZ",
    },
}


def _patch_oem(
    oem,
    codename=None,
    meta_installed=True,
    factory_installed=True,
    bios_in_modaliases=True,
):
    """Return a dict of patches for check_oem_meta(oem)."""
    cfg = _OEM_TEST_CONFIG[oem]
    dmi_value = cfg["dmi_value"]
    if codename is None:
        codename = cfg["codename"]

    meta_pkg = cfg["meta_pkg"]
    # Derive factory_pkg the same way check_oem_meta does, using the
    # factory_prefix from _OEM_CONFIGS (not the test config).
    oem_cfg = pmt._OEM_CONFIGS[oem]
    fp = oem_cfg["factory_prefix"]
    factory_pkg = meta_pkg.replace(fp, fp + "-factory", 1)

    # For sutton the biosid is the first 3 chars of the dmi value.
    biosid = dmi_value[:3] if oem == "sutton" else dmi_value
    modalias_pattern = (
        cfg["modalias_match"](biosid)
        if bios_in_modaliases
        else cfg["modalias_mismatch"]
    )
    modaliases = _make_modaliases(modalias_pattern)

    def fake_apt_cache(pkg):
        return modaliases

    def fake_is_installed(pkg):
        if pkg == meta_pkg:
            return meta_installed
        if pkg == factory_pkg:
            return factory_installed
        return False

    return {
        "_read_dmi": MagicMock(return_value=dmi_value),
        "_ubuntu_codename": MagicMock(return_value=codename),
        "_ubuntu_drivers_list": MagicMock(return_value=[meta_pkg]),
        "_apt_cache_modaliases": MagicMock(side_effect=fake_apt_cache),
        "_is_installed": MagicMock(side_effect=fake_is_installed),
    }


def _apply_patches(patches):
    """Context manager: patch all names in *patches* inside pmt module."""
    import contextlib

    managers = [patch.object(pmt, name, val) for name, val in patches.items()]

    @contextlib.contextmanager
    def _ctx():
        with contextlib.ExitStack() as stack:
            for m in managers:
                stack.enter_context(m)
            yield

    return _ctx()


# ===========================================================================
# check_oem_meta — all three OEMs x jammy / noble / unsupported
# ===========================================================================


class TestCheckOemMeta(unittest.TestCase):
    """Parametric tests for check_oem_meta covering all three OEM codenames."""

    def _assert_exit(self, oem, expected_code, **kw):
        patches = _patch_oem(oem, **kw)
        with _apply_patches(patches):
            with self.assertRaises(SystemExit) as cm:
                pmt.check_oem_meta(oem)
        self.assertEqual(cm.exception.code, expected_code)

    def _assert_passes(self, oem, codename):
        self._assert_exit(oem, 0, codename=codename)

    def _assert_fails(self, oem, codename, **kw):
        self._assert_exit(oem, 1, codename=codename, **kw)

    # --- somerville ---

    def test_somerville_jammy_pass(self):
        self._assert_passes("somerville", "jammy")

    def test_somerville_noble_pass(self):
        self._assert_passes("somerville", "noble")

    def test_somerville_jammy_fail_meta_not_installed(self):
        self._assert_fails(
            "somerville",
            "jammy",
            meta_installed=False,
            factory_installed=False,
        )

    def test_somerville_jammy_fail_factory_not_installed(self):
        self._assert_fails("somerville", "jammy", factory_installed=False)

    def test_somerville_jammy_fail_bios_id_mismatch(self):
        self._assert_fails("somerville", "jammy", bios_in_modaliases=False)

    def test_somerville_noble_fail_meta_not_installed(self):
        self._assert_fails(
            "somerville",
            "noble",
            meta_installed=False,
            factory_installed=False,
        )

    def test_somerville_noble_fail_factory_not_installed(self):
        self._assert_fails("somerville", "noble", factory_installed=False)

    def test_somerville_noble_fail_bios_id_mismatch(self):
        self._assert_fails("somerville", "noble", bios_in_modaliases=False)

    def test_somerville_unsupported_codename_fails(self):
        self._assert_fails("somerville", "mantic")

    # --- stella ---

    def test_stella_jammy_pass(self):
        self._assert_passes("stella", "jammy")

    def test_stella_noble_pass(self):
        self._assert_passes("stella", "noble")

    def test_stella_jammy_fail_meta_not_installed(self):
        self._assert_fails(
            "stella", "jammy", meta_installed=False, factory_installed=False
        )

    def test_stella_jammy_fail_factory_not_installed(self):
        self._assert_fails("stella", "jammy", factory_installed=False)

    def test_stella_jammy_fail_bios_id_mismatch(self):
        self._assert_fails("stella", "jammy", bios_in_modaliases=False)

    def test_stella_noble_fail_meta_not_installed(self):
        self._assert_fails(
            "stella", "noble", meta_installed=False, factory_installed=False
        )

    def test_stella_noble_fail_factory_not_installed(self):
        self._assert_fails("stella", "noble", factory_installed=False)

    def test_stella_noble_fail_bios_id_mismatch(self):
        self._assert_fails("stella", "noble", bios_in_modaliases=False)

    def test_stella_unsupported_codename_fails(self):
        self._assert_fails("stella", "mantic")

    # --- sutton ---

    def test_sutton_jammy_pass(self):
        self._assert_passes("sutton", "jammy")

    def test_sutton_noble_pass(self):
        self._assert_passes("sutton", "noble")

    def test_sutton_jammy_fail_meta_not_installed(self):
        self._assert_fails(
            "sutton", "jammy", meta_installed=False, factory_installed=False
        )

    def test_sutton_jammy_fail_factory_not_installed(self):
        self._assert_fails("sutton", "jammy", factory_installed=False)

    def test_sutton_jammy_fail_bios_id_mismatch(self):
        self._assert_fails("sutton", "jammy", bios_in_modaliases=False)

    def test_sutton_noble_fail_meta_not_installed(self):
        self._assert_fails(
            "sutton", "noble", meta_installed=False, factory_installed=False
        )

    def test_sutton_noble_fail_factory_not_installed(self):
        self._assert_fails("sutton", "noble", factory_installed=False)

    def test_sutton_noble_fail_bios_id_mismatch(self):
        self._assert_fails("sutton", "noble", bios_in_modaliases=False)

    def test_sutton_unsupported_codename_fails(self):
        self._assert_fails("sutton", "mantic")

    def test_sutton_biosid_uses_first_three_chars_of_bios_version(self):
        """Verify the biosid slice: only the first 3 chars of bios_version are used."""
        # bios_version "A01XXX" -> biosid "A01"; modalias uses "A01", so it must match.
        self._assert_passes("sutton", "jammy")

    def test_sutton_no_matching_packages_fails(self):
        """When ubuntu-drivers returns no oem packages, exit 1."""
        patches = _patch_oem("sutton", codename="jammy")
        patches["_ubuntu_drivers_list"] = MagicMock(return_value=[])
        with _apply_patches(patches):
            with self.assertRaises(SystemExit) as cm:
                pmt.check_oem_meta("sutton")
        self.assertEqual(cm.exception.code, 1)


# ===========================================================================
# main() argument parsing / dispatch
# ===========================================================================


class TestMainArguments(unittest.TestCase):

    def _main(self, argv):
        with patch.object(sys, "argv", ["platform_meta_test.py"] + argv):
            with self.assertRaises(SystemExit) as cm:
                pmt.main()
        return cm.exception.code

    def test_help_exits_zero(self):
        with self.assertRaises(SystemExit) as cm:
            with patch.object(
                sys, "argv", ["platform_meta_test.py", "--help"]
            ):
                pmt.main()
        self.assertEqual(cm.exception.code, 0)

    def test_unknown_oem_codename_exits_nonzero(self):
        self.assertNotEqual(
            self._main(["--oem-codename", "unknown-project"]), 0
        )

    def test_no_arguments_exits_nonzero(self):
        self.assertNotEqual(self._main([]), 0)

    def test_stella_cmit_alias_rejected(self):
        """'stella.cmit' is not a known OEM codename and must be rejected."""
        self.assertNotEqual(self._main(["--oem-codename", "stella.cmit"]), 0)

    def test_somerville_dispatches(self):
        with patch.object(pmt, "check_oem_meta") as mock:
            mock.side_effect = SystemExit(0)
            self.assertEqual(self._main(["--oem-codename", "somerville"]), 0)
            mock.assert_called_once_with("somerville")

    def test_stella_dispatches(self):
        with patch.object(pmt, "check_oem_meta") as mock:
            mock.side_effect = SystemExit(0)
            self.assertEqual(self._main(["--oem-codename", "stella"]), 0)
            mock.assert_called_once_with("stella")

    def test_sutton_dispatches(self):
        with patch.object(pmt, "check_oem_meta") as mock:
            mock.side_effect = SystemExit(0)
            self.assertEqual(self._main(["--oem-codename", "sutton"]), 0)
            mock.assert_called_once_with("sutton")


if __name__ == "__main__":
    unittest.main()
