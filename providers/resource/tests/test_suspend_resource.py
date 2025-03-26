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

    def test_get_supported_suspend_type(self):
        types = ["s2idle", "[deep]"]
        supported_type = suspend_resource.get_supported_suspend_type(types)
        self.assertEqual(supported_type, "deep")
        types = [
            "[s2idle]",
        ]
        supported_type = suspend_resource.get_supported_suspend_type(types)
        self.assertEqual(supported_type, "s2idle")
        types = [
            "",
        ]
        supported_type = suspend_resource.get_supported_suspend_type(types)
        self.assertEqual(supported_type, None)

    @patch("suspend_resource.get_mem_sleep_types")
    @patch("suspend_resource.get_supported_suspend_type")
    @patch("sys.stdout", new_callable=io.StringIO)
    def test_main(self, mock_stdout, mock_supported_type, mock_mem_sleep):
        mock_supported_type.return_value = "s2idle"
        suspend_resource.main()
        self.assertEqual(mock_stdout.getvalue(), "type: s2idle\n")
