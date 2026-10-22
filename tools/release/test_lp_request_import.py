import unittest
from unittest.mock import patch, PropertyMock

import lp_request_import


class TestMain(unittest.TestCase):
    @patch("lp_request_import.get_launchpad_client")
    def test_main_typo(self, get_launchpad_client_mock):
        lp_client = get_launchpad_client_mock()
        lp_client.git_repositories.getByPath.return_value = None

        with self.assertRaises(SystemExit):
            lp_request_import.main(["typo_in_name"])

    @patch("lp_request_import.get_launchpad_client")
    @patch("lp_request_import.datetime")
    @patch("lp_request_import.timedelta")
    def test_main_import_fail(
        self, timedelta_mock, datetime_mock, get_launchpad_client_mock
    ):
        lp_client = get_launchpad_client_mock()
        repo = lp_client.git_repositories.getByPath()
        repo.code_import.requestImport.side_effect = Exception(
            "Code import has to be re-approved manually"
        )

        with self.assertRaises(SystemExit):
            lp_request_import.main(["checkbox-edge"])
        get_launchpad_client_mock.assert_called_with(timeout=30)

    @patch("lp_request_import.get_launchpad_client")
    def test_main_request_timeout(self, get_launchpad_client_mock):
        repo = get_launchpad_client_mock().git_repositories.getByPath()
        repo.code_import.requestImport.side_effect = TimeoutError(
            "Launchpad request timed out"
        )

        with self.assertRaisesRegex(
            SystemExit,
            "^Launchpad request timed out: Launchpad request timed out$",
        ):
            lp_request_import.main(["checkbox-edge"])

    @patch("lp_request_import.get_launchpad_client")
    def test_main_poll_timeout(self, get_launchpad_client_mock):
        repo = get_launchpad_client_mock().git_repositories.getByPath()
        type(repo.code_import).date_last_successful = PropertyMock(
            side_effect=TimeoutError("Launchpad polling timed out")
        )

        with self.assertRaisesRegex(
            SystemExit,
            "^Launchpad request timed out: Launchpad polling timed out$",
        ):
            lp_request_import.main(["checkbox-edge"])

    @patch("lp_request_import.get_launchpad_client")
    def test_main_client_timeout(self, client_mock):
        client_mock.side_effect = TimeoutError("The read operation timed out")

        with self.assertRaisesRegex(
            SystemExit,
            "^Launchpad request timed out: The read operation timed out$",
        ):
            lp_request_import.main(["checkbox-edge"])

    @patch("lp_request_import.get_launchpad_client")
    def test_main_unexpected_error(self, client_mock):
        client_mock.side_effect = ValueError("Unexpected error")

        with self.assertRaisesRegex(ValueError, "Unexpected error"):
            lp_request_import.main(["checkbox-edge"])

    @patch("lp_request_import.get_launchpad_client")
    @patch("lp_request_import.datetime")
    @patch("lp_request_import.timedelta")
    def test_main_import_timeout(
        self, timedelta_mock, datetime_mock, get_launchpad_client_mock
    ):
        lp_client = get_launchpad_client_mock()
        repo = lp_client.git_repositories.getByPath()
        repo.code_import.requestImport.side_effect = Exception(
            "This code import is already running"
        )

        # start at 0, first check at 100
        datetime_mock.utcnow.side_effect = [0, 100]
        timedelta_mock.return_value = 0
        repo.code_import.date_last_successful.replace.return_value = -1

        with self.assertRaises(SystemExit):
            lp_request_import.main(["checkbox-edge"])

    @patch("lp_request_import.get_launchpad_client")
    @patch("lp_request_import.datetime")
    @patch("lp_request_import.timedelta")
    @patch("lp_request_import.time.sleep")
    def test_main_import_ok(
        self,
        sleep_mock,
        timedelta_mock,
        datetime_mock,
        get_launchpad_client_mock,
    ):
        lp_client = get_launchpad_client_mock()
        repo = lp_client.git_repositories.getByPath()
        repo.code_import.requestImport.side_effect = Exception(
            "This code import is already running"
        )

        # start at 0, first check at 100
        datetime_mock.utcnow.side_effect = [0, 100, 300]
        timedelta_mock.return_value = 1000
        repo.code_import.date_last_successful.replace.side_effect = [-1, 200]

        lp_request_import.main(["checkbox-edge"])
        sleep_mock.assert_called_once_with(30)
