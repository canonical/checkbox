import shlex
import unittest

from unittest.mock import MagicMock, patch, call

import get_version
from get_version import TraceabilityEnum


@patch("get_version.logger", new=MagicMock())
class GetVersionTests(unittest.TestCase):
    @patch("get_version.check_output")
    def test_get_last_stable_release(self, check_output_mock):
        check_output_mock.return_value = "vX.Y.Z\n  "

        fetched_version = get_version.get_last_stable_release("")

        self.assertTrue(check_output_mock.called)
        self.assertEqual(fetched_version, "vX.Y.Z")

    @patch("get_version.check_output")
    def test_get_history_since(self, check_output_mock):
        check_output_mock.return_value = "commit1\ncommit2"

        history = get_version.get_history_since("vX.Y.Z", "repo_path")
        self.assertEqual(history, ["commit1", "commit2"])
        args, kwargs = check_output_mock.call_args_list[-1]
        self.assertEqual(kwargs["cwd"], "repo_path")
        self.assertIn("vX.Y.Z", shlex.join(args[0]))

    def test_get_most_severe(self):
        self.assertEqual(
            TraceabilityEnum.BREAKING,
            get_version.get_most_severe(
                TraceabilityEnum.BREAKING, TraceabilityEnum.NEW
            ),
        )
        self.assertEqual(
            TraceabilityEnum.NEW,
            get_version.get_most_severe(
                TraceabilityEnum.BUGFIX, TraceabilityEnum.NEW
            ),
        )
        self.assertEqual(
            TraceabilityEnum.BUGFIX,
            get_version.get_most_severe(
                TraceabilityEnum.BUGFIX, TraceabilityEnum.INFRA
            ),
        )
        self.assertEqual(
            TraceabilityEnum.INFRA,
            get_version.get_most_severe(
                TraceabilityEnum.INFRA, TraceabilityEnum.INFRA
            ),
        )

    def test_get_needed_bump_breaking(self):
        history = ["a (new) #3", "b (bugfix) #2", "c (Breaking) #1"]

        needed_bump = get_version.get_needed_bump(history)

        self.assertEqual(needed_bump, TraceabilityEnum.BREAKING)

    def test_get_needed_bump_new(self):
        history = ["a (new) #3", "b (bugfix) #2", "c (infra) #1"]

        needed_bump = get_version.get_needed_bump(history)

        self.assertEqual(needed_bump, TraceabilityEnum.NEW)

    def test_get_needed_bump_bugfix(self):
        history = ["a (bugfix) #3", "b (bugfix) #2", "c (infra) #1"]

        needed_bump = get_version.get_needed_bump(history)

        self.assertEqual(needed_bump, TraceabilityEnum.BUGFIX)

    def test_get_needed_bump_infra(self):
        history = ["a (infra) #3", "b (infra) #2", "c (infra) #1"]

        needed_bump = get_version.get_needed_bump(history)

        self.assertEqual(needed_bump, TraceabilityEnum.INFRA)

    def test_get_needed_bump_warning(self):
        history = ["a #2", "b #3"]

        needed_bump = get_version.get_needed_bump(history)

        # warns once per commit + a header tha explains that some commits
        # were not categorized
        self.assertEqual(get_version.logger.warning.call_count, 3)
        self.assertEqual(needed_bump, TraceabilityEnum.INFRA)

    def test_add_dev_suffix(self):
        postfixed_version = get_version.add_dev_suffix("vX.Y.Z", 24)
        self.assertEqual(postfixed_version, "vX.Y.Z-dev24")

    def test_describe_bump(self):
        # describe supports all traceability enums
        for value in TraceabilityEnum:
            get_version.describe_bump(value)


@patch("logging.getLogger", new=MagicMock())
class MainTests(unittest.TestCase):
    @patch("get_version.check_output")
    @patch("get_version.print")
    def test_get_version_major(self, print_mock, check_output_mock):
        check_output_mock.side_effect = [
            "v1.2.3",
            "a (new) #1\nb (breaking) #2\nc (infra) #3",
        ]
        get_version.main(["--dev-suffix", "--log", "WARNING"])
        self.assertEqual(print_mock.call_count, 1)
        # last version is v1.2.3
        # we had at least 1 breaking change, we should get v2.0.0
        # we asked the dev suffix and we have 3 commits in the history
        # so it should have a -dev3 at the end
        self.assertEqual(print_mock.call_args, call("v2.0.0-dev3"))

    @patch("get_version.check_output")
    @patch("get_version.print")
    def test_get_version_minor(self, print_mock, check_output_mock):
        check_output_mock.side_effect = [
            "v1.2.3",
            "a (new) #1\nb (new) #2\nc (infra) #3",
        ]
        get_version.main(["--log", "WARNING"])
        self.assertEqual(print_mock.call_count, 1)
        # last version is v1.2.3
        # we had at least 1 new feature, we should get v1.3.0
        # we didnt ask the dev suffix, so it shouldnt be there
        self.assertEqual(print_mock.call_args, call("v1.3.0"))

    @patch("get_version.check_output")
    @patch("get_version.print")
    def test_get_version_patch(self, print_mock, check_output_mock):
        check_output_mock.side_effect = [
            "v1.2.3",
            "a (bugfix) #1\nb (infra) #2\nc (infra) #3",
        ]
        get_version.main(["--log", "WARNING"])
        self.assertEqual(print_mock.call_count, 1)
        # last version is v1.2.3
        # we had at least 1 bugfix, we should get v1.2.4
        # we didnt ask the dev suffix, so it shouldnt be there
        self.assertEqual(print_mock.call_args, call("v1.2.4"))

    @patch("get_version.check_output")
    @patch("get_version.print")
    def test_get_version_error(self, print_mock, check_output_mock):
        check_output_mock.side_effect = [
            "v1.2.3",
            "a (infra) #1\nb (infra) #2\nc (infra) #3",
        ]
        # last version is v1.2.3
        # this should fail because we didn't have any release worthy commit
        with self.assertRaises(SystemExit):
            get_version.main(["--log", "WARNING"])

        check_output_mock.side_effect = [
            "v1.2.3",
            "",
        ]
        # last version is v1.2.3
        # this should fail because we are on a tagged commit
        # (so nothing to release here)
        with self.assertRaises(SystemExit):
            get_version.main(["--log", "WARNING"])
