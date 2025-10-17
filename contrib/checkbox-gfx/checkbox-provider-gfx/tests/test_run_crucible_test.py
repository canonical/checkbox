import io
import sys
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch, Mock

from run_crucible_test import run_crucible, SUCCESS_MARKER


class TestCrucibleRunner(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.out_path = Path(self.tmpdir.name) / "crucible_out.txt"

        # Capture printed output for assertions
        self._stdout = sys.stdout
        sys.stdout = io.StringIO()

    def tearDown(self):
        sys.stdout = self._stdout
        self.tmpdir.cleanup()

    @patch("run_crucible_test.subprocess.run")
    def test_run_crucible_passes_on_success_marker(self, mock_run):
        # Simulate crucible stdout that includes the success marker
        mock_run.return_value = Mock(
            stdout=f"some lines...\n{SUCCESS_MARKER}\nmore lines...\n",
            returncode=0,
        )

        passed = run_crucible(
            "func.depthstencil.stencil-triangles.clear-0x17.ref-0x17.compare-op-always",
            crucible_dir=Path("/fake/dir"),
            xdg_runtime_dir="/fake/runtime",
            out_path=self.out_path,
            use_fork=True,
        )

        self.assertTrue(passed, "Expected run to pass when success marker is present.")
        # Output file should be cleaned up
        self.assertFalse(self.out_path.exists(), "Output file should be removed after run.")
        # Stdout should include the content that was written (and then 'cat'-ed)
        printed = sys.stdout.getvalue()
        self.assertIn(SUCCESS_MARKER, printed)

        # Verify we invoked crucible with expected args
        args, kwargs = mock_run.call_args
        self.assertIn("--fork", args[0], "Expected --fork in command arguments.")

        # Check env and cwd were set
        self.assertEqual(kwargs["cwd"], "/fake/dir")
        self.assertEqual(kwargs["env"]["XDG_RUNTIME_DIR"], "/fake/runtime")

    @patch("run_crucible_test.subprocess.run")
    def test_run_crucible_fails_without_success_marker(self, mock_run):
        mock_run.return_value = Mock(
            stdout="some lines...\ncrucible: info   : fail 2\nmore lines...\n",
            returncode=1,
        )

        passed = run_crucible(
            "some.test",
            crucible_dir=Path("/fake/dir"),
            xdg_runtime_dir="/fake/runtime",
            out_path=self.out_path,
            use_fork=False,  # also exercise the no-fork path
        )

        self.assertFalse(passed, "Expected run to fail when success marker is absent.")
        self.assertFalse(self.out_path.exists(), "Output file should be removed after run.")

        # Verify we *didn't* include --fork
        args, _ = mock_run.call_args
        self.assertNotIn("--fork", args[0], "Did not expect --fork in command arguments.")

    @patch("run_crucible_test.subprocess.run")
    def test_run_crucible_prints_entire_stdout(self, mock_run):
        fake_output = "line1\nline2\nline3\n"
        mock_run.return_value = Mock(stdout=fake_output, returncode=0)

        _ = run_crucible(
            "another.test",
            crucible_dir=Path("/fake/dir"),
            xdg_runtime_dir="/fake/runtime",
            out_path=self.out_path,
        )

        printed = sys.stdout.getvalue()
        self.assertEqual(printed.endswith(fake_output), True, "Printed output should match crucible stdout")

if __name__ == "__main__":
    unittest.main()
