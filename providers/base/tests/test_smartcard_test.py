import unittest
from unittest.mock import patch, MagicMock
import logging

from checkbox_support.helpers.timeout import mock_timeout

# Import the class to be tested
# Assuming smartcard_test.py is in the same directory or accessible via PYTHONPATH
from smartcard_test import (
    SmartcardTest,
    NoCardException,
    CardConnectionException,
)


@mock_timeout()
class TestSmartcardTest(unittest.TestCase):
    def setUp(self):
        """
        Set up for each test case.
        We'll patch `smartcard.System.readers` globally for most tests
        since it's accessed in the constructor.
        """
        # Patch smartcard.System.readers to return a mock list of readers
        self.mock_reader_class = MagicMock()
        self.mock_reader_class.name = "Mock Reader 1"
        self.mock_reader_class_contactless = MagicMock()
        self.mock_reader_class_contactless.name = "Mock Reader 2 - Contactless"
        self.mock_reader_class_cl = MagicMock()
        self.mock_reader_class_cl.name = "Mock Reader 3 -CL"

        self.mock_readers_list = [
            self.mock_reader_class,
            self.mock_reader_class_contactless,
            self.mock_reader_class_cl,
        ]

        self.patcher_readers = patch(
            "smartcard_test.readers", return_value=self.mock_readers_list
        )
        self.mock_readers = self.patcher_readers.start()

        # Initialize SmartcardTest instance
        self.sc = SmartcardTest()

        self.sc.readers = self.mock_readers_list

        # Suppress logging output during tests unless explicitly needed
        self.sc.logger.setLevel(logging.CRITICAL)

    def tearDown(self):
        """
        Clean up after each test case.
        Stop all patches.
        """
        self.patcher_readers.stop()

    def test_stringify_reader_name(self):
        """
        Test stringify_reader_name method.
        """
        self.assertEqual(
            self.sc.stringify_reader_name("My Reader Name 123!@#"),
            "My-Reader-Name-123-",
        )
        self.assertEqual(
            self.sc.stringify_reader_name("Another_Reader-Name.V2"),
            "Another-Reader-Name-V2",
        )
        self.assertEqual(self.sc.stringify_reader_name("Short"), "Short")
        self.assertEqual(
            self.sc.stringify_reader_name("A" * 50), "A" * 40
        )  # Test truncation

    def test_reader_filter_all(self):
        """
        Test reader_filter with 'All' type.
        """
        self.assertEqual(
            self.sc.reader_filter("All", self.mock_reader_class),
            self.mock_reader_class,
        )
        self.assertEqual(
            self.sc.reader_filter("ALL", self.mock_reader_class_contactless),
            self.mock_reader_class_contactless,
        )

    def test_reader_filter_contact(self):
        """
        Test reader_filter with 'contact' type.
        """
        self.assertEqual(
            self.sc.reader_filter("contact", self.mock_reader_class),
            self.mock_reader_class,
        )
        self.assertIsNone(
            self.sc.reader_filter(
                "contact", self.mock_reader_class_contactless
            )
        )
        self.assertIsNone(
            self.sc.reader_filter("contact", self.mock_reader_class_cl)
        )

    def test_reader_filter_contactless(self):
        """
        Test reader_filter with 'contactless' type.
        """
        self.assertIsNone(
            self.sc.reader_filter("contactless", self.mock_reader_class)
        )
        self.assertEqual(
            self.sc.reader_filter(
                "contactless", self.mock_reader_class_contactless
            ),
            self.mock_reader_class_contactless,
        )
        self.assertEqual(
            self.sc.reader_filter("contactless", self.mock_reader_class_cl),
            self.mock_reader_class_cl,
        )

    @patch("builtins.print")
    def test_list_readers(self, mock_print):
        """
        Test list_readers method.
        """
        # Test with 'All'
        self.sc.list_readers("All")
        expected_calls = [
            unittest.mock.call("smartcard_reader: Mock-Reader-1"),
            unittest.mock.call("smartcard_reader: Mock-Reader-2-Contactless"),
            unittest.mock.call("smartcard_reader: Mock-Reader-3-CL"),
        ]
        mock_print.assert_has_calls(expected_calls, any_order=True)
        mock_print.reset_mock()

        # Test with 'contact'
        self.sc.list_readers("contact")
        mock_print.assert_called_once_with("smartcard_reader: Mock-Reader-1")
        mock_print.reset_mock()

        # Test with 'contactless'
        self.sc.list_readers("contactless")
        expected_calls = [
            unittest.mock.call("smartcard_reader: Mock-Reader-2-Contactless"),
            unittest.mock.call("smartcard_reader: Mock-Reader-3-CL"),
        ]
        mock_print.assert_has_calls(expected_calls, any_order=True)
        self.assertEqual(mock_print.call_count, 2)
        mock_print.reset_mock()

    @patch("smartcard_test.SmartcardTest.logger.info")
    def test_detect_reader_success(self, mock_logger_info):
        """
        Test detect_reader method when readers are found.
        """
        # Test with 'All'
        self.sc.detect_reader("All")
        expected_calls = [
            unittest.mock.call("Mock Reader 1"),
            unittest.mock.call("Mock Reader 2 - Contactless"),
            unittest.mock.call("Mock Reader 3 -CL"),
        ]
        mock_logger_info.assert_has_calls(expected_calls, any_order=True)
        self.assertEqual(mock_logger_info.call_count, 3)

    @patch("smartcard_test.SmartcardTest.logger.info")
    def test_detect_reader_no_reader(self, mock_logger_info):
        """
        Test detect_reader method when no readers are found.
        """
        # Mock readers to be empty
        sc_no_readers = SmartcardTest()
        sc_no_readers.readers = []
        with self.assertRaises(SystemExit) as cm:
            sc_no_readers.detect_reader("All")
        self.assertEqual(
            cm.exception.code,
            "There is no smartcard reader in this system",
        )
        mock_logger_info.assert_not_called()

    def test_get_real_reader_instance(self):
        """
        Test get_real_reader_instance method.
        """
        # Assuming stringify_reader_name works correctly
        reader_name = self.sc.stringify_reader_name(
            self.mock_reader_class.name
        )
        found_reader = self.sc.get_real_reader_instance(reader_name)
        self.assertEqual(found_reader, self.mock_reader_class)

        # Test with a non-existent reader
        self.assertIsNone(
            self.sc.get_real_reader_instance("NonExistentReader")
        )

    @patch("smartcard_test.SmartcardTest.get_real_reader_instance")
    @patch("smartcard_test.SmartcardTest.logger.info")
    def test_get_connection_success(
        self, mock_logger_info, mock_get_real_reader_instance
    ):
        """
        Test get_connection method on successful connection.
        """
        mock_connection = MagicMock()
        mock_reader = MagicMock()
        mock_reader.createConnection.return_value = mock_connection
        mock_reader.name = "Test Reader"

        mock_get_real_reader_instance.return_value = mock_reader

        connection = self.sc.get_connection("Test Reader Stringified")

        mock_get_real_reader_instance.assert_called_once_with(
            "Test Reader Stringified"
        )
        self.assertEqual(connection, mock_connection)

    @patch("smartcard_test.SmartcardTest.get_real_reader_instance")
    @patch("sys.exit")
    @patch("smartcard_test.SmartcardTest.logger.info")
    def test_get_connection_no_card_exception(
        self, mock_logger_info, mock_sys_exit, mock_get_real_reader_instance
    ):
        """
        Test get_connection method when NoCardException occurs.
        """
        mock_reader = MagicMock()
        mock_reader.createConnection.side_effect = NoCardException(
            "No card", hresult=-1
        )
        mock_get_real_reader_instance.return_value = mock_reader

        with self.assertRaises(SystemExit) as cm:
            self.sc.get_connection("Test Reader Stringified")
        self.assertEqual(
            cm.exception.code, "no card inserted or card is unsupported"
        )
        mock_logger_info.assert_not_called()  # Should not log success if exception occurs

        mock_get_real_reader_instance.return_value = None
        with self.assertRaises(SystemExit) as cm:
            self.sc.get_connection("Test Reader Stringified")
        self.assertEqual(cm.exception.code, "no smartcard reader")

    @patch("smartcard_test.SmartcardTest.get_real_reader_instance")
    @patch("sys.exit")
    @patch("smartcard_test.SmartcardTest.logger.info")
    def test_get_connection_card_connection_exception(
        self, mock_logger_info, mock_sys_exit, mock_get_real_reader_instance
    ):
        """
        Test get_connection method when CardConnectionException occurs.
        """
        mock_reader = MagicMock()
        mock_reader.createConnection.side_effect = CardConnectionException(
            "Connection error"
        )
        mock_get_real_reader_instance.return_value = mock_reader

        with self.assertRaises(SystemExit) as cm:
            self.sc.get_connection("Test Reader Stringified")
        self.assertEqual(
            cm.exception.code, "no card inserted or card is unsupported"
        )
        mock_logger_info.assert_not_called()  # Should not log success if exception occurs

    @patch("smartcard_test.SmartcardTest.get_real_reader_instance")
    @patch("smartcard_test.SmartcardTest.logger.info")
    @patch("smartcard_test.CardRequest")
    def test_detect_smartcard_success(
        self, MockCardRequest, mock_logger_info, mock_get_real_reader_instance
    ):
        """
        Test detect_smartcard method for successful insertion and removal.
        """
        mock_real_reader = MagicMock()
        mock_real_reader.name = "Mock Reader 1"
        mock_get_real_reader_instance.return_value = mock_real_reader

        mock_card_insert = MagicMock()
        mock_card_insert.reader = "Mock Reader 1"
        mock_card_insert.atr = [0x3B, 0x00]  # Example ATR

        mock_card_request_instance_new = MagicMock()
        mock_card_request_instance_new.waitforcardevent.side_effect = [
            [mock_card_insert],
        ]
        mock_card_request_instance_old = MagicMock()
        mock_card_request_instance_old.waitforcardevent.side_effect = [
            [],
        ]

        MockCardRequest.side_effect = [
            mock_card_request_instance_new,
            mock_card_request_instance_old,
        ]
        self.sc.detect_smartcard("Mock-Reader-1")

        mock_get_real_reader_instance.assert_called_once_with("Mock-Reader-1")
        self.assertEqual(MockCardRequest.call_count, 2)
        MockCardRequest.assert_has_calls(
            [
                unittest.mock.call(timeout=30, newcardonly=True),
                unittest.mock.call(timeout=30, newcardonly=False),
            ]
        )

        expected_logger_calls = [
            unittest.mock.call(
                "Smartcard insertion and removal detection test is starting"
            ),
            unittest.mock.call(
                "Please insert and remove the smartcard within 30 seconds.\n"
            ),
            unittest.mock.call("Smart card insertion detected:"),
            unittest.mock.call(mock_card_insert),
            unittest.mock.call(
                "\nPlease remove it to test the removal detection\n"
            ),
            unittest.mock.call("Smart card removal detected:"),
            unittest.mock.call(mock_card_insert),
        ]
        mock_logger_info.assert_has_calls(expected_logger_calls)

    @patch("smartcard_test.SmartcardTest.get_connection")
    @patch("smartcard_test.SmartcardTest.logger.info")
    @patch("smartcard.util.toHexString", return_value="3B00")
    def test_send_apdu_test_success(
        self, mock_toHexString, mock_logger_info, mock_get_connection
    ):
        """
        Test send_apdu_test method on successful APDU transmission.
        """
        mock_connection = MagicMock()
        mock_connection.getATR.return_value = [0x3B, 0x00]
        mock_connection.transmit.return_value = (
            [],
            self.sc.sw1_list[0],
            0x00,
        )  # Simulate success SW1
        mock_get_connection.return_value = mock_connection

        self.sc.send_apdu_test("Test Reader Stringified")

        mock_get_connection.assert_called_once_with("Test Reader Stringified")

        expected_logger_calls = [
            unittest.mock.call("ATR from smartcard:"),
            unittest.mock.call("3B 00"),
            unittest.mock.call("Send/Receive APDU command is working"),
        ]
        mock_logger_info.assert_has_calls(expected_logger_calls)

    @patch("smartcard_test.SmartcardTest.get_connection")
    @patch("sys.exit")
    @patch("smartcard_test.SmartcardTest.logger.info")
    @patch("smartcard.util.toHexString")
    def test_send_apdu_test_failure(
        self,
        mock_toHexString,
        mock_logger_info,
        mock_sys_exit,
        mock_get_connection,
    ):
        """
        Test send_apdu_test method when APDU transmission fails (SW1 not in list).
        """
        mock_connection = MagicMock()
        mock_connection.getATR.return_value = [0x3B, 0x00]
        mock_connection.transmit.return_value = (
            [],
            0x11,
            0x00,
        )  # Simulate failure SW1
        mock_get_connection.return_value = mock_connection

        with self.assertRaises(SystemExit) as cm:
            self.sc.send_apdu_test("Test Reader Stringified")
        self.assertEqual(
            cm.exception.code, "Could not working for this smartcard reader"
        )

        mock_get_connection.assert_called_once_with("Test Reader Stringified")
        mock_logger_info.assert_has_calls(
            [
                unittest.mock.call("ATR from smartcard:"),
                unittest.mock.call("3B 00"),
            ]
        )
        # Ensure success message is NOT logged
        self.assertNotIn(
            unittest.mock.call("Send/Receive APDU command is working"),
            mock_logger_info.call_args_list,
        )

        mock_get_connection.return_value = (
            None  # No return value from connection
        )
        with self.assertRaises(SystemExit) as cm:
            self.sc.send_apdu_test("Test Reader Stringified")
        self.assertEqual(
            cm.exception.code, "Could not working for this smartcard reader"
        )

    def test_args_parsing_resources(self):
        """
        Test _args_parsing for 'resources' command.
        """
        args = self.sc._args_parsing(["resources", "-t", "contact"])
        self.assertEqual(args.test_type, "resources")
        self.assertEqual(args.type, "contact")

        args = self.sc._args_parsing(["resources"])  # Default type
        self.assertEqual(args.test_type, "resources")
        self.assertEqual(args.type, "All")

    def test_args_parsing_detect_reader(self):
        """
        Test _args_parsing for 'detect_reader' command.
        """
        args = self.sc._args_parsing(
            ["detect_reader", "--type", "contactless"]
        )
        self.assertEqual(args.test_type, "detect_reader")
        self.assertEqual(args.type, "contactless")

        args = self.sc._args_parsing(["detect_reader"])  # Default type
        self.assertEqual(args.test_type, "detect_reader")
        self.assertEqual(args.type, "All")

    def test_args_parsing_detect_card(self):
        """
        Test _args_parsing for 'detect_card' command.
        """
        args = self.sc._args_parsing(["detect_card", "-r", "MyReader"])
        self.assertEqual(args.test_type, "detect_card")
        self.assertEqual(args.reader, "MyReader")

    def test_args_parsing_send(self):
        """
        Test _args_parsing for 'send' command.
        """
        args = self.sc._args_parsing(["send", "-r", "AnotherReader"])
        self.assertEqual(args.test_type, "send")
        self.assertEqual(args.reader, "AnotherReader")

    def test_args_parsing_no_subcommand(self):
        """
        Test _args_parsing when no subcommand is provided.
        """
        with self.assertRaises(
            SystemExit
        ):  # argparse will exit if required subcommand is missing
            self.sc._args_parsing([])

    @patch("smartcard_test.SmartcardTest.list_readers")
    def test_function_select_resources(self, mock_list_readers):
        """
        Test function_select for 'resources' type.
        """
        mock_args = MagicMock()
        mock_args.test_type = "resources"
        mock_args.type = "All"
        self.sc.function_select(mock_args)
        mock_list_readers.assert_called_once_with("All")

    @patch("smartcard_test.SmartcardTest.detect_reader")
    def test_function_select_detect_reader(self, mock_detect_reader):
        """
        Test function_select for 'detect_reader' type.
        """
        mock_args = MagicMock()
        mock_args.test_type = "detect_reader"
        mock_args.type = "contact"
        self.sc.function_select(mock_args)
        mock_detect_reader.assert_called_once_with("contact")

    @patch("smartcard_test.SmartcardTest.detect_smartcard")
    def test_function_select_detect_card(self, mock_detect_smartcard):
        """
        Test function_select for 'detect_card' type.
        """
        mock_args = MagicMock()
        mock_args.test_type = "detect_card"
        mock_args.reader = "MyReader"
        self.sc.function_select(mock_args)
        mock_detect_smartcard.assert_called_once_with("MyReader")

    @patch("smartcard_test.SmartcardTest.send_apdu_test")
    def test_function_select_send(self, mock_send_apdu_test):
        """
        Test function_select for 'send' type.
        """
        mock_args = MagicMock()
        mock_args.test_type = "send"
        mock_args.reader = "AnotherReader"
        self.sc.function_select(mock_args)
        mock_send_apdu_test.assert_called_once_with("AnotherReader")


if __name__ == "__main__":
    unittest.main(argv=["first-arg-is-ignored"], exit=False)
