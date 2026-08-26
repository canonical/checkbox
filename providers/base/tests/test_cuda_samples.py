#!/usr/bin/env python3
# This file is part of Checkbox.
#
# Copyright 2026 Canonical Ltd.
# Written by:
#   Isaac Yang <isaac.yang@canonical.com>
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

import io
import json
import os
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import cuda_samples


def make_tree(root, samples, binary_at=None):
    """Create a fake cuda-samples tree.

    samples: list of (category, name); binary_at: callable mapping
    (category, name) to the binary path to create, or None.
    """
    for category, name in samples:
        os.makedirs(
            os.path.join(root, "Samples", category, name), exist_ok=True
        )
        path = binary_at(category, name) if binary_at else None
        if path:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w") as stream:
                stream.write("#!/bin/sh\n")
            os.chmod(path, 0o755)


class ResolveRootTests(unittest.TestCase):
    def test_env_path_wins(self):
        with tempfile.TemporaryDirectory() as tmp:
            make_tree(tmp, [("0_Introduction", "deviceQuery")])
            with patch.dict(os.environ, {"CUDA_SAMPLES_PATH": tmp}):
                self.assertEqual(
                    cuda_samples.resolve_root(), os.path.realpath(tmp)
                )

    def test_explicit_path_wins_over_env(self):
        with tempfile.TemporaryDirectory() as tmp:
            make_tree(tmp, [("0_Introduction", "deviceQuery")])
            with patch.dict(os.environ, {"CUDA_SAMPLES_PATH": "/nonexistent"}):
                self.assertEqual(
                    cuda_samples.resolve_root(tmp), os.path.realpath(tmp)
                )

    def test_no_tree_raises_with_candidates(self):
        with patch.dict(os.environ, {"CUDA_SAMPLES_PATH": "/nonexistent"}):
            with patch.object(cuda_samples.glob, "glob", return_value=[]):
                with self.assertRaises(SystemExit) as ctx:
                    cuda_samples.resolve_root()
        self.assertIn("/nonexistent", str(ctx.exception))
        self.assertIn("prebuilt-only", str(ctx.exception))
        # An explicit CUDA_SAMPLES_PATH is authoritative: no silent
        # fallback to the default roots.
        self.assertNotIn(cuda_samples.CLASSIC_DEFAULT_ROOT, str(ctx.exception))


