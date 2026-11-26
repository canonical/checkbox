import subprocess
import tempfile
import unittest
from pathlib import Path

import yaml


class TestThermaldJob(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        job_file = (
            Path(__file__).resolve().parents[1]
            / "units/Iiotg/thermal_jobs.yaml"
        )
        with job_file.open() as stream:
            jobs = list(yaml.safe_load_all(stream))
        cls.job = next(
            job for job in jobs if job.get("id") == "iiotg-thermal/thermald"
        )

    def test_declares_host_os_environment(self):
        self.assertIn("CHECKBOX_OS_IS_UBUNTUCORE", self.job.get("environ", []))

    def test_checks_thermald_for_host_os(self):
        cases = [
            (False, False, 0, 0),
            (False, True, 0, 0),
            (True, False, 3, 0),
            (True, True, 3, 0),
            (False, True, 3, 3),
            (True, True, 0, 1),
        ]
        with tempfile.TemporaryDirectory() as temp_dir:
            systemctl = Path(temp_dir) / "systemctl"
            systemctl.write_text('#!/bin/sh\nexit "$TEST_SYSTEMCTL_STATUS"\n')
            systemctl.chmod(0o755)
            journalctl = Path(temp_dir) / "journalctl"
            journalctl.write_text("#!/bin/sh\nexit 0\n")
            journalctl.chmod(0o755)
            for on_core, strict_snap, status, expected in cases:
                with self.subTest(
                    on_core=on_core, strict_snap=strict_snap, status=status
                ):
                    environ = {
                        "PATH": temp_dir,
                        "TEST_SYSTEMCTL_STATUS": str(status),
                    }
                    if on_core:
                        environ["CHECKBOX_OS_IS_UBUNTUCORE"] = "1"
                    if strict_snap:
                        environ["CHECKBOX_RUNNING_STRICT_SNAP"] = "1"
                    result = subprocess.run(
                        ["/bin/sh", "-c", self.job["command"]],
                        env=environ,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        universal_newlines=True,
                    )
                    self.assertEqual(
                        result.returncode, expected, result.stderr
                    )
