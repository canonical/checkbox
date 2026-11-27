import os
import tempfile
import unittest
from unittest.mock import patch

import canary_results

JOBS = [
    {"name": "Wait for the edge packages", "conclusion": "success"},
    {"name": "uc22-amd64 on hp-1", "conclusion": "success"},
    {"name": "uc22-amd64 on hp-2", "conclusion": "failure"},
    {"name": "uc24-arm64 on rpi4", "conclusion": "failure"},
    {"name": "uc24-arm64 on rpi400-arm64", "conclusion": "failure"},
    {"name": "Check if a retry is needed", "conclusion": "success"},
]


class CanaryResultsTests(unittest.TestCase):
    def run_stage(self, stage, jobs):
        with tempfile.TemporaryDirectory() as tmp:
            env = {
                "GITHUB_OUTPUT": os.path.join(tmp, "output"),
                "GITHUB_STEP_SUMMARY": os.path.join(tmp, "summary"),
            }
            with patch.dict(os.environ, env), patch.object(
                canary_results, "get_jobs", return_value=jobs
            ), patch("builtins.print"):
                code = canary_results.main([stage])
            with open(env["GITHUB_OUTPUT"]) as f:
                output = f.read()
            with open(env["GITHUB_STEP_SUMMARY"]) as f:
                summary = f.read()
        return code, output, summary

    def test_check_retries_platforms_without_passing_jobs(self):
        code, output, summary = self.run_stage("check", JOBS)
        self.assertEqual(code, 0)
        self.assertEqual(output, 'retry=["uc24-arm64"]\n')
        self.assertIn("retrying rpi4 and rpi400-arm64 in 30 minutes", summary)

    def test_result_accepts_when_every_platform_passed(self):
        jobs = JOBS + [
            {"name": "uc24-arm64 on rpi4 (retry)", "conclusion": "success"},
            # Skipped retry jobs are not expanded and keep the raw name
            {
                "name": "${{ matrix.platform }} on ${{ matrix.queue }} "
                "(retry)",
                "conclusion": "skipped",
            },
        ]
        code, output, summary = self.run_stage("result", jobs)
        self.assertEqual(code, 0)
        self.assertEqual(output, "retry=[]\n")
        self.assertIn("at least one job passed on each platform", summary)

    def test_result_rejects_when_a_platform_never_passed(self):
        jobs = JOBS + [
            {"name": "uc24-arm64 on rpi4 (retry)", "conclusion": "failure"},
        ]
        code, _, summary = self.run_stage("result", jobs)
        self.assertEqual(code, 1)
        self.assertIn("Rejected, no job passed in either attempt", summary)


if __name__ == "__main__":
    unittest.main()
