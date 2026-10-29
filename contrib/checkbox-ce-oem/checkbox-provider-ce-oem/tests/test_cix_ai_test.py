import argparse
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import cix_ai_test as cat

GOOD = f"{cat.PASS_LINE}\n"


def make_args(tool: str, **kwargs) -> argparse.Namespace:
    values = {
        "tool": tool,
        "testdata": "/data",
        "frames": 2,
        "timeout": 5,
    }
    values.update(kwargs)
    return argparse.Namespace(**values)


class TestVerify(unittest.TestCase):
    def test_pass(self):
        self.assertEqual(cat.verify("batch", GOOD, 0, 1), [])

    def test_rc_zero_but_error_line(self):
        out = "[Err] noe_ioctl (config clusters)\n" + GOOD
        problems = cat.verify("batch", out, 0, 1)
        self.assertEqual(len(problems), 1)

    def test_nonzero_rc(self):
        self.assertTrue(cat.verify("batch", GOOD, 1, 1))

    def test_missing_pass_line(self):
        self.assertTrue(cat.verify("batch", "nothing", 0, 1))

    def test_no_pass_line_tool(self):
        self.assertEqual(cat.verify("flush_job", "done", 0, 1), [])

    def test_benchmark_frame_count(self):
        self.assertEqual(cat.verify("benchmark", GOOD * 2, 0, 2), [])
        self.assertTrue(cat.verify("benchmark", GOOD, 0, 2))

    def test_profiler_expected_line(self):
        self.assertTrue(cat.verify("profiler", "", 0, 1))
        out = "get profiler tensor success\n"
        self.assertEqual(cat.verify("profiler", out, 0, 1), [])


class TestCheckEnv(unittest.TestCase):
    def test_missing_binary(self):
        with patch.object(cat, "BIN_DIR", Path("/nonexistent")):
            with self.assertRaises(SystemExit) as cm:
                cat.check_env("batch", Path("/data"))
        self.assertIn("ENV ERROR", str(cm.exception))

    def test_missing_testdata(self):
        with patch.object(Path, "is_file", side_effect=[True, False]):
            with self.assertRaises(SystemExit) as cm:
                cat.check_env("batch", Path("/data"))
        self.assertIn("ENV ERROR", str(cm.exception))


class TestRunTool(unittest.TestCase):
    @patch.dict("os.environ", {}, clear=True)
    @patch("cix_ai_test.check_env", return_value=Path("/bin/noe_batch"))
    @patch("cix_ai_test.subprocess.run")
    def test_pass(self, mock_run, _env):
        mock_run.return_value = MagicMock(stdout=GOOD, returncode=0)
        cat.run_tool(make_args("batch"))
        env = mock_run.call_args.kwargs["env"]
        self.assertEqual(env["LD_LIBRARY_PATH"], str(cat.LIB_DIR))

    @patch("cix_ai_test.check_env", return_value=Path("/bin/noe_batch"))
    @patch("cix_ai_test.subprocess.run")
    def test_fail(self, mock_run, _env):
        mock_run.return_value = MagicMock(stdout="[Err] x", returncode=0)
        with self.assertRaises(SystemExit):
            cat.run_tool(make_args("batch"))

    @patch("cix_ai_test.os.geteuid", return_value=1000)
    @patch("cix_ai_test.check_env", return_value=Path("/bin/noe_dfs"))
    def test_dfs_needs_root(self, _env, _uid):
        with self.assertRaises(SystemExit) as cm:
            cat.run_tool(make_args("dfs"))
        self.assertIn("root", str(cm.exception))


class TestBuildEnv(unittest.TestCase):
    @patch.dict("os.environ", {}, clear=True)
    def test_default(self):
        env = cat.build_env()
        self.assertEqual(env["LD_LIBRARY_PATH"], str(cat.LIB_DIR))

    @patch.dict(
        "os.environ",
        {"CIX_NOE_LIB_DIR": "/snap/x", "LD_LIBRARY_PATH": "/old"},
        clear=True,
    )
    def test_override_and_keep_existing(self):
        self.assertEqual(cat.build_env()["LD_LIBRARY_PATH"], "/snap/x:/old")


class TestRestoreGovernor(unittest.TestCase):
    def test_restored_on_error(self):
        gov = MagicMock()
        gov.read_text.return_value = "simple_ondemand\n"
        with patch.object(cat, "DEVFREQ_GOVERNOR", gov):
            with self.assertRaises(RuntimeError):
                with cat.restore_governor():
                    raise RuntimeError
        self.assertEqual(
            [c.args[0] for c in gov.write_text.call_args_list],
            ["userspace", "simple_ondemand"],
        )
