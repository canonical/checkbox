import unittest
from unittest.mock import patch, MagicMock

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
    @patch("time.sleep", new=MagicMock())
    def test_main_import_ok(
        self, timedelta_mock, datetime_mock, get_launchpad_client_mock
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
