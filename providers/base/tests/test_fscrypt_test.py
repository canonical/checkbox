from unittest.mock import patch
import fscrypt_test
import unittest


def _prepare_path_and_subprocess(mock_path, mock_subprocess):
    mock_path.exists.side_effect = [True, False, True]
    mock_path.mkdir.return_value = True
    mock_path.__truediv__.return_value = mock_path
    mock_path.__str__.return_value = "path"
    mock_path.return_value = mock_path
    mock_path.open = mock_path
    mock_path.__enter__ = mock_path
    mock_path.read.return_value = "test\n"
    mock_subprocess.run.side_effect = [0, Exception("Should be called once")]
    mock_subprocess.check_call.return_value = 0
    mock_subprocess.check_output.return_value = (
        "path this-is-ignore this-also supported   Yes"
    )


class FscryptTestCase(unittest.TestCase):
    @patch("fscrypt_test.Path")
    @patch("fscrypt_test.subprocess")
    def test_main_success(self, mock_subprocess, mock_path):
        _prepare_path_and_subprocess(
            mock_path,
            mock_subprocess,
        )
        fscrypt_test.main()

    @patch("fscrypt_test.Path")
    @patch("fscrypt_test.subprocess")
    def test_main_failure_setup(self, mock_subprocess, mock_path):
        _prepare_path_and_subprocess(
            mock_path,
            mock_subprocess,
        )
        # Fake fscrypt setup not working.
        mock_subprocess.check_output.return_value = (
            "path this-is-ignore this-also supported   No"
        )
        with self.assertRaises(SystemExit) as context:
            fscrypt_test.main()
        self.assertEqual(str(context.exception), "Failed to setup fscrypt")

    @patch("fscrypt_test.Path")
    @patch("fscrypt_test.subprocess")
    def test_main_failure_lock(self, mock_subprocess, mock_path):
        _prepare_path_and_subprocess(
            mock_path,
            mock_subprocess,
        )
        # Fake fscrypt lock not working.
        mock_path.exists.side_effect = [True, True, True]
        with self.assertRaises(SystemExit) as context:
            fscrypt_test.main()
        self.assertEqual(
            str(context.exception), "File should not be accessible when locked"
        )

    @patch("fscrypt_test.Path")
    @patch("fscrypt_test.subprocess")
    def test_main_failure_unlock(self, mock_subprocess, mock_path):
        _prepare_path_and_subprocess(
            mock_path,
            mock_subprocess,
        )
        # Fake bad unlink file content.
        mock_path.read.return_value = "invalid\n"
        with self.assertRaises(SystemExit) as context:
            fscrypt_test.main()
        self.assertEqual(
            str(context.exception), "File contents not correct after unlock"
        )

    @patch("fscrypt_test.Path")
    @patch("fscrypt_test.subprocess")
    def test_main_failure_not_already_setup(self, mock_subprocess, mock_path):
        _prepare_path_and_subprocess(
            mock_path,
            mock_subprocess,
        )
        # Fake fscrypt.conf not already existing, so it has to be deleted.
        mock_path.exists.side_effect = [False, False, True]
        mock_subprocess.run.side_effect = [0, 0]
        fscrypt_test.main()
        self.assertTrue(mock_path.unlink.called)
