import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from subprocess import CompletedProcess
from unittest.mock import patch

import optee_helper
import xtest_install_ta


def _proc(returncode=0, stdout="", stderr=""):
    return CompletedProcess([], returncode, stdout=stdout, stderr=stderr)


class TestSupplicantServesTaDir(unittest.TestCase):
    @patch("optee_helper.subprocess.run")
    def test_snap_supplicant_with_ta_path(self, mock_run):
        mock_run.return_value = _proc(
            stdout="1234 tee-supplicant --fs-parent-path /var/snap/x-test/"
            "common/lib/optee-fs --ta-path /var/snap/x-test/common/lib/"
            "optee_armtz\n"
        )
        self.assertTrue(optee_helper._supplicant_serves_ta_dir())

    @patch("optee_helper.subprocess.run")
    def test_snap_supplicant_with_ta_dir(self, mock_run):
        mock_run.return_value = _proc(
            stdout="1234 tee-supplicant --ta-dir /var/snap/x-test/common/"
            "lib/optee_armtz\n"
        )
        self.assertTrue(optee_helper._supplicant_serves_ta_dir())

    @patch("optee_helper.subprocess.run")
    def test_initramfs_supplicant_without_ta_dir(self, mock_run):
        mock_run.return_value = _proc(
            stdout="352 @tee-supplicant --fs-parent-path /run/mnt/tee-data\n"
        )
        self.assertFalse(optee_helper._supplicant_serves_ta_dir())


@patch("optee_helper.install_ta")
@patch("optee_helper.find_ta_path", return_value="/var/snap/x/optee_armtz")
@patch("optee_helper._run_command", return_value=_proc())
@patch("optee_helper.look_up_app", return_value="x-test.xtest")
class TestLaunchXtestInstallsTa(unittest.TestCase):
    @patch("optee_helper._supplicant_serves_ta_dir", return_value=False)
    @patch("optee_helper._lookup_optee_version", return_value="4.2")
    def test_4x_system_supplicant_installs(self, *_):
        optee_helper.launch_xtest("regression", "4101")
        optee_helper.install_ta.assert_called_once_with(
            "x-test.xtest", "/var/snap/x/optee_armtz"
        )

    @patch("optee_helper._supplicant_serves_ta_dir", return_value=True)
    @patch("optee_helper._lookup_optee_version", return_value="4.2")
    def test_4x_snap_supplicant_skips_install(self, *_):
        optee_helper.launch_xtest("regression", "4101")
        optee_helper.install_ta.assert_not_called()

    @patch("optee_helper._supplicant_serves_ta_dir", return_value=True)
    @patch("optee_helper._lookup_optee_version", return_value="3.19")
    def test_pre_4x_always_installs(self, *_):
        optee_helper.launch_xtest("regression", "4101")
        optee_helper.install_ta.assert_called_once()


class TestInstallTa(unittest.TestCase):
    @patch("xtest_install_ta.run")
    @patch(
        "xtest_install_ta.glob.glob",
        return_value=["/ta/b.ta", "/ta/a.ta", "/ta/c.ta"],
    )
    def test_rejected_ta_does_not_block_the_rest(self, _, mock_run):
        mock_run.side_effect = [
            _proc(),
            _proc(1, stderr="TEEC_InvokeCommand: 0xffff000f"),
            _proc(),
        ]
        with redirect_stdout(io.StringIO()) as out:
            rejected = xtest_install_ta.install_ta("x-test.xtest", "/ta")
        self.assertEqual(rejected, ["b.ta"])
        self.assertEqual(mock_run.call_count, 3)
        self.assertEqual(
            [c.args[0][-1] for c in mock_run.call_args_list],
            ["/ta/a.ta", "/ta/b.ta", "/ta/c.ta"],
        )
        self.assertIn("Rejected b.ta: TEEC_InvokeCommand", out.getvalue())


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

    @patch("optee_helper._supplicant_serves_ta_dir", return_value=False)
    def test_system_supplicant_drops_1033_and_1039(self, _):
        out, err = self._generate()
        self.assertNotIn("test_id: 1033", out)
        self.assertNotIn("test_id: 1039", out)
        self.assertIn("test_id: 4101", out)
        self.assertIn("skipping regression 1033", err)
        self.assertIn("skipping regression 1039", err)

    @patch("optee_helper._supplicant_serves_ta_dir", return_value=True)
    def test_snap_supplicant_keeps_every_case(self, _):
        out, err = self._generate()
        self.assertIn("test_id: 1033", out)
        self.assertIn("test_id: 1039", out)
        self.assertEqual(err, "")


if __name__ == "__main__":
    unittest.main()