class DiscoveryTests(unittest.TestCase):
    def test_discover_and_find_binary_all_layouts(self):
        layouts = {
            # Makefile era, binary in the sample dir
            ("0_Introduction", "deviceQuery"): lambda root: os.path.join(
                root,
                "Samples",
                "0_Introduction",
                "deviceQuery",
                "deviceQuery",
            ),
            # Makefile era, binary only in the release dir
            ("1_Utilities", "bandwidthTest"): lambda root: os.path.join(
                root,
                "bin",
                "x86_64",
                "linux",
                "release",
                "bandwidthTest",
            ),
            # cmake era
            ("3_CUDA_Features", "cdpSimplePrint"): lambda root: os.path.join(
                root,
                "build",
                "Samples",
                "3_CUDA_Features",
                "cdpSimplePrint",
                "cdpSimplePrint",
            ),
        }
        with tempfile.TemporaryDirectory() as tmp:
            make_tree(
                tmp,
                list(layouts) + [("2_Concepts_and_Techniques", "notBuilt")],
                binary_at=lambda c, n: (
                    layouts[(c, n)](tmp) if (c, n) in layouts else None
                ),
            )
            with patch.object(
                cuda_samples.platform, "machine", return_value="x86_64"
            ):
                found = {
                    (category, name): cuda_samples.find_binary(
                        tmp, category, name
                    )
                    for category, name in cuda_samples.discover_samples(tmp)
                }
        self.assertEqual(len(found), 4)
        for key, layout in layouts.items():
            self.assertEqual(found[key], layout(tmp))
        self.assertIsNone(found[("2_Concepts_and_Techniques", "notBuilt")])

    def test_nested_platform_category(self):
        with tempfile.TemporaryDirectory() as tmp:
            make_tree(
                tmp,
                [
                    ("0_Introduction", "deviceQuery"),
                    ("8_Platform_Specific/Tegra", "cuDLAHybridMode"),
                ],
                binary_at=lambda c, n: os.path.join(tmp, "Samples", c, n, n),
            )
            samples = list(cuda_samples.discover_samples(tmp))
            self.assertIn(
                ("8_Platform_Specific/Tegra", "cuDLAHybridMode"), samples
            )
            # The platform dir itself is not a sample.
            self.assertNotIn(("8_Platform_Specific", "Tegra"), samples)
            self.assertTrue(
                cuda_samples.find_binary(
                    tmp, "8_Platform_Specific/Tegra", "cuDLAHybridMode"
                )
            )

    def test_snap_root_is_a_candidate(self):
        with patch.dict(os.environ, {}, clear=True):
            with patch.object(
                cuda_samples.glob,
                "glob",
                return_value=["/snap/tegra-samples/current/cuda-samples"],
            ) as glob_mock:
                self.assertEqual(
                    cuda_samples.candidate_roots(),
                    [
                        cuda_samples.CLASSIC_DEFAULT_ROOT,
                        "/snap/tegra-samples/current/cuda-samples",
                    ],
                )
        glob_mock.assert_called_once_with(cuda_samples.SNAP_ROOT_GLOB)

    def test_build_machinery_dirs_are_not_samples(self):
        with tempfile.TemporaryDirectory() as tmp:
            make_tree(
                tmp,
                [
                    ("0_Introduction", "deviceQuery"),
                    # in-source cmake build drops these everywhere
                    ("0_Introduction", "CMakeFiles"),
                    ("CMakeFiles", "3.28.3"),
                    ("0_Introduction", ".vs"),
                ],
            )
            self.assertEqual(
                list(cuda_samples.discover_samples(tmp)),
                [("0_Introduction", "deviceQuery")],
            )

    def test_non_executable_is_not_a_binary(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(
                tmp, "Samples", "0_Introduction", "deviceQuery", "deviceQuery"
            )
            make_tree(
                tmp,
                [("0_Introduction", "deviceQuery")],
                binary_at=lambda c, n: path,
            )
            os.chmod(path, 0o644)
            self.assertIsNone(
                cuda_samples.find_binary(tmp, "0_Introduction", "deviceQuery")
            )


class ExcludeTests(unittest.TestCase):
    def _load(self, payload):
        with tempfile.NamedTemporaryFile("w", suffix=".json") as stream:
            json.dump(payload, stream)
            stream.flush()
            with patch.dict(
                os.environ, {"CUDA_SAMPLES_EXCLUDE_FILE": stream.name}
            ):
                return cuda_samples.load_excludes()

    def test_valid_file(self):
        excludes = self._load(
            {"excludes": [{"name": "simpleGLES", "reason": "headless"}]}
        )
        self.assertEqual(
            cuda_samples.exclude_reason(
                excludes, "5_Domain_Specific", "simpleGLES"
            ),
            "headless",
        )
        self.assertIsNone(
            cuda_samples.exclude_reason(
                excludes, "0_Introduction", "deviceQuery"
            )
        )

    def test_category_qualified_entry(self):
        excludes = [{"name": "simple", "category": "7_libNVVM", "reason": "x"}]
        self.assertEqual(
            cuda_samples.exclude_reason(excludes, "7_libNVVM", "simple"), "x"
        )
        self.assertIsNone(
            cuda_samples.exclude_reason(excludes, "0_Introduction", "simple")
        )

    def test_invalid_shape_raises(self):
        for payload in (
            [],
            {"excludes": [{"name": "x"}]},
            # unknown key (e.g. a typo for 'category')
            {"excludes": [{"name": "x", "reason": "y", "categorey": "z"}]},
            # non-string values must be rejected, not silently ignored
            {"excludes": [{"name": "x", "reason": "y", "category": 7}]},
            {"excludes": [{"name": 3, "reason": "y"}]},
        ):
            with self.assertRaises(SystemExit):
                self._load(payload)

    def test_explicit_missing_file_raises(self):
        with patch.dict(
            os.environ, {"CUDA_SAMPLES_EXCLUDE_FILE": "/nonexistent.json"}
        ):
            with self.assertRaises(SystemExit):
                cuda_samples.load_excludes()

    def test_missing_default_is_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = {"PLAINBOX_PROVIDER_DATA": tmp}
            with patch.dict(os.environ, env, clear=True):
                self.assertEqual(cuda_samples.load_excludes(), [])

    def test_shipped_default_validates(self):
        data_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "data",
        )
        with patch.dict(
            os.environ, {"PLAINBOX_PROVIDER_DATA": data_dir}, clear=True
        ):
            excludes = cuda_samples.load_excludes()
        names = [entry["name"] for entry in excludes]
        self.assertIn("simpleGLES", names)
        # Jetson/L4T-specific excludes live in the jetson list, not
        # the universal default (they run fine on e.g. a GB300).
        self.assertNotIn("matrixMul_nvrtc", names)

    def test_shipped_jetson_list_via_bare_name(self):
        data_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "data",
        )
        env = {
            "PLAINBOX_PROVIDER_DATA": data_dir,
            "CUDA_SAMPLES_EXCLUDE_FILE": "exclude_jobs.jetson.json",
        }
        with patch.dict(os.environ, env, clear=True):
            excludes = cuda_samples.load_excludes()
        names = [entry["name"] for entry in excludes]
        self.assertIn("matrixMul_nvrtc", names)
        self.assertIn("simpleGLES", names)

    def test_bare_name_without_provider_data_raises(self):
        env = {"CUDA_SAMPLES_EXCLUDE_FILE": "exclude_jobs.jetson.json"}
        with patch.dict(os.environ, env, clear=True):
            with self.assertRaises(SystemExit):
                cuda_samples.load_excludes()


