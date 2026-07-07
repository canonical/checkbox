import unittest
from io import StringIO
from unittest import mock

import serial
import serial_raw_uart_test


class FakeSerial:
    def __init__(self, baudrate=115200, echo=True):
        self.baudrate = baudrate
        self.echo = echo
        self.closed = False
        self.timeout = None
        self.last_write = b""
        self.reset_input_called = False
        self.reset_output_called = False

    def reset_input_buffer(self):
        self.reset_input_called = True

    def reset_output_buffer(self):
        self.reset_output_called = True

    def write(self, payload):
        self.last_write = payload

    def flush(self):
        pass

    def read(self, size):
        if self.echo:
            return self.last_write[:size]
        return b""

    def close(self):
        self.closed = True


class SerialRawUartTest(unittest.TestCase):
    """Unit tests for serial_raw_uart_test.py."""

    def test_parse_raw_uart_ports(self):
        ports = serial_raw_uart_test.parse_raw_uart_ports(
            "uart0:0x2260000:max uart1:/dev/ttyS1:115200"
        )

        self.assertEqual(len(ports), 2)
        self.assertEqual(ports[0].name, "uart0")
        self.assertEqual(ports[0].name_id, "uart0")
        self.assertEqual(ports[0].target, "0x2260000")
        self.assertEqual(ports[0].target_id, "0x2260000")
        self.assertEqual(ports[0].target_type, "addr")
        self.assertEqual(ports[0].baud, "max")
        self.assertEqual(ports[1].target_type, "node")
        self.assertEqual(ports[1].baud, 115200)

    def test_parse_raw_uart_ports_rejects_malformed_entry(self):
        with self.assertRaisesRegex(ValueError, "invalid format"):
            serial_raw_uart_test.parse_raw_uart_port("uart0:/dev/ttyS1")

    def test_parse_raw_uart_ports_rejects_bad_baud(self):
        with self.assertRaisesRegex(ValueError, "BAUD"):
            serial_raw_uart_test.parse_raw_uart_port(
                "uart0:/dev/ttyS1:not-a-baud"
            )

    def test_print_raw_uart_resources(self):
        output = StringIO()
        with mock.patch("sys.stdout", output):
            serial_raw_uart_test.print_raw_uart_resources(
                "uart0:0x2260000:max uart1:/dev/ttyS1:115200"
            )

        self.assertEqual(
            output.getvalue(),
            "name: uart0\n"
            "name_id: uart0\n"
            "target: 0x2260000\n"
            "target_id: 0x2260000\n"
            "target_type: addr\n"
            "baud: max\n\n"
            "name: uart1\n"
            "name_id: uart1\n"
            "target: /dev/ttyS1\n"
            "target_id: dev_ttyS1\n"
            "target_type: node\n"
            "baud: 115200\n\n",
        )

    def test_get_rates_to_test(self):
        self.assertEqual(
            serial_raw_uart_test.get_rates_to_test(0, 9600), [9600]
        )
        self.assertEqual(
            serial_raw_uart_test.get_rates_to_test(0, "max"), [115200]
        )
        self.assertEqual(
            serial_raw_uart_test.get_rates_to_test(115200, "sweep"),
            [9600, 19200, 38400, 57600, 115200],
        )
        self.assertEqual(
            serial_raw_uart_test.get_rates_to_test(115200, "autoscan-max"),
            [115200, 57600, 38400, 19200, 9600],
        )

    def test_get_sweep_down_rates(self):
        self.assertEqual(
            serial_raw_uart_test.get_sweep_down_rates(115200),
            [115200, 57600, 38400, 19200, 9600],
        )
        self.assertEqual(
            serial_raw_uart_test.get_sweep_down_rates(123456),
            [123456, 115200, 57600, 38400, 19200, 9600],
        )

    def test_sweep_down_requires_integer_baud(self):
        with self.assertRaisesRegex(ValueError, "requires an integer baud"):
            serial_raw_uart_test.get_sweep_down_rates("max")

    @mock.patch(
        "serial_raw_uart_test.get_driver_baud_base", return_value=3000000
    )
    @mock.patch("serial_raw_uart_test.get_active_consoles", return_value=set())
    def test_resolve_device_by_node(self, mock_consoles, mock_baud_base):
        device = serial_raw_uart_test.resolve_device("/dev/ttyS1")

        self.assertEqual(device.target, "/dev/ttyS1")
        self.assertEqual(device.dev_node, "/dev/ttyS1")
        self.assertEqual(device.baud_base, 3000000)
        self.assertFalse(device.is_console)

    @mock.patch(
        "serial_raw_uart_test.scan_available_uarts",
        return_value={"0x2260000": "/dev/ttyS0"},
    )
    @mock.patch(
        "serial_raw_uart_test.get_driver_baud_base", return_value=115200
    )
    @mock.patch("serial_raw_uart_test.get_active_consoles", return_value=set())
    def test_resolve_device_by_address(
        self, mock_consoles, mock_baud_base, mock_scan
    ):
        device = serial_raw_uart_test.resolve_device("0x2260000")

        self.assertEqual(device.target, "0x2260000")
        self.assertEqual(device.dev_node, "/dev/ttyS0")
        self.assertEqual(device.baud_base, 115200)

    def test_resolve_device_blocks_usb_serial_node(self):
        with self.assertRaisesRegex(RuntimeError, "USB serial"):
            serial_raw_uart_test.resolve_device("/dev/ttyUSB0")

    @mock.patch(
        "serial_raw_uart_test.get_active_consoles", return_value={"ttyS0"}
    )
    def test_resolve_device_blocks_console(self, mock_consoles):
        with self.assertRaisesRegex(RuntimeError, "active system console"):
            serial_raw_uart_test.resolve_device("/dev/ttyS0")

    def test_run_ping_success(self):
        serial_conn = FakeSerial(echo=True)

        self.assertTrue(serial_raw_uart_test.run_ping(serial_conn))
        self.assertTrue(serial_conn.reset_input_called)

    def test_run_ping_failure(self):
        self.assertFalse(serial_raw_uart_test.run_ping(FakeSerial(echo=False)))

    @mock.patch("os.urandom", return_value=b"abcd")
    def test_run_stress_success(self, mock_urandom):
        serial_conn = FakeSerial(echo=True)

        self.assertTrue(
            serial_raw_uart_test.run_stress(serial_conn, count=2, size=4)
        )
        self.assertTrue(serial_conn.reset_input_called)
        self.assertTrue(serial_conn.reset_output_called)

    @mock.patch("os.urandom", return_value=b"abcd")
    def test_run_stress_failure(self, mock_urandom):
        self.assertFalse(
            serial_raw_uart_test.run_stress(
                FakeSerial(echo=False), count=2, size=4
            )
        )

    @mock.patch("time.sleep")
    @mock.patch("serial.Serial")
    def test_open_serial_and_run_closes_connection(
        self, mock_serial, mock_sleep
    ):
        serial_conn = FakeSerial()
        mock_serial.return_value = serial_conn

        result = serial_raw_uart_test.open_serial_and_run(
            "/dev/ttyS0", 115200, lambda conn: conn.baudrate
        )

        self.assertEqual(result, 115200)
        self.assertTrue(serial_conn.closed)
        mock_serial.assert_called_once_with("/dev/ttyS0", 115200, timeout=1.0)

    @mock.patch("serial_raw_uart_test.open_serial_and_run")
    @mock.patch("serial_raw_uart_test.resolve_device")
    def test_run_loopback_autoscan_stops_at_first_pass(
        self, mock_resolve, mock_open
    ):
        mock_resolve.return_value = serial_raw_uart_test.UartDevice(
            "0x2260000", "/dev/ttyS0", 115200, False
        )
        mock_open.side_effect = [False, True]

        output = StringIO()
        with mock.patch("sys.stdout", output):
            results = serial_raw_uart_test.run_loopback(
                "0x2260000", "autoscan-max", "quick"
            )

        self.assertEqual(
            [result.baud_rate for result in results], [115200, 57600]
        )
        self.assertFalse(results[0].passed)
        self.assertTrue(results[1].passed)
        self.assertIn("Max working baud: 57600", output.getvalue())

    @mock.patch("serial_raw_uart_test.open_serial_and_run")
    @mock.patch("serial_raw_uart_test.resolve_device")
    def test_run_loopback_sweep_down(self, mock_resolve, mock_open):
        mock_resolve.return_value = serial_raw_uart_test.UartDevice(
            "/dev/ttyS0", "/dev/ttyS0", 4000000, False
        )
        mock_open.return_value = True

        with mock.patch("sys.stdout", StringIO()):
            results = serial_raw_uart_test.run_loopback(
                "/dev/ttyS0", 115200, "quick", sweep_down=True
            )

        self.assertEqual(
            [result.baud_rate for result in results],
            [115200, 57600, 38400, 19200, 9600],
        )

    @mock.patch("serial_raw_uart_test.run_loopback")
    def test_quick_command_exits_nonzero_on_failure(self, mock_run_loopback):
        mock_run_loopback.return_value = [
            serial_raw_uart_test.LoopbackResult(115200, False, "FAILED")
        ]

        with self.assertRaises(SystemExit) as cm:
            serial_raw_uart_test.main(
                ["quick", "--target", "/dev/ttyS0", "--baud", "115200"]
            )

        self.assertEqual(cm.exception.code, 1)

    @mock.patch("serial_raw_uart_test.run_loopback")
    def test_stress_command_uses_count_and_size(self, mock_run_loopback):
        mock_run_loopback.return_value = [
            serial_raw_uart_test.LoopbackResult(115200, True, "PASSED")
        ]

        serial_raw_uart_test.main(
            [
                "stress",
                "--target",
                "/dev/ttyS0",
                "--baud",
                "115200",
                "--count",
                "50",
                "--size",
                "512",
            ]
        )

        mock_run_loopback.assert_called_once_with(
            "/dev/ttyS0",
            115200,
            "stress",
            stress_count=50,
            stress_size=512,
            sweep_down=False,
        )

    @mock.patch("serial_raw_uart_test.run_loopback")
    def test_quick_command_uses_sweep_down(self, mock_run_loopback):
        mock_run_loopback.return_value = [
            serial_raw_uart_test.LoopbackResult(115200, True, "PASSED")
        ]

        serial_raw_uart_test.main(
            [
                "quick",
                "--target",
                "/dev/ttyS0",
                "--baud",
                "115200",
                "--sweep-down",
            ]
        )

        mock_run_loopback.assert_called_once_with(
            "/dev/ttyS0",
            115200,
            "quick",
            sweep_down=True,
        )

    @mock.patch("serial_raw_uart_test.run_loopback")
    def test_stress_command_uses_sweep_down(self, mock_run_loopback):
        mock_run_loopback.return_value = [
            serial_raw_uart_test.LoopbackResult(115200, True, "PASSED")
        ]

        serial_raw_uart_test.main(
            [
                "stress",
                "--target",
                "/dev/ttyS0",
                "--baud",
                "115200",
                "--count",
                "50",
                "--size",
                "512",
                "--sweep-down",
            ]
        )

        mock_run_loopback.assert_called_once_with(
            "/dev/ttyS0",
            115200,
            "stress",
            stress_count=50,
            stress_size=512,
            sweep_down=True,
        )

    def test_serial_exception_is_available_for_mocks(self):
        self.assertTrue(hasattr(serial, "SerialException"))


if __name__ == "__main__":
    unittest.main()
