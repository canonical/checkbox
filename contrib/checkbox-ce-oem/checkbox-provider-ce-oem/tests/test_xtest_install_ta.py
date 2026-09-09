import os
import tempfile
import unittest
from unittest.mock import patch

import xtest_install_ta


class TestFindTaPath(unittest.TestCase):

    def test_finds_ta_directly_under_common_on_real_filesystem(self):
        # Regression test: on real devices the TA lives directly under
        # the snap's persistent common data dir, e.g.
        # /var/snap/<snap_name>/common/lib/optee_armtz — a sibling of
        # "current"/the numbered revision dirs, not nested under them.
        # Exercised against a real filesystem (rather than a mocked
        # os.walk) so a regression that goes back to searching only
        # under ".../current" would actually be caught here.
        with tempfile.TemporaryDirectory() as tmp:
            snap_root = os.path.join(tmp, "hon-x-test")
            ta_dir = os.path.join(snap_root, "common", "lib", "optee_armtz")
            os.makedirs(ta_dir)
            revision_dir = os.path.join(snap_root, "x1")
            os.makedirs(revision_dir)
            os.symlink(revision_dir, os.path.join(snap_root, "current"))

            real_join = os.path.join

            def fake_join(a, *rest):
                # Redirect only find_ta_path()'s own "/var/snap" root
                # onto our fixture; everything else joins normally.
                if a == "/var/snap":
                    return real_join(tmp, *rest)
                return real_join(a, *rest)

            with patch("xtest_install_ta.os.path.join", fake_join):
                found = xtest_install_ta.find_ta_path("hon-x-test")
            self.assertEqual(found, ta_dir)

    @patch("xtest_install_ta.os.walk")
    def test_ta_found(self, mock_walk):
        mock_walk.return_value = [
            ("/var/snap/hon-x-test", ["common", "current", "x1"], []),
            ("/var/snap/hon-x-test/common", ["lib"], []),
            ("/var/snap/hon-x-test/common/lib", ["optee_armtz"], []),
        ]
        path = xtest_install_ta.find_ta_path("hon-x-test")
        self.assertEqual(
            path,
            "/var/snap/hon-x-test/common/lib/optee_armtz",
        )
        mock_walk.assert_called_once_with("/var/snap/hon-x-test")

    @patch("xtest_install_ta.os.walk")
    def test_ta_not_found(self, mock_walk):
        mock_walk.return_value = [
            ("/var/snap/hon-x-test", ["common"], []),
            ("/var/snap/hon-x-test/common", [], []),
        ]
        with self.assertRaises(SystemError):
            xtest_install_ta.find_ta_path("hon-x-test")

    @patch("xtest_install_ta.os.walk")
    def test_multiple_ta_found_in_same_snap(self, mock_walk):
        # Even scoped to a single snap, more than one match should
        # still be treated as ambiguous and fail loudly.
        mock_walk.return_value = [
            (
                "/var/snap/hon-x-test/common/lib",
                ["optee_armtz"],
                [],
            ),
            (
                "/var/snap/hon-x-test/x1",
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
