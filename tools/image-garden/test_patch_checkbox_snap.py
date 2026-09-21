import argparse
import contextlib
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import patch_checkbox_snap


class PatchCheckboxSnapTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.repo = self.root / "repo"
        self.snap = self.root / "snap"
        self.repo.mkdir()
        (self.repo / "providers").mkdir()
        self.site_packages = self.snap / "lib/python3.12/site-packages"
        for name in patch_checkbox_snap.PYTHON_PACKAGES.values():
            (self.site_packages / name).mkdir(parents=True)

    def tearDown(self):
        self.temp_dir.cleanup()

    def make_file(self, path, text="content"):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)

    def make_package_sources(self):
        # sync_dirs requires every python package source to exist, plus
        # the metabox provider, which is always synced.
        for source in patch_checkbox_snap.PYTHON_PACKAGES:
            (self.repo / source).mkdir(parents=True, exist_ok=True)
        (self.repo / patch_checkbox_snap.METABOX_PROVIDER[0]).mkdir(
            parents=True, exist_ok=True
        )

    @contextlib.contextmanager
    def patched_subprocess(self, output_dir, downloaded=None):
        # Fakes "git rev-parse", "snap download" and "unsquashfs" so
        # patch_snap() can run without touching the network or the
        # filesystem outside of self.root.
        def fake_check_output(command, cwd=None, text=None, stderr=None):
            return str(self.repo) + "\n"

        def fake_run(command, cwd=None, check=None):
            if command[:2] == ["snap", "download"]:
                if downloaded is not None:
                    downloaded.append(command[2])
                self.make_file(Path(cwd) / "download.snap")
            elif command[0] == "unsquashfs":
                site_packages = output_dir / "lib/python3.12/site-packages"
                for name in patch_checkbox_snap.PYTHON_PACKAGES.values():
                    (site_packages / name).mkdir(parents=True, exist_ok=True)
            else:
                raise AssertionError(command)
            return argparse.Namespace(returncode=0)

        with patch.object(
            patch_checkbox_snap.subprocess,
            "check_output",
            side_effect=fake_check_output,
        ), patch.object(
            patch_checkbox_snap.subprocess, "run", side_effect=fake_run
        ):
            yield

    def test_overlays_checkbox_ng_package(self):
        self.make_package_sources()
        self.make_file(self.repo / "checkbox-ng/checkbox_ng/foo.py", "new")
        self.make_file(self.site_packages / "checkbox_ng/stale.py", "stale")

        patch_checkbox_snap.sync_dirs(self.repo, self.snap)

        self.assertEqual(
            (self.site_packages / "checkbox_ng/foo.py").read_text(), "new"
        )
        self.assertEqual(
            (self.site_packages / "checkbox_ng/stale.py").read_text(), "stale"
        )

    def test_syncs_plainbox_and_checkbox_support(self):
        self.make_package_sources()
        self.make_file(
            self.repo / "checkbox-ng/plainbox/impl/foo.py", "plainbox"
        )
        self.make_file(
            self.repo / "checkbox-support/checkbox_support/foo.py", "support"
        )

        patch_checkbox_snap.sync_dirs(self.repo, self.snap)

        self.assertEqual(
            (self.site_packages / "plainbox/impl/foo.py").read_text(),
            "plainbox",
        )
        self.assertEqual(
            (self.site_packages / "checkbox_support/foo.py").read_text(),
            "support",
        )

    def test_syncs_every_matching_dir_in_the_snap(self):
        self.make_package_sources()
        other = self.snap / "usr/lib/python3/dist-packages/checkbox_ng"
        other.mkdir(parents=True)
        self.make_file(self.repo / "checkbox-ng/checkbox_ng/foo.py", "new")

        patch_checkbox_snap.sync_dirs(self.repo, self.snap)

        self.assertEqual(
            (self.site_packages / "checkbox_ng/foo.py").read_text(), "new"
        )
        self.assertEqual((other / "foo.py").read_text(), "new")

    def test_adds_metabox_provider(self):
        # Metabox is a testing provider, never shipped in production
        # snaps, so add its files and provider descriptor.
        self.make_package_sources()
        self.make_file(
            self.repo / "metabox/metabox/metabox-provider/units/jobs.yaml",
            "metabox jobs",
        )

        patch_checkbox_snap.sync_dirs(self.repo, self.snap)

        destination = self.snap / "providers/checkbox-provider-metabox"
        self.assertEqual(
            (destination / "units/jobs.yaml").read_text(), "metabox jobs"
        )
        manifest = "2021.com.canonical.certification.metabox.provider"
        self.assertEqual(
            (destination / manifest).read_text(),
            (
                patch_checkbox_snap.METABOX_PROVIDER_EXTRA / manifest
            ).read_text(),
        )

    def test_fails_when_package_is_not_found_in_snap(self):
        self.make_package_sources()
        snap = self.root / "empty-snap"
        snap.mkdir()

        with self.assertRaisesRegex(ValueError, "checkbox_ng"):
            patch_checkbox_snap.sync_dirs(self.repo, snap)

    def test_fails_when_source_dir_is_missing(self):
        with self.assertRaises(FileNotFoundError):
            patch_checkbox_snap.sync_dirs(self.repo, self.snap)

    def test_repo_root_prefers_git_top_level(self):
        subdir = self.repo / "checkbox-ng"
        subdir.mkdir()
        subprocess.run(
            ["git", "init", "-q", str(self.repo)],
            check=True,
        )

        self.assertEqual(
            patch_checkbox_snap.repo_root(subdir), self.repo.resolve()
        )

    def test_repo_root_falls_back_without_git(self):
        # Spread syncs the repo without ".git", so patching must still
        # work from a plain directory.
        self.assertEqual(
            patch_checkbox_snap.repo_root(self.repo), self.repo.resolve()
        )

    def test_overlays_provider_present_in_snap(self):
        self.make_package_sources()
        self.make_file(
            self.repo / "providers/base/units/jobs.yaml", "new jobs"
        )
        self.make_file(
            self.snap / "providers/checkbox-provider-base"
            / "checkbox-provider-base.provider",
            "generated metadata",
        )

        synced = patch_checkbox_snap.sync_dirs(self.repo, self.snap)

        destination = self.snap / "providers/checkbox-provider-base"
        self.assertIn(destination, synced)
        self.assertEqual(
            (destination / "units/jobs.yaml").read_text(), "new jobs"
        )
        self.assertEqual(
            (destination / "checkbox-provider-base.provider").read_text(),
            "generated metadata",
        )

    def test_skips_provider_absent_from_snap(self):
        self.make_package_sources()
        self.make_file(self.repo / "providers/docker/units/jobs.yaml")

        synced = patch_checkbox_snap.sync_dirs(self.repo, self.snap)

        destination = self.snap / "providers/checkbox-provider-docker"
        self.assertNotIn(destination, synced)
        self.assertFalse(destination.exists())

    def test_patch_snap_downloads_and_unsquashes(self):
        # --series should derive the snap name, and the download/unsquash
        # path should end with the repo content synced into the snap.
        output = self.root / "patched"
        self.make_package_sources()
        self.make_file(self.repo / "checkbox-ng/checkbox_ng/foo.py", "new")
        downloaded = []

        with self.patched_subprocess(output, downloaded=downloaded):
            patch_checkbox_snap.patch_snap(
                series="24",
                channel="edge",
                output_dir=output,
                repo_root_path=self.repo,
            )

        self.assertEqual(downloaded, ["checkbox24"])
        self.assertEqual(
            (
                output / "lib/python3.12/site-packages/checkbox_ng/foo.py"
            ).read_text(),
            "new",
        )

    def test_patch_snap_defaults_output_dir_to_snap_name(self):
        self.make_package_sources()
        cwd = self.root / "cwd"
        cwd.mkdir()
        output = cwd / "checkbox24"

        previous_cwd = Path.cwd()
        os.chdir(cwd)
        try:
            with self.patched_subprocess(output):
                patch_checkbox_snap.patch_snap(
                    snap="checkbox24",
                    channel="edge",
                    repo_root_path=self.repo,
                )
        finally:
            os.chdir(previous_cwd)

        self.assertTrue(output.is_dir())

    def test_patch_snap_uses_local_snap_file(self):
        # A local snap file should be unsquashed directly, without
        # invoking "snap download".
        self.make_package_sources()
        output = self.root / "patched"
        snap_file = self.root / "local.snap"
        self.make_file(snap_file)

        with self.patched_subprocess(output):
            patch_checkbox_snap.patch_snap(
                snap="checkbox24",
                channel="edge",
                snap_file=snap_file,
                output_dir=output,
                repo_root_path=self.repo,
            )

        self.assertTrue(output.is_dir())

    def test_main_accepts_keyword_arguments(self):
        with patch.object(patch_checkbox_snap, "patch_snap") as mock_patch:
            patch_checkbox_snap.main(
                snap="checkbox24",
                channel="edge",
                output_dir=self.root / "patched",
                repo_root_path=self.repo,
                force=True,
            )

        mock_patch.assert_called_once_with(
            snap="checkbox24",
            channel="edge",
            output_dir=self.root / "patched",
            repo_root_path=self.repo,
            force=True,
        )


if __name__ == "__main__":
    unittest.main()
