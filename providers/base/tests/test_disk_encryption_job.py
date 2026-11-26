import subprocess
import tempfile
import unittest
from pathlib import Path

from plainbox.impl.secure.rfc822 import load_rfc822_records
from plainbox.impl.unit.job import JobDefinition


class TestDiskEncryptionJob(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        job_file = (
            Path(__file__).resolve().parents[1] / "units/disk/encryption.pxu"
        )
        records = load_rfc822_records(job_file.read_text())
        record = next(
            record
            for record in records
            if record.data.get("id") == "disk/encryption/detect"
        )
        cls.job = JobDefinition.from_rfc822_record(record)

    def test_declares_host_os_environment(self):
        self.assertIn(
            "CHECKBOX_OS_IS_UBUNTUCORE", self.job.get_environ_settings()
        )

    def test_selects_command_by_host_os(self):
        cases = [
            (False, False, "desktop"),
            (False, True, "desktop"),
            (True, False, ""),
            (True, True, ""),
        ]
        with tempfile.TemporaryDirectory() as temp_dir:
            command = Path(temp_dir) / "fde_tests.py"
            command.write_text('#!/bin/sh\nprintf "%s" "$1"\n')
            command.chmod(0o755)
            for on_core, strict_snap, expected in cases:
                with self.subTest(on_core=on_core, strict_snap=strict_snap):
                    environ = {"PATH": temp_dir}
                    if on_core:
                        environ["CHECKBOX_OS_IS_UBUNTUCORE"] = "1"
                    if strict_snap:
                        environ["CHECKBOX_RUNNING_STRICT_SNAP"] = "1"
                    output = subprocess.check_output(
                        ["/bin/sh", "-c", self.job.command],
                        env=environ,
                        universal_newlines=True,
                    )
                    self.assertEqual(output, expected)
