import unittest

import check_submission


class CheckSubmissionTests(unittest.TestCase):
    def setUp(self):
        self.submission = {
            "results": [
                {
                    "id": "smoke-pass",
                    "outcome": "pass",
                    "io_log": "SMOKE_PASS\n",
                },
                {
                    "id": "smoke-fail",
                    "outcome": "fail",
                    "io_log": "SMOKE_FAIL\n",
                },
            ]
        }

    def test_passes_when_outcomes_and_output_match(self):
        golden = [
            {
                "id": "smoke-pass",
                "outcome": "pass",
                "output_contains": "SMOKE_PASS",
            },
            {"id": "smoke-fail", "outcome": "fail"},
        ]

        failures = check_submission.check_submission(
            golden, self.submission
        )

        self.assertEqual(failures, [])

    def test_fails_when_job_missing_from_submission(self):
        golden = [{"id": "smoke-missing", "outcome": "pass"}]

        failures = check_submission.check_submission(
            golden, self.submission
        )

        self.assertEqual(
            failures, ["smoke-missing: missing from submission"]
        )

    def test_fails_when_outcome_mismatches(self):
        golden = [{"id": "smoke-pass", "outcome": "fail"}]

        failures = check_submission.check_submission(
            golden, self.submission
        )

        self.assertEqual(len(failures), 1)
        self.assertIn("expected outcome 'fail'", failures[0])
        self.assertIn("got 'pass'", failures[0])

    def test_fails_when_output_does_not_contain_expected_substring(self):
        golden = [
            {
                "id": "smoke-pass",
                "outcome": "pass",
                "output_contains": "MISSING_MARKER",
            }
        ]

        failures = check_submission.check_submission(
            golden, self.submission
        )

        self.assertEqual(len(failures), 1)
        self.assertIn("expected output to contain", failures[0])


if __name__ == "__main__":
    unittest.main()
