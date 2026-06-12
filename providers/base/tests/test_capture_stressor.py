import unittest
from unittest.mock import patch

import capture_stressor


class TestCaptureStressorResource(unittest.TestCase):
    @patch("os.getenv", return_value="")
    @patch("capture_stressor.print")
    @patch("subprocess.run")
    def test_stressors_printed(self, run_mock, print_mock, getenv_mock):
        stressors = run_mock()
        stressors.stdout = "class 'cpu': fake-stressor-unittest"
        printed = ""

        def fake_print(*args, **kwargs):
            nonlocal printed
            printed += " ".join(str(a) for a in args) + "\n"

        print_mock.side_effect = fake_print

        capture_stressor.main()

        self.assertIn("stressor: fake-stressor-unittest", printed)
        self.assertIn("root: False", printed)
        self.assertIn("pathological: False", printed)
        self.assertIn("unsupported: False", printed)

    @patch("os.getenv", return_value="")
    @patch("capture_stressor.print")
    @patch("subprocess.run")
    def test_stressors_printed_extra_unsupported(
        self, run_mock, print_mock, getenv_mock
    ):
        getenv_mock.return_value = "fake-stressor-unittest"
        stressors = run_mock()
        stressors.stdout = "class 'cpu': fake-stressor-unittest"
        printed = ""

        def fake_print(*args, **kwargs):
            nonlocal printed
            printed += " ".join(str(a) for a in args) + "\n"

        print_mock.side_effect = fake_print

        capture_stressor.main()

        self.assertIn("stressor: fake-stressor-unittest", printed)
        self.assertIn("root: False", printed)
        self.assertIn("pathological: False", printed)
        self.assertIn("unsupported: True", printed)