class VersionTests(unittest.TestCase):
    def test_parse_tag(self):
        self.assertEqual(cuda_samples.parse_tag("v12.5"), (12, 5))
        self.assertEqual(cuda_samples.parse_tag("12.5"), (12, 5))
        self.assertEqual(cuda_samples.parse_tag("v13.2update"), (13, 2))
        self.assertEqual(cuda_samples.parse_tag("v12.5-3-gabc"), (12, 5))
        self.assertIsNone(cuda_samples.parse_tag("master"))

    @patch("cuda_samples.subprocess.check_output")
    def test_cuda_version(self, check_output):
        check_output.return_value = (
            "| NVIDIA-SMI 540.5.0  Driver Version: 540.5.0"
            "  CUDA Version: 12.6     |"
        )
        self.assertEqual(cuda_samples.cuda_version(), (12, 6))

    @patch("cuda_samples.subprocess.check_output")
    def test_cuda_version_unparseable_raises(self, check_output):
        check_output.return_value = "garbage"
        with self.assertRaises(SystemExit):
            cuda_samples.cuda_version()

    @patch("cuda_samples.cuda_version", return_value=(12, 6))
    @patch("cuda_samples._git")
    def test_version_match_ok(self, git, _version):
        git.side_effect = ["v12.5", "v12.5\nv13.0\nv9.2"]
        cuda_samples.check_version_match("/tree")

    @patch("cuda_samples.cuda_version", return_value=(12, 6))
    @patch("cuda_samples._git")
    def test_version_mismatch_raises(self, git, _version):
        git.side_effect = ["v13.0-3-gabc", "v12.5\nv13.0\nv9.2"]
        with self.assertRaises(SystemExit) as ctx:
            cuda_samples.check_version_match("/tree")
        self.assertIn("expected v12.5", str(ctx.exception))

    @patch("cuda_samples._git")
    def test_non_git_tree_is_skipped_with_reason(self, git):
        git.side_effect = RuntimeError("not a git repository")
        with patch("sys.stdout", new_callable=io.StringIO) as stdout:
            cuda_samples.check_version_match("/tree")
        self.assertIn("skipping the version match", stdout.getvalue())
        # The underlying git error is surfaced for triage, not hidden.
        self.assertIn("not a git repository", stdout.getvalue())

    @patch("cuda_samples._git")
    def test_broken_git_checkout_fails_readiness(self, git):
        # A tree WITH .git must not silently skip the check.
        git.side_effect = RuntimeError("fatal: bad object HEAD")
        with tempfile.TemporaryDirectory() as tmp:
            os.mkdir(os.path.join(tmp, ".git"))
            with self.assertRaises(SystemExit) as ctx:
                cuda_samples.check_version_match(tmp)
        self.assertIn("bad object HEAD", str(ctx.exception))

    @patch("cuda_samples.cuda_version", return_value=(13, 0))
    @patch("cuda_samples._git")
    def test_tag_incomplete_clone_prints_inconclusive_note(
        self, git, _version
    ):
        # current == newest tag in the clone but < CUDA version: a
        # --single-branch clone cannot prove there is no newer tag.
        git.side_effect = ["v12.5", "v12.5\nv9.2"]
        with patch("sys.stdout", new_callable=io.StringIO) as stdout:
            cuda_samples.check_version_match("/tree")
        self.assertIn("inconclusive", stdout.getvalue())

    @patch("cuda_samples.subprocess.run")
    def test_git_uses_safe_directory(self, run):
        run.return_value.returncode = 0
        run.return_value.stdout = "v12.5\n"
        cuda_samples._git("/tree", "describe", "--tags")
        argv = run.call_args[0][0]
        self.assertEqual(
            argv[:5], ["git", "-c", "safe.directory=/tree", "-C", "/tree"]
        )

    @patch("cuda_samples.cuda_version", return_value=(9, 0))
    @patch("cuda_samples._git")
    def test_no_tag_below_cuda_version_raises(self, git, _version):
        git.side_effect = ["v12.5", "v12.5\nv13.0"]
        with self.assertRaises(SystemExit) as ctx:
            cuda_samples.check_version_match("/tree")
        self.assertIn("<= CUDA version 9.0", str(ctx.exception))


