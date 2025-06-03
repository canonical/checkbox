import unittest
import io
from unittest.mock import patch, mock_open

import suspend_resource


class SuspendResourceTests(unittest.TestCase):

    @patch(
        "builtins.open", new_callable=mock_open, read_data="s2idle [deep]\n"
    )
    def test_get_mem_sleep_types(self, mock_open):
        types = suspend_resource.get_mem_sleep_types()
        self.assertEqual(types, ["s2idle", "[deep]"])

    def test_get_supported_suspend_types(self):
        types = ["s2idle", "[deep]"]
        supported_types = suspend_resource.get_supported_suspend_types(types)
        expected = {
            "deep": "yes",
            "s2idle": "no",
        }
        self.assertEqual(supported_types, expected)
        types = [
            "[s2idle]",
        ]
        supported_types = suspend_resource.get_supported_suspend_types(types)
        expected = {
            "s2idle": "yes",
        }
        self.assertEqual(supported_types, expected)
        types = [
            "",
        ]
        supported_types = suspend_resource.get_supported_suspend_types(types)
        self.assertEqual(supported_types, {})

    @patch("suspend_resource.get_mem_sleep_types")
    @patch("suspend_resource.get_supported_suspend_types")
    @patch("sys.stdout", new_callable=io.StringIO)
    def test_main(self, mock_stdout, mock_supported_types, mock_mem_sleep):
        mock_supported_types.return_value = {"s2idle": "yes"}
        suspend_resource.main()
        self.assertEqual(
            mock_stdout.getvalue(), "type: s2idle\nactive: yes\n\n"
        )
