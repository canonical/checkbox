import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from subprocess import CompletedProcess
from unittest.mock import patch

import optee_helper

INITRAMFS_SUPPLICANT = "352 @tee-supplicant --fs-parent-path /run/mnt/tee-data"
SNAP_SUPPLICANT = (
    "1234 tee-supplicant --fs-parent-path /var/snap/x-test/common/lib/"
    "optee-fs --ta-path /var/snap/x-test/common/lib/optee_armtz "
    "--plugin-path /var/snap/x-test/common/usr/lib/tee-supplicant/plugins"
)


def _proc(returncode=0, stdout="", stderr=""):
    return CompletedProcess([], returncode, stdout=stdout, stderr=stderr)


class TestFindSupplicant(unittest.TestCase):
    @patch("optee_helper.subprocess.run")
    def test_splits_pid_and_cmdline(self, mock_run):
        mock_run.return_value = _proc(stdout=INITRAMFS_SUPPLICANT + "\n")
        self.assertEqual(
            optee_helper._find_supplicant(),
            ("352", "@tee-supplicant --fs-parent-path /run/mnt/tee-data"),
        )


class TestSupplicantServesTaDir(unittest.TestCase):
    def test_snap_supplicant_with_ta_path(self):
        self.assertTrue(
            optee_helper._supplicant_serves_ta_dir(SNAP_SUPPLICANT)
        )

    def test_snap_supplicant_400_with_ta_dir(self):
        self.assertTrue(
            optee_helper._supplicant_serves_ta_dir(
                "tee-supplicant --ta-dir /var/snap/x-test/common/lib/"
                "optee_armtz"
            )
        )

    def test_initramfs_supplicant_without_ta_dir(self):
        self.assertFalse(
            optee_helper._supplicant_serves_ta_dir(INITRAMFS_SUPPLICANT)
        )


@patch("optee_helper.stage_ta_for_supplicant")
@patch("optee_helper.install_ta")
@patch("optee_helper.find_ta_path", return_value="/var/snap/x/optee_armtz")
@patch("optee_helper._run_command", return_value=_proc())
@patch("optee_helper.look_up_app", return_value="x-test.xtest")
class TestLaunchXtestTaDelivery(unittest.TestCase):
    @patch(
        "optee_helper._find_supplicant",
        return_value=("352", INITRAMFS_SUPPLICANT),
    )
    @patch("optee_helper._lookup_optee_version", return_value="4.2")
    def test_4x_supplicant_without_ta_dir_stages(self, *_):
        optee_helper.launch_xtest("regression", "4101")
        optee_helper.stage_ta_for_supplicant.assert_called_once_with(
            "/var/snap/x/optee_armtz", "/proc/352/root"
        )
        optee_helper.install_ta.assert_not_called()

    @patch(
        "optee_helper._find_supplicant", return_value=("1234", SNAP_SUPPLICANT)
    )
    @patch("optee_helper._lookup_optee_version", return_value="4.2")
    def test_4x_snap_supplicant_does_nothing(self, *_):
        optee_helper.launch_xtest("regression", "4101")
        optee_helper.stage_ta_for_supplicant.assert_not_called()
        optee_helper.install_ta.assert_not_called()

    @patch(
        "optee_helper._find_supplicant", return_value=("1234", SNAP_SUPPLICANT)
    )
    @patch("optee_helper._lookup_optee_version", return_value="3.19")
    def test_pre_4x_still_installs(self, *_):
        optee_helper.launch_xtest("regression", "4101")
        optee_helper.install_ta.assert_called_once_with(
            "x-test.xtest", "/var/snap/x/optee_armtz"
        )
        optee_helper.stage_ta_for_supplicant.assert_not_called()


class TestStageTaForSupplicant(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.ta_path = os.path.join(self.tmp.name, "optee_armtz")
        os.mkdir(self.ta_path)
        for name in ("b.ta", "a.ta", "version"):
            with open(os.path.join(self.ta_path, name), "w") as fp:
                fp.write(name)
        self.root = os.path.join(self.tmp.name, "root")
        os.mkdir(self.root)

    def test_copies_only_ta_files_into_default_dir_under_root(self):
        with redirect_stdout(io.StringIO()) as out:
            optee_helper.stage_ta_for_supplicant(self.ta_path, self.root)
        dest = os.path.join(self.root, "lib", "optee_armtz")
        self.assertEqual(sorted(os.listdir(dest)), ["a.ta", "b.ta"])
        self.assertIn("Staged 2 TAs into {}".format(dest), out.getvalue())

    def test_repeat_overwrites_without_error(self):
        with redirect_stdout(io.StringIO()):
            optee_helper.stage_ta_for_supplicant(self.ta_path, self.root)
            optee_helper.stage_ta_for_supplicant(self.ta_path, self.root)
        dest = os.path.join(self.root, "lib", "optee_armtz")
        self.assertEqual(sorted(os.listdir(dest)), ["a.ta", "b.ta"])

    def test_unwritable_root_is_reported_not_raised(self):
        not_a_dir = os.path.join(self.tmp.name, "file")
        with open(not_a_dir, "w") as fp:
            fp.write("x")
        with redirect_stdout(io.StringIO()) as out:
            optee_helper.stage_ta_for_supplicant(self.ta_path, not_a_dir)
        self.assertIn("Cannot stage TAs into", out.getvalue())


class TestGenerateSkipsSnapSupplicantOnlyCases(unittest.TestCase):
    CASES = [
        {"suite": s, "test_id": i, "test_name": "t" + i, "test_description": d}
        for s, i, d in [
            ("regression", "1033", "Test the supplicant plugin framework"),
            ("regression", "1039", "Test subkey verification"),
            ("regression", "4101", "Bigint init"),
            ("pkcs11", "1000", "Initialize and close Cryptoki library"),
        ]
    ]

    def _generate(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json") as fp:
            json.dump(self.CASES, fp)
            fp.flush()
            out, err = io.StringIO(), io.StringIO()
            with redirect_stdout(out), redirect_stderr(err):
                optee_helper.parse_json_file(fp.name)
        return out.getvalue(), err.getvalue()

    @patch(
        "optee_helper._find_supplicant",
        return_value=("352", INITRAMFS_SUPPLICANT),
    )
    def test_system_supplicant_drops_1033_and_1039(self, _):
        out, err = self._generate()
        self.assertNotIn("test_id: 1033", out)
        self.assertNotIn("test_id: 1039", out)
        self.assertIn("test_id: 4101", out)
        self.assertIn("skipping regression 1033", err)
        self.assertIn("skipping regression 1039", err)

    @patch(
        "optee_helper._find_supplicant", return_value=("1234", SNAP_SUPPLICANT)
    )
    def test_snap_supplicant_keeps_every_case(self, _):
        out, err = self._generate()
        self.assertIn("test_id: 1033", out)
        self.assertIn("test_id: 1039", out)
        self.assertEqual(err, "")


if __name__ == "__main__":
    unittest.main()
