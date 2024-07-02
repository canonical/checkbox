import unittest
import sys
from unittest.mock import patch, call, Mock, MagicMock
from io import StringIO
from contextlib import redirect_stdout

# Mock the dbus module due to is is not available on CI testing environment
sys.modules["dbus"] = MagicMock()

import wwan_resource_with_iterations


class TestMultipleResources(unittest.TestCase):

    @patch("builtins.print")
    def test_dump_resource(self, mock_print):
        mock_instance = Mock()
        mock_instance.return_value = ["test"]

        mock_mm = Mock()
        mock_mm.get_modem_ids = mock_instance
        mock_mm.get_equipment_id = mock_instance
        mock_mm.get_manufacturer = mock_instance
        mock_mm.get_model_name = mock_instance
        mock_mm.get_firmware_revision = mock_instance
        mock_mm.get_hardware_revision = mock_instance

        with redirect_stdout(StringIO()):
            wwan_resource_with_iterations.dump_wwan_resource(mock_mm, 2)
            self.assertTrue(mock_mm.get_equipment_id.called)
            self.assertTrue(mock_mm.get_manufacturer.called)
            self.assertTrue(mock_mm.get_model_name.called)
            self.assertTrue(mock_mm.get_firmware_revision.called)
            self.assertTrue(mock_mm.get_hardware_revision.called)
            self.assertEqual(mock_print.call_count, 16)

    def test_parser_mmcli(self):
        sys.argv = [
            "wwan_resource_with_iterations.py",
            "-i",
            "5",
            "--use-cli",
        ]
        args = wwan_resource_with_iterations.register_arguments()

        self.assertEqual(args.iteration, 5)
        self.assertEqual(args.use_cli, True)

    def test_parser_mmdbus(self):
        sys.argv = ["wwan_resource_with_iterations.py"]
        args = wwan_resource_with_iterations.register_arguments()

        self.assertEqual(args.iteration, 3)
        self.assertEqual(args.use_cli, False)
