import unittest
import pwd
from unittest.mock import patch
from checkbox_ng.user_utils import check_user_exists, guess_normal_user


class TestCheckUserExists(unittest.TestCase):
    @patch("pwd.getpwnam")
    def test_user_exists(self, mock_getpwnam):
        mock_getpwnam.return_value = pwd.struct_passwd(
            (
                "testuser",
                "x",
                1001,
                1001,
                "Test User",
                "/home/testuser",
                "/bin/bash",
            )
        )
        self.assertTrue(check_user_exists("testuser"))
        mock_getpwnam.assert_called_with("testuser")

    @patch("pwd.getpwnam")
    def test_user_does_not_exist(self, mock_getpwnam):
        mock_getpwnam.side_effect = KeyError("testuser not found")
        self.assertFalse(check_user_exists("testuser"))

    def test_invalid_input(self):
        with self.assertRaises(TypeError):
            check_user_exists(None)


class TestGuessNormalUser(unittest.TestCase):
    @patch("pwd.getpwall")
    def test_guess_ubuntu_user(self, mock_getpwall):
        mock_getpwall.return_value = [
            pwd.struct_passwd(
                (
                    "ubuntu",
                    "x",
                    2222,
                    2222,
                    "Ubuntu User",
                    "/home/ubuntu",
                    "/bin/bash",
                )
            )
        ]
        self.assertEqual(guess_normal_user(), "ubuntu")

    @patch("pwd.getpwall")
    @patch("pwd.getpwuid")
    def test_guess_uid_1000_user(self, mock_getpwuid, mock_getpwall):
        mock_getpwall.return_value = []
        mock_getpwuid.return_value = pwd.struct_passwd(
            (
                "user1000",
                "x",
                1000,
                1000,
                "User 1000",
                "/home/user1000",
                "/bin/bash",
            )
        )
        self.assertEqual(guess_normal_user(), "user1000")

    @patch("pwd.getpwall")
    @patch("pwd.getpwuid")
    def test_guess_uid_1001_user(self, mock_getpwuid, mock_getpwall):
        mock_getpwall.return_value = []
        mock_getpwuid.side_effect = [
            KeyError("UID 1000 not found"),
            pwd.struct_passwd(
                (
                    "user1001",
                    "x",
                    1001,
                    1001,
                    "User 1001",
                    "/home/user1001",
                    "/bin/bash",
                )
            ),
        ]
        self.assertEqual(guess_normal_user(), "user1001")

    @patch("pwd.getpwall")
    @patch("pwd.getpwuid")
    def test_cannot_guess_the_user(self, mock_getpwuid, mock_getpwall):
        mock_getpwall.return_value = []
        mock_getpwuid.side_effect = [KeyError(), KeyError()]

        with self.assertRaises(RuntimeError):
            guess_normal_user()


if __name__ == "__main__":
    unittest.main()
