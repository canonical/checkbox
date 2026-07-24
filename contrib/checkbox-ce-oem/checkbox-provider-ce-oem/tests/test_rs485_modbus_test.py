import unittest
from io import StringIO
from unittest import mock

import rs485_modbus_test


class FakeResponse:
    def __init__(self, registers=None, is_error=False):
        self.registers = registers
        self._is_error = is_error

    def isError(self):
        return self._is_error


class FakeClient:
    def __init__(self, connect_result=True, response=None):
        self.connect_result = connect_result
        self.response = response or FakeResponse([11, 22])
        self.closed = False
        self.holding_calls = []
        self.input_calls = []

    def connect(self):
        return self.connect_result

    def close(self):
        self.closed = True

    def read_holding_registers(self, *args, **kwargs):
        self.holding_calls.append((args, kwargs))
        return self.response

    def read_input_registers(self, *args, **kwargs):
        self.input_calls.append((args, kwargs))
        return self.response


class LegacyFakeClient(FakeClient):
    def read_holding_registers(self, *args, **kwargs):
        if "slave" in kwargs:
            raise TypeError("unexpected keyword argument 'slave'")
        self.holding_calls.append((args, kwargs))
        return self.response


class NewFakeClient(FakeClient):
    def read_holding_registers(self, *args, **kwargs):
        if "slave" in kwargs or "unit" in kwargs:
            raise TypeError("unexpected unit ID keyword")
        self.holding_calls.append((args, kwargs))
        return self.response


