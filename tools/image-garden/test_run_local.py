import argparse
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import run_local


class RunLocalTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.launcher = self.root / "launcher.conf"
        self.launcher.write_text("[launcher]\n")

    def tearDown(self):
        self.temp_dir.cleanup()

    def args(self, **kwargs):
        values = {
            "launcher": self.launcher,
            "series": "24",
            "channel": "edge",
            "snap_file": None,
        }
        values.update(kwargs)
        return argparse.Namespace(**values)

    @patch.object(run_local.subprocess, "run")
    @patch.object(run_local.patch_checkbox_snap, "main")
    def test_stages_launcher_and_runs_spread(self, mock_patch_snap, mock_run):
        with patch.object(run_local, "PROJECT_DIR", self.root):
            run_local.run(self.args())

        self.assertEqual(
            (self.root / "local_run_24/launcher.conf").read_text(),
            "[launcher]\n",
        )
        mock_patch_snap.assert_called_once_with(
            snap="checkbox24",
            channel="edge",
            repo_root_path=self.root,
            output_dir=self.root / "local_run_24/checkbox24",
            force=True,
            snap_file=None,
        )
        mock_run.assert_called_once_with(
            [
                "image-garden.spread",
                "-vv",
                f"-artifacts={self.root / 'local_run_24/artifacts'}",
                "garden:ubuntu-core-24:tests/run-patched-snap",
            ],
            check=True,
        )

    def test_rejects_invalid_series(self):
        with self.assertRaisesRegex(ValueError, "invalid Ubuntu Core series"):
            run_local.run(self.args(series="25"))

    def test_rejects_missing_launcher(self):
        with self.assertRaisesRegex(FileNotFoundError, "launcher"):
            run_local.run(self.args(launcher=self.root / "missing.conf"))


if __name__ == "__main__":
    unittest.main()