class CommandTests(unittest.TestCase):
    def test_list_emits_skip_records(self):
        with tempfile.TemporaryDirectory() as tmp:
            make_tree(
                tmp,
                [
                    ("0_Introduction", "deviceQuery"),
                    ("5_Domain_Specific", "simpleGLES"),
                    ("6_Performance", "notBuiltSample"),
                ],
                binary_at=lambda c, n: (
                    None
                    if n == "notBuiltSample"
                    else os.path.join(tmp, "Samples", c, n, n)
                ),
            )
            excludes = [{"name": "simpleGLES", "reason": "headless"}]
            with patch.object(
                cuda_samples, "load_excludes", return_value=excludes
            ):
                with patch("sys.stdout", new_callable=io.StringIO) as stdout:
                    cuda_samples.main(["--path", tmp, "list"])
        records = [
            dict(
                line.split(": ", 1) if ": " in line else (line[:-1], "")
                for line in block.splitlines()
            )
            for block in stdout.getvalue().strip().split("\n\n")
        ]
        self.assertEqual(len(records), 3)
        self.assertEqual(records[0]["name"], "deviceQuery")
        self.assertEqual(records[0]["skip"], "False")
        self.assertEqual(records[0]["skip_reason"], "")
        self.assertTrue(records[0]["path"])
        self.assertEqual(records[1]["name"], "simpleGLES")
        self.assertEqual(records[1]["skip"], "True")
        self.assertEqual(records[1]["skip_reason"], "headless")
        # A sample that is present but not built is a visible skip too.
        self.assertEqual(records[2]["name"], "notBuiltSample")
        self.assertEqual(records[2]["skip"], "True")
        self.assertEqual(records[2]["skip_reason"], "not built")
        self.assertEqual(records[2]["path"], "")

    def test_run_missing_binary_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            make_tree(tmp, [("0_Introduction", "deviceQuery")])
            with self.assertRaises(SystemExit) as ctx:
                cuda_samples.main(
                    ["--path", tmp, "run", "0_Introduction", "deviceQuery"]
                )
        self.assertIn("No built binary", str(ctx.exception))

    @patch("cuda_samples.os.killpg")
    @patch("cuda_samples.subprocess.Popen")
    def test_run_timeout_kills_process_group(self, popen, killpg):
        proc = popen.return_value
        proc.pid = 1234
        # SIGKILL may not reap a process stuck in uninterruptible
        # sleep: the post-kill wait must be bounded and swallowed.
        proc.wait.side_effect = [
            subprocess.TimeoutExpired("deviceQuery", 300),
            subprocess.TimeoutExpired("deviceQuery", 10),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            make_tree(
                tmp,
                [("0_Introduction", "deviceQuery")],
                binary_at=lambda c, n: os.path.join(tmp, "Samples", c, n, n),
            )
            self.assertEqual(
                cuda_samples.main(
                    ["--path", tmp, "run", "0_Introduction", "deviceQuery"]
                ),
                1,
            )
        killpg.assert_called_once_with(1234, cuda_samples.signal.SIGKILL)
        self.assertTrue(popen.call_args[1]["start_new_session"])
        self.assertEqual(proc.wait.call_count, 2)
        self.assertIsNotNone(proc.wait.call_args_list[1][1].get("timeout"))

    @patch("cuda_samples.subprocess.Popen")
    def test_run_unexecutable_binary_is_readable_error(self, popen):
        popen.side_effect = OSError("Exec format error")
        with tempfile.TemporaryDirectory() as tmp:
            make_tree(
                tmp,
                [("0_Introduction", "deviceQuery")],
                binary_at=lambda c, n: os.path.join(tmp, "Samples", c, n, n),
            )
            with self.assertRaises(SystemExit) as ctx:
                cuda_samples.main(
                    ["--path", tmp, "run", "0_Introduction", "deviceQuery"]
                )
        self.assertIn("Cannot execute", str(ctx.exception))
        self.assertIn("deviceQuery", str(ctx.exception))

    @patch("cuda_samples.subprocess.Popen")
    def test_run_propagates_exit_code_and_uses_sandbox(self, popen):
        popen.return_value.wait.return_value = 7
        with tempfile.TemporaryDirectory() as tmp:
            make_tree(
                tmp,
                [("0_Introduction", "deviceQuery")],
                binary_at=lambda c, n: os.path.join(tmp, "Samples", c, n, n),
            )
            self.assertEqual(
                cuda_samples.main(
                    ["--path", tmp, "run", "0_Introduction", "deviceQuery"]
                ),
                7,
            )
            cwd = popen.call_args[1]["cwd"]
            # The sample runs in a disposable copy, NOT the tree (which
            # may be root-owned and must never be written to)...
            self.assertTrue(
                cwd.endswith(
                    os.path.join("Samples", "0_Introduction", "deviceQuery")
                )
            )
            self.assertFalse(cwd.startswith(os.path.realpath(tmp)))
        # ...and the sandbox is removed afterwards.
        self.assertFalse(os.path.exists(cwd))

    def test_make_sandbox_mirrors_tree_and_links_common(self):
        import shutil

        with tempfile.TemporaryDirectory() as tmp:
            make_tree(
                tmp,
                [("4_CUDA_Libraries", "boxFilterNPP")],
                binary_at=lambda c, n: os.path.join(tmp, "Samples", c, n, n),
            )
            os.makedirs(os.path.join(tmp, "Common", "data"))
            sandbox, run_dir = cuda_samples.make_sandbox(
                tmp, "4_CUDA_Libraries", "boxFilterNPP"
            )
            try:
                # The sample dir is a writable copy at the same depth,
                # and Common resolves via the tree-shaped climb.
                self.assertTrue(
                    os.path.isfile(os.path.join(run_dir, "boxFilterNPP"))
                )
                self.assertTrue(
                    os.path.isdir(
                        os.path.join(run_dir, "..", "..", "..", "Common")
                    )
                )
            finally:
                shutil.rmtree(sandbox)

    def test_run_timeout_env_must_be_numeric(self):
        with patch.dict(os.environ, {"CUDA_SAMPLES_TIMEOUT": "fast"}):
            with self.assertRaises(SystemExit):
                cuda_samples.run_timeout()

    def test_readiness_unbuilt_tree_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            make_tree(tmp, [("0_Introduction", "deviceQuery")])
            with self.assertRaises(SystemExit) as ctx:
                cuda_samples.main(["--path", tmp, "readiness"])
        self.assertIn("prebuilt-only", str(ctx.exception))

    def test_readiness_mostly_unbuilt_tree_raises(self):
        # 1 built vs 2 unbuilt: the tree looks partially built.
        with tempfile.TemporaryDirectory() as tmp:
            make_tree(
                tmp,
                [
                    ("0_Introduction", "deviceQuery"),
                    ("0_Introduction", "asyncAPI"),
                    ("1_Utilities", "topologyQuery"),
                ],
                binary_at=lambda c, n: (
                    os.path.join(tmp, "Samples", c, n, n)
                    if n == "deviceQuery"
                    else None
                ),
            )
            with patch.object(cuda_samples, "load_excludes", return_value=[]):
                with self.assertRaises(SystemExit) as ctx:
                    cuda_samples.main(["--path", tmp, "readiness"])
        self.assertIn("partially built", str(ctx.exception))


class TemplateGateTests(unittest.TestCase):
    def test_pxu_requires_gate_is_per_record(self):
        """The template's skip gate must hold per record.

        Plainbox splits an unparenthesized 'a and b' requires
        expression and evaluates each side existentially across ALL
        records, which would let every excluded sample run as long as
        any runnable sample exists.  The parenthesized form is
        evaluated whole, per record.  Evaluate the actual line from
        jobs.pxu through the real evaluator to pin this down.
        """
        try:
            from plainbox.impl.resource import Resource, ResourceExpression
        except ImportError:
            self.skipTest("plainbox not installed")
        jobs_pxu = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "units",
            "cuda",
            "jobs.pxu",
        )
        with open(jobs_pxu) as stream:
            line = next(
                row.strip()
                for row in stream
                if "cuda_samples_resource.name" in row
            )
        self.assertTrue(
            line.startswith("(") and line.endswith(")"),
            "the requires gate must be parenthesized: {}".format(line),
        )
        expr = ResourceExpression(
            line.format(name="simpleGLES", category="5_Domain_Specific")
        )
        excluded = Resource(
            {
                "name": "simpleGLES",
                "category": "5_Domain_Specific",
                "skip": "True",
            }
        )
        runnable = Resource(
            {
                "name": "deviceQuery",
                "category": "0_Introduction",
                "skip": "False",
            }
        )
        # A runnable record elsewhere must NOT unlock the excluded job.
        self.assertFalse(expr.evaluate([excluded, runnable]))
        not_excluded = Resource(
            {
                "name": "simpleGLES",
                "category": "5_Domain_Specific",
                "skip": "False",
            }
        )
        self.assertTrue(expr.evaluate([not_excluded, runnable]))


if __name__ == "__main__":
    unittest.main()
