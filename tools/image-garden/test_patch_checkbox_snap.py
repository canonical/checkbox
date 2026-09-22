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
        self.site_packages.mkdir(parents=True)

        for source in patch_checkbox_snap.PYTHON_PACKAGES:
            (self.repo / source).mkdir(parents=True)
        (self.repo / "providers/base/units").mkdir(parents=True)
        (self.repo / "providers/docker/units").mkdir(parents=True)
        (self.repo / "metabox/metabox/metabox-provider/units").mkdir(parents=True)

        for name in patch_checkbox_snap.PYTHON_PACKAGES.values():
            (self.site_packages / name).mkdir(parents=True)
        (self.snap / "providers/checkbox-provider-base").mkdir(parents=True)

    def tearDown(self):
        self.temp_dir.cleanup()

    def write_file(self, path, text="content"):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)

    def test_sync_dirs_patches_packages_and_providers(self):
        self.write_file(self.repo / "checkbox-ng/checkbox_ng/foo.py")
        self.write_file(self.repo / "checkbox-ng/plainbox/foo.py")
        self.write_file(self.repo / "checkbox-support/checkbox_support/foo.py")
        self.write_file(self.repo / "providers/base/units/jobs.yaml")
        self.write_file(self.repo / "providers/docker/units/jobs.yaml")
        self.write_file(self.repo / "metabox/metabox/metabox-provider/units/jobs.yaml")

        patch_checkbox_snap.sync_dirs(self.repo, self.snap)

        self.assertTrue((self.site_packages / "checkbox_ng/foo.py").is_file())
        self.assertTrue((self.site_packages / "plainbox/foo.py").is_file())
        self.assertTrue((self.site_packages / "checkbox_support/foo.py").is_file())
        self.assertTrue(
            (self.snap / "providers/checkbox-provider-base/units/jobs.yaml").is_file()
        )
        self.assertFalse((self.snap / "providers/checkbox-provider-docker").exists())
        self.assertTrue(
            (
                self.snap / "providers/checkbox-provider-metabox/units/jobs.yaml"
            ).is_file()
        )
        self.assertTrue(
            (
                self.snap
                / "providers/checkbox-provider-metabox"
                / "2021.com.canonical.certification.metabox.provider"
            ).is_file()
        )

    def test_patch_snap_uses_local_snap_file(self):
        snap_file = self.root / "checkbox24.snap"
        self.write_file(snap_file)
        output = self.root / "patched"

        def fake_unsquash(source, destination):
            self.assertEqual(source, snap_file)
            for name in patch_checkbox_snap.PYTHON_PACKAGES.values():
                (destination / f"lib/python3.12/site-packages/{name}").mkdir(
                    parents=True
                )
            (destination / "providers/checkbox-provider-base").mkdir(parents=True)

        with patch.object(patch_checkbox_snap, "unsquash", fake_unsquash):
            patch_checkbox_snap.patch_snap(
                snap="checkbox24",
                snap_file=snap_file,
                output_dir=output,
                repo_root_path=self.repo,
            )

        self.assertTrue((output / "providers/checkbox-provider-metabox").is_dir())

    def test_patch_snap_requires_force_for_existing_output(self):
        output = self.root / "patched"
        output.mkdir()

        with self.assertRaises(FileExistsError):
            patch_checkbox_snap.patch_snap(
                snap="checkbox24",
                snap_file=self.root / "checkbox24.snap",
                output_dir=output,
                repo_root_path=self.repo,
            )


if __name__ == "__main__":
    unittest.main()
