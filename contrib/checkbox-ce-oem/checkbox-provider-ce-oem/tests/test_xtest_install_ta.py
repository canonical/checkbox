import unittest
from unittest.mock import patch

import xtest_install_ta


class TestFindTaPath(unittest.TestCase):

    @patch("xtest_install_ta.os.walk")
    def test_ta_found(self, mock_walk):
        mock_walk.return_value = [
            ("/var/snap/hon-x-test/current", ["common"], []),
            ("/var/snap/hon-x-test/current/common", ["lib"], []),
            (
                "/var/snap/hon-x-test/current/common/lib",
                ["optee_armtz"],
                [],
            ),
        ]
        path = xtest_install_ta.find_ta_path("hon-x-test")
        self.assertEqual(
            path,
            "/var/snap/hon-x-test/current/common/lib/optee_armtz",
        )
        mock_walk.assert_called_once_with("/var/snap/hon-x-test/current")

    @patch("xtest_install_ta.os.walk")
    def test_ta_not_found(self, mock_walk):
        mock_walk.return_value = [
            ("/var/snap/hon-x-test/current", ["common"], []),
            ("/var/snap/hon-x-test/current/common", [], []),
        ]
        with self.assertRaises(SystemError):
            xtest_install_ta.find_ta_path("hon-x-test")

    @patch("xtest_install_ta.os.walk")
    def test_multiple_ta_found_in_same_snap(self, mock_walk):
        # Even scoped to a single snap, more than one match should
        # still be treated as ambiguous and fail loudly.
        mock_walk.return_value = [
            (
                "/var/snap/hon-x-test/current/common/lib",
                ["optee_armtz"],
                [],
            ),
            (
                "/var/snap/hon-x-test/current/x1",
                ["optee_armtz"],
                [],
            ),
        ]
        with self.assertRaises(SystemError):
            xtest_install_ta.find_ta_path("hon-x-test")


class TestMain(unittest.TestCase):

    @patch.dict("xtest_install_ta.os.environ", {"XTEST": "hon-x-test"})
    @patch("xtest_install_ta.install_ta")
    @patch("xtest_install_ta.find_ta_path")
    @patch("xtest_install_ta.look_up_app")
    def test_main_uses_snap_from_xtest_env(
        self, mock_look_up_app, mock_find_ta_path, mock_install_ta
    ):
        mock_look_up_app.return_value = "hon-x-test.xtest"
        mock_find_ta_path.return_value = (
            "/var/snap/hon-x-test/common/lib/optee_armtz"
        )

        xtest_install_ta.main()

        mock_look_up_app.assert_called_once_with("xtest", "hon-x-test")
        mock_find_ta_path.assert_called_once_with("hon-x-test")
        mock_install_ta.assert_called_once_with(
            "hon-x-test.xtest",
            "/var/snap/hon-x-test/common/lib/optee_armtz",
        )


if __name__ == "__main__":
    unittest.main()