class RS485ModbusTest(unittest.TestCase):
    """Unit tests for RS485 Modbus test helper commands."""

    def test_parse_multiple_peripherals(self):
        peripherals = rs485_modbus_test.parse_peripherals(
            "device0:/dev/ttyS0:9600:1:holding:0:2:N "
            "meter0:/dev/ttyS1:19200:2:input:10:4:E"
        )

        self.assertEqual(len(peripherals), 2)
        self.assertEqual(peripherals[0].name, "device0")
        self.assertEqual(peripherals[0].name_id, "device0")
        self.assertEqual(peripherals[0].node, "/dev/ttyS0")
        self.assertEqual(peripherals[0].node_id, "dev_ttyS0")
        self.assertEqual(peripherals[0].baudrate, 9600)
        self.assertEqual(peripherals[0].unit_id, 1)
        self.assertEqual(peripherals[0].register_type, "holding")
        self.assertEqual(peripherals[0].register_address, 0)
        self.assertEqual(peripherals[0].register_count, 2)
        self.assertEqual(peripherals[0].parity, "N")
        self.assertEqual(peripherals[1].register_type, "input")
        self.assertEqual(peripherals[1].parity, "E")

    def test_rejects_malformed_entry(self):
        with self.assertRaisesRegex(ValueError, "invalid format"):
            rs485_modbus_test.parse_peripheral("device0:/dev/ttyS0:9600")

    def test_rejects_unsupported_register_type(self):
        with self.assertRaisesRegex(ValueError, "REGISTER_TYPE"):
            rs485_modbus_test.parse_peripheral(
                "device0:/dev/ttyS0:9600:1:coil:0:2:N"
            )

    def test_list_command_prints_checkbox_resource_records(self):
        output = StringIO()
        with mock.patch("sys.stdout", output):
            rs485_modbus_test.main(
                [
                    "list",
                    "device0:/dev/ttyS0:9600:1:holding:0:2:N",
                ]
            )

        self.assertEqual(
            output.getvalue(),
            "name: device0\n"
            "name_id: device0\n"
            "node: /dev/ttyS0\n"
            "node_id: dev_ttyS0\n"
            "baudrate: 9600\n"
            "unit_id: 1\n"
            "register_type: holding\n"
            "register_address: 0\n"
            "register_count: 2\n"
            "parity: N\n\n",
        )

    def test_build_read_config(self):
        parser = rs485_modbus_test.build_parser()
        args = parser.parse_args(
            [
                "read",
                "--port",
                "/dev/ttyS0",
                "--baudrate",
                "9600",
                "--unit-id",
                "1",
                "--register-type",
                "holding",
                "--address",
                "0",
                "--count",
                "2",
                "--parity",
                "n",
            ]
        )

        config = rs485_modbus_test.build_read_config(args)

        self.assertEqual(config.port, "/dev/ttyS0")
        self.assertEqual(config.baudrate, 9600)
        self.assertEqual(config.unit_id, 1)
        self.assertEqual(config.register_type, "holding")
        self.assertEqual(config.address, 0)
        self.assertEqual(config.count, 2)
        self.assertEqual(config.parity, "N")

    def test_holding_register_read_success(self):
        config = rs485_modbus_test.ModbusReadConfig(
            "/dev/ttyS0", 9600, 1, "holding", 0, 2, "N"
        )
        client = FakeClient(response=FakeResponse([100, 200]))

        registers = rs485_modbus_test.run_modbus_read(
            config, client_factory=lambda config: client
        )

        self.assertEqual(registers, [100, 200])
        self.assertEqual(
            client.holding_calls,
            [((0,), {"count": 2, "slave": 1})],
        )
        self.assertTrue(client.closed)

    def test_input_register_read_success(self):
        config = rs485_modbus_test.ModbusReadConfig(
            "/dev/ttyS0", 9600, 1, "input", 10, 4, "E"
        )
        client = FakeClient(response=FakeResponse([1, 2, 3, 4]))

        registers = rs485_modbus_test.run_modbus_read(
            config, client_factory=lambda config: client
        )

        self.assertEqual(registers, [1, 2, 3, 4])
        self.assertEqual(
            client.input_calls,
            [((10,), {"count": 4, "slave": 1})],
        )
        self.assertTrue(client.closed)

    def test_legacy_pymodbus_unit_keyword_fallback(self):
        config = rs485_modbus_test.ModbusReadConfig(
            "/dev/ttyS0", 9600, 1, "holding", 0, 2, "N"
        )
        client = LegacyFakeClient(response=FakeResponse([10, 20]))

        registers = rs485_modbus_test.run_modbus_read(
            config, client_factory=lambda config: client
        )

        self.assertEqual(registers, [10, 20])
        self.assertEqual(
            client.holding_calls,
            [((0,), {"count": 2, "unit": 1})],
        )

    def test_new_pymodbus_device_id_keyword_fallback(self):
        config = rs485_modbus_test.ModbusReadConfig(
            "/dev/ttyS0", 9600, 1, "holding", 0, 2, "N"
        )
        client = NewFakeClient(response=FakeResponse([10, 20]))

        registers = rs485_modbus_test.run_modbus_read(
            config, client_factory=lambda config: client
        )

        self.assertEqual(registers, [10, 20])
        self.assertEqual(
            client.holding_calls,
            [((0,), {"count": 2, "device_id": 1})],
        )

    def test_modbus_error_response_fails(self):
        config = rs485_modbus_test.ModbusReadConfig(
            "/dev/ttyS0", 9600, 1, "holding", 0, 2, "N"
        )
        client = FakeClient(response=FakeResponse(is_error=True))

        with self.assertRaisesRegex(RuntimeError, "Modbus error response"):
            rs485_modbus_test.run_modbus_read(
                config, client_factory=lambda config: client
            )

        self.assertTrue(client.closed)

    def test_connection_failure_fails(self):
        config = rs485_modbus_test.ModbusReadConfig(
            "/dev/ttyS0", 9600, 1, "holding", 0, 2, "N"
        )
        client = FakeClient(connect_result=False)

        with self.assertRaisesRegex(RuntimeError, "Failed to connect"):
            rs485_modbus_test.run_modbus_read(
                config, client_factory=lambda config: client
            )

        self.assertTrue(client.closed)

    def test_unsupported_register_type_fails(self):
        config = rs485_modbus_test.ModbusReadConfig(
            "/dev/ttyS0", 9600, 1, "coil", 0, 2, "N"
        )
        client = FakeClient()

        with self.assertRaisesRegex(ValueError, "unsupported register type"):
            rs485_modbus_test.run_modbus_read(
                config, client_factory=lambda config: client
            )

        self.assertTrue(client.closed)

    @mock.patch("rs485_modbus_test.run_modbus_read")
    def test_read_command_exits_non_zero_on_read_failure(self, mock_run):
        mock_run.side_effect = RuntimeError("Failed to connect to /dev/ttyS0")

        with mock.patch("sys.stdout", StringIO()):
            with self.assertRaises(SystemExit) as cm:
                rs485_modbus_test.main(
                    [
                        "read",
                        "--port",
                        "/dev/ttyS0",
                        "--baudrate",
                        "9600",
                        "--unit-id",
                        "1",
                        "--register-type",
                        "holding",
                        "--address",
                        "0",
                        "--count",
                        "2",
                        "--parity",
                        "N",
                    ]
                )

        self.assertEqual(cm.exception.code, 1)

    def test_write_command_is_reserved(self):
        with mock.patch("sys.stdout", StringIO()):
            with self.assertRaises(SystemExit) as cm:
                rs485_modbus_test.main(["write"])

        self.assertEqual(cm.exception.code, 1)


if __name__ == "__main__":
    unittest.main()
