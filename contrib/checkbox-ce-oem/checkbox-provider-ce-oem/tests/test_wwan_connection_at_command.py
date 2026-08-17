import importlib
import itertools
import os
import unittest
from unittest.mock import MagicMock, patch

import wwan_connection_at_command as wcac


class FakeSerial:
    """A minimal fake serial.Serial for testing ModemAtController."""

    def __init__(self, lines=()):
        self._lines = list(lines)
        self.written = []
        self.closed = False

    def reset_input_buffer(self):
        pass

    def write(self, data):
        self.written.append(data)

    def flush(self):
        pass

    def readline(self):
        if self._lines:
            return (self._lines.pop(0) + "\r\n").encode("utf-8")
        return b""

    def close(self):
        self.closed = True


def make_modem(lines=()):
    """Build a ModemAtController with a FakeSerial already attached."""
    modem = wcac.ModemAtController("/dev/ttyUSB2")
    modem.ser = FakeSerial(lines)
    return modem


class TestModemAtControllerLifecycle(unittest.TestCase):
    @patch("wwan_connection_at_command.serial.Serial")
    def test_open_creates_serial_and_disables_echo(self, mock_serial_cls):
        fake_ser = MagicMock()
        fake_ser.readline.side_effect = [b"OK\r\n"]
        mock_serial_cls.return_value = fake_ser
        modem = wcac.ModemAtController("/dev/ttyUSB2")

        result = modem.open()

        self.assertIs(result, modem)
        self.assertIs(modem.ser, fake_ser)
        mock_serial_cls.assert_called_once_with(
            "/dev/ttyUSB2", baudrate=115200, timeout=2
        )
        fake_ser.write.assert_called_once_with(b"ATE0\r\n")

    def test_close_closes_serial_and_clears_it(self):
        modem = wcac.ModemAtController("/dev/ttyUSB2")
        fake_ser = MagicMock()
        modem.ser = fake_ser

        modem.close()

        fake_ser.close.assert_called_once()
        self.assertIsNone(modem.ser)

    def test_close_is_a_noop_when_never_opened(self):
        modem = wcac.ModemAtController("/dev/ttyUSB2")
        modem.close()  # must not raise
        self.assertIsNone(modem.ser)

    @patch("wwan_connection_at_command.serial.Serial")
    def test_context_manager_opens_and_closes(self, mock_serial_cls):
        fake_ser = MagicMock()
        fake_ser.readline.side_effect = [b"OK\r\n"]
        mock_serial_cls.return_value = fake_ser

        with wcac.ModemAtController("/dev/ttyUSB2") as modem:
            self.assertIs(modem.ser, fake_ser)

        fake_ser.close.assert_called_once()

    @patch("wwan_connection_at_command.time.sleep", return_value=None)
    @patch("wwan_connection_at_command.serial.Serial")
    def test_open_polling_retries_until_available(
        self, mock_serial_cls, mock_sleep
    ):
        fake_ser = MagicMock()
        fake_ser.readline.side_effect = [b"OK\r\n"]
        mock_serial_cls.side_effect = [
            wcac.serial.SerialException("busy"),
            fake_ser,
        ]
        modem = wcac.ModemAtController("/dev/ttyUSB2")

        result = modem.open_polling(timeout=10, interval=1)

        self.assertIs(result, modem)
        self.assertIs(modem.ser, fake_ser)

    @patch(
        "wwan_connection_at_command.time.time",
        side_effect=itertools.count(1000, 50),
    )
    @patch("wwan_connection_at_command.time.sleep", return_value=None)
    @patch("wwan_connection_at_command.serial.Serial")
    def test_open_polling_gives_up_after_timeout(
        self, mock_serial_cls, mock_sleep, mock_time
    ):
        mock_serial_cls.side_effect = wcac.serial.SerialException("busy")
        modem = wcac.ModemAtController("/dev/ttyUSB2")

        self.assertIsNone(modem.open_polling(timeout=5))


class TestSendCommand(unittest.TestCase):
    def test_returns_ok_response(self):
        modem = make_modem(["+CSQ: 15,0", "", "OK"])
        rc, raw = modem.send_command("AT+CSQ")
        self.assertEqual(rc, 0)
        self.assertIn("+CSQ: 15,0", raw)
        self.assertIn("OK", raw)

    def test_returns_error_response(self):
        modem = make_modem(["ERROR"])
        rc, raw = modem.send_command("AT+BOGUS")
        self.assertEqual(rc, 1)
        self.assertIn("ERROR", raw)

    def test_skips_echoed_command_line(self):
        modem = make_modem(["AT+CSQ", "+CSQ: 15,0", "OK"])
        rc, raw = modem.send_command("AT+CSQ")
        self.assertEqual(rc, 0)
        self.assertNotIn("AT+CSQ", raw.splitlines())

    def test_writes_command_with_crlf(self):
        modem = make_modem(["OK"])
        modem.send_command("AT")
        self.assertEqual(modem.ser.written, [b"AT\r\n"])

    @patch(
        "wwan_connection_at_command.time.time",
        side_effect=itertools.count(1000, 50),
    )
    def test_times_out_without_terminator(self, mock_time):
        modem = make_modem([])
        rc, raw = modem.send_command("AT", timeout=5)
        self.assertEqual(rc, 1)


class TestParseAtResponse(unittest.TestCase):
    def test_strips_ok_terminator(self):
        self.assertEqual(
            wcac.parse_at_response("+CSQ: 15,0\nOK"), "+CSQ: 15,0"
        )

    def test_strips_error_terminator(self):
        self.assertEqual(wcac.parse_at_response("ERROR"), "")

    def test_returns_empty_for_bare_ok(self):
        self.assertEqual(wcac.parse_at_response("OK"), "")


class TestQuery(unittest.TestCase):
    @patch("wwan_connection_at_command.ModemAtController.send_command")
    def test_returns_parsed_response_on_success(self, mock_send):
        mock_send.return_value = (0, "+CSQ: 15,0\nOK")
        modem = wcac.ModemAtController("/dev/ttyUSB2")
        self.assertEqual(modem.query("AT+CSQ"), "+CSQ: 15,0")

    @patch("wwan_connection_at_command.ModemAtController.send_command")
    def test_returns_none_on_failure(self, mock_send):
        mock_send.return_value = (1, "ERROR")
        modem = wcac.ModemAtController("/dev/ttyUSB2")
        self.assertIsNone(modem.query("AT+CSQ"))


class TestResolveConfigPath(unittest.TestCase):
    @patch(
        "wwan_connection_at_command.WWAN_AT_COMMAND_DATA_DIR",
        "/var/tmp/checkbox-providers/checkbox-provider-ce-oem/data"
        "/wwan_at_command",
    )
    def test_bare_filename_resolved_against_data_dir(self):
        self.assertEqual(
            wcac.resolve_config_path("SIM7672G-LNGV_wwan_at_command.json"),
            "/var/tmp/checkbox-providers/checkbox-provider-ce-oem/data"
            "/wwan_at_command/SIM7672G-LNGV_wwan_at_command.json",
        )

    def test_absolute_path_used_as_is(self):
        self.assertEqual(
            wcac.resolve_config_path("/etc/wwan/custom.json"),
            "/etc/wwan/custom.json",
        )

    def test_relative_path_with_separator_used_as_is(self):
        self.assertEqual(
            wcac.resolve_config_path("configs/custom.json"),
            "configs/custom.json",
        )


class TestDefaultConfigFromEnv(unittest.TestCase):
    """Exercise the module-level DEFAULT_CONFIG wiring itself.

    DEFAULT_CONFIG is computed once at import time from
    WWAN_AT_COMMAND_JSON/PLAINBOX_PROVIDER_DATA, so these tests reload
    the module under controlled environment variables and always
    reload it back to a clean state afterwards.
    """

    def _reload_with_env(self, env):
        with patch.dict(os.environ, env, clear=False):
            importlib.reload(wcac)

    def tearDown(self):
        importlib.reload(wcac)

    def test_bare_filename_env_resolves_under_data_dir(self):
        self._reload_with_env(
            {
                "PLAINBOX_PROVIDER_DATA": "/var/tmp/checkbox-providers"
                "/checkbox-provider-ce-oem/data",
                "WWAN_AT_COMMAND_JSON": "SIM7672G-LNGV_wwan_at_command.json",
            }
        )
        self.assertEqual(
            wcac.DEFAULT_CONFIG,
            "/var/tmp/checkbox-providers/checkbox-provider-ce-oem/data"
            "/wwan_at_command/SIM7672G-LNGV_wwan_at_command.json",
        )

    def test_full_path_env_used_as_is(self):
        self._reload_with_env(
            {"WWAN_AT_COMMAND_JSON": "/etc/wwan/custom.json"}
        )
        self.assertEqual(wcac.DEFAULT_CONFIG, "/etc/wwan/custom.json")

    def test_unset_env_gives_no_default(self):
        with patch.dict(os.environ, {}, clear=False) as _:
            os.environ.pop("WWAN_AT_COMMAND_JSON", None)
            importlib.reload(wcac)
        self.assertIsNone(wcac.DEFAULT_CONFIG)


class TestMainConfigValidation(unittest.TestCase):
    def test_exits_when_no_control_if_set(self):
        env = dict(os.environ)
        env.pop("WWAN_CONTROL_IF", None)
        test_argv = ["wwan_connection_at_command.py"]
        with patch.dict(os.environ, env, clear=True):
            with patch("sys.argv", test_argv):
                with self.assertRaises(SystemExit) as ctx:
                    wcac.main()
        self.assertEqual(ctx.exception.code, 1)

    @patch.object(wcac, "DEFAULT_CONFIG", None)
    @patch.dict(os.environ, {"WWAN_CONTROL_IF": "/dev/ttyUSB2"})
    def test_exits_when_no_config_available(self):
        test_argv = ["wwan_connection_at_command.py"]
        with patch("sys.argv", test_argv):
            with self.assertRaises(SystemExit) as ctx:
                wcac.main()
        self.assertEqual(ctx.exception.code, 1)

    @patch(
        "wwan_connection_at_command.ModemAtController.ensure_radio_enabled",
        return_value=False,
    )
    @patch("wwan_connection_at_command.ModemAtController.detect_module")
    @patch("wwan_connection_at_command.ModemAtController.close")
    @patch("wwan_connection_at_command.ModemAtController.open")
    @patch("wwan_connection_at_command.load_config", return_value={})
    @patch.dict(
        os.environ,
        {
            "WWAN_APN": "internet",
            "WWAN_NET_IF": "enx0",
            "WWAN_CONTROL_IF": "/dev/ttyUSB2",
        },
    )
    def test_exits_when_radio_cannot_be_enabled(
        self,
        mock_load_config,
        mock_open,
        mock_close,
        mock_detect_module,
        mock_ensure_enabled,
    ):
        mock_detect_module.return_value = ("SIM7672G-LNGV", {})
        test_argv = [
            "wwan_connection_at_command.py",
            "--config",
            "/tmp/wwan_at_command.json",
        ]
        with patch("sys.argv", test_argv):
            with self.assertRaises(SystemExit) as ctx:
                wcac.main()
        self.assertEqual(ctx.exception.code, 1)
        mock_ensure_enabled.assert_called_once()
        mock_close.assert_called_once()


class TestDetectModule(unittest.TestCase):
    @patch("wwan_connection_at_command.ModemAtController.send_command")
    def test_matches_first_known_module(self, mock_send):
        mock_send.return_value = (
            0,
            "SIMCOM_INCORPORATED\nSIM7672G-LNGV\nOK",
        )
        config = {"SIM7672G-LNGV": {"Set auto-dial": "AT+DIALMODE=0"}}
        modem = wcac.ModemAtController("/dev/ttyUSB2")
        name, steps = modem.detect_module(config)
        self.assertEqual(name, "SIM7672G-LNGV")
        self.assertEqual(steps, config["SIM7672G-LNGV"])

    @patch("wwan_connection_at_command.ModemAtController.send_command")
    def test_exits_when_no_module_matches(self, mock_send):
        mock_send.return_value = (0, "UNKNOWN_MODEL\nOK")
        modem = wcac.ModemAtController("/dev/ttyUSB2")
        with self.assertRaises(SystemExit):
            modem.detect_module({"SIM7672G-LNGV": {}})

    @patch("wwan_connection_at_command.ModemAtController.send_command")
    def test_exits_when_ati_fails(self, mock_send):
        mock_send.return_value = (1, "ERROR")
        modem = wcac.ModemAtController("/dev/ttyUSB2")
        with self.assertRaises(SystemExit):
            modem.detect_module({"SIM7672G-LNGV": {}})


class TestGetCfunState(unittest.TestCase):
    @patch("wwan_connection_at_command.ModemAtController.query")
    def test_parses_cfun_value(self, mock_query):
        mock_query.return_value = "+CFUN: 1"
        modem = wcac.ModemAtController("/dev/ttyUSB2")
        self.assertEqual(modem.get_cfun_state(), 1)

    @patch(
        "wwan_connection_at_command.ModemAtController.query",
        return_value=None,
    )
    def test_returns_none_when_query_fails(self, mock_query):
        modem = wcac.ModemAtController("/dev/ttyUSB2")
        self.assertIsNone(modem.get_cfun_state())


class TestEnsureRadioEnabled(unittest.TestCase):
    @patch("wwan_connection_at_command.ModemAtController.send_command")
    @patch(
        "wwan_connection_at_command.ModemAtController.query",
        return_value="+CFUN: 1",
    )
    def test_already_enabled_skips_enable_command(self, mock_query, mock_send):
        modem = wcac.ModemAtController("/dev/ttyUSB2")
        self.assertTrue(modem.ensure_radio_enabled())
        mock_send.assert_not_called()

    @patch("wwan_connection_at_command.ModemAtController.send_command")
    @patch("wwan_connection_at_command.ModemAtController.query")
    def test_enables_when_not_already_enabled(self, mock_query, mock_send):
        mock_query.side_effect = ["+CFUN: 4", "+CFUN: 1"]
        mock_send.return_value = (0, "OK")
        modem = wcac.ModemAtController("/dev/ttyUSB2")
        self.assertTrue(modem.ensure_radio_enabled())
        mock_send.assert_called_once_with("AT+CFUN=1", timeout=10)

    @patch("wwan_connection_at_command.ModemAtController.send_command")
    @patch(
        "wwan_connection_at_command.ModemAtController.query",
        return_value="+CFUN: 4",
    )
    def test_fails_when_enable_command_fails(self, mock_query, mock_send):
        mock_send.return_value = (1, "ERROR")
        modem = wcac.ModemAtController("/dev/ttyUSB2")
        self.assertFalse(modem.ensure_radio_enabled())

    @patch("wwan_connection_at_command.ModemAtController.send_command")
    @patch("wwan_connection_at_command.ModemAtController.query")
    def test_fails_when_still_not_enabled_after_command(
        self, mock_query, mock_send
    ):
        mock_query.side_effect = ["+CFUN: 4", "+CFUN: 4"]
        mock_send.return_value = (0, "OK")
        modem = wcac.ModemAtController("/dev/ttyUSB2")
        self.assertFalse(modem.ensure_radio_enabled())


class TestRunAtStep(unittest.TestCase):
    ENV = {"WWAN_APN": "internet", "WWAN_NET_IF": "enx0"}

    def _modem(self):
        return wcac.ModemAtController("/dev/ttyUSB2")

    @patch("wwan_connection_at_command.ModemAtController.send_command")
    def test_plain_string_step_passes_on_any_response(self, mock_send):
        mock_send.return_value = (0, "OK")
        modem = self._modem()
        self.assertTrue(
            modem.run_at_step("Set auto-dial", "AT+DIALMODE=0", self.ENV)
        )

    @patch("wwan_connection_at_command.ModemAtController.send_command")
    def test_plain_string_step_fails_on_nonzero_rc(self, mock_send):
        mock_send.return_value = (1, "ERROR")
        modem = self._modem()
        self.assertFalse(
            modem.run_at_step("Set auto-dial", "AT+DIALMODE=0", self.ENV)
        )

    @patch("wwan_connection_at_command.ModemAtController.send_command")
    def test_apn_placeholder_is_substituted(self, mock_send):
        mock_send.return_value = (0, "OK")
        modem = self._modem()
        modem.run_at_step("Set APN", 'AT+CGDCONT=1,"IP","{APN}"', self.ENV)
        sent_cmd = mock_send.call_args[0][0]
        self.assertEqual(sent_cmd, 'AT+CGDCONT=1,"IP","internet"')

    @patch("wwan_connection_at_command.ModemAtController.send_command")
    def test_expect_substring_pass_and_fail(self, mock_send):
        spec = {"cmd": "AT+CPIN?", "expect": "READY"}
        modem = self._modem()
        mock_send.return_value = (0, "+CPIN: READY\nOK")
        self.assertTrue(modem.run_at_step("SIM status", spec, self.ENV))

        mock_send.return_value = (0, "+CPIN: SIM PIN\nOK")
        self.assertFalse(modem.run_at_step("SIM status", spec, self.ENV))

    @patch("wwan_connection_at_command.ModemAtController.send_command")
    def test_expect_nonempty_pass_and_fail(self, mock_send):
        spec = {"cmd": "AT+CGPADDR=1", "expect_nonempty": True}
        modem = self._modem()
        mock_send.return_value = (0, "+CGPADDR: 1,10.0.0.5\nOK")
        self.assertTrue(modem.run_at_step("Verify IP", spec, self.ENV))

        mock_send.return_value = (0, "OK")
        self.assertFalse(modem.run_at_step("Verify IP", spec, self.ENV))

    @patch("wwan_connection_at_command.ModemAtController.send_command")
    def test_expect_min_pass_and_fail(self, mock_send):
        spec = {"cmd": "AT+CSQ", "expect_min": 10}
        modem = self._modem()
        mock_send.return_value = (0, "+CSQ: 15,0\nOK")
        self.assertTrue(modem.run_at_step("Signal quality", spec, self.ENV))

        mock_send.return_value = (0, "+CSQ: 3,0\nOK")
        self.assertFalse(modem.run_at_step("Signal quality", spec, self.ENV))

    @patch("time.sleep", return_value=None)
    @patch("wwan_connection_at_command.ModemAtController.send_command")
    def test_poll_retries_until_pass(self, mock_send, mock_sleep):
        spec = {"cmd": "AT+CGATT?", "expect": "CGATT: 1", "poll": True}
        mock_send.side_effect = [
            (0, "+CGATT: 0\nOK"),
            (0, "+CGATT: 1\nOK"),
        ]
        modem = self._modem()
        self.assertTrue(
            modem.run_at_step("Verify GPRS attachment", spec, self.ENV)
        )
        self.assertEqual(mock_send.call_count, 2)
        mock_sleep.assert_called_once()

    @patch("time.sleep", return_value=None)
    @patch(
        "wwan_connection_at_command.time.time",
        side_effect=itertools.count(1000, 50),
    )
    @patch("wwan_connection_at_command.ModemAtController.send_command")
    def test_poll_gives_up_after_deadline(
        self, mock_send, mock_time, mock_sleep
    ):
        spec = {"cmd": "AT+CGATT?", "expect": "CGATT: 1", "poll": True}
        mock_send.return_value = (0, "+CGATT: 0\nOK")
        modem = self._modem()
        self.assertFalse(
            modem.run_at_step("Verify GPRS attachment", spec, self.ENV)
        )


class TestDeprioritizeDefaultRoute(unittest.TestCase):
    @patch("wwan_connection_at_command.run_cmd")
    def test_lowers_metric_of_existing_default_route(self, mock_run_cmd):
        mock_run_cmd.side_effect = [
            (
                0,
                "default via 192.168.0.1 dev enx0 proto dhcp metric 100\n",
                "",
            ),
            (0, "", ""),
        ]
        wcac.deprioritize_default_route("enx0", metric=200)
        replace_call = mock_run_cmd.call_args_list[1][0][0]
        self.assertEqual(
            replace_call,
            [
                "ip",
                "route",
                "replace",
                "default",
                "via",
                "192.168.0.1",
                "dev",
                "enx0",
                "metric",
                "200",
            ],
        )

    @patch("wwan_connection_at_command.run_cmd")
    def test_noop_when_no_default_route(self, mock_run_cmd):
        mock_run_cmd.return_value = (0, "", "")
        wcac.deprioritize_default_route("enx0")
        self.assertEqual(mock_run_cmd.call_count, 1)


class TestRegistrationParsing(unittest.TestCase):
    def _modem(self):
        return wcac.ModemAtController("/dev/ttyUSB2")

    @patch("wwan_connection_at_command.ModemAtController.query")
    def test_get_registration_maps_stat_codes(self, mock_query):
        mock_query.return_value = "+CREG: 0,5"
        modem = self._modem()
        self.assertEqual(modem.get_registration(), "roaming")

    @patch(
        "wwan_connection_at_command.ModemAtController.query",
        return_value=None,
    )
    def test_get_registration_returns_none_on_failure(self, mock_query):
        modem = self._modem()
        self.assertIsNone(modem.get_registration())

    @patch("wwan_connection_at_command.ModemAtController.query")
    @patch("wwan_connection_at_command.ModemAtController.send_command")
    def test_get_operator_id_extracts_numeric_plmn(
        self, mock_send, mock_query
    ):
        mock_query.return_value = '+COPS: 0,2,"46697",7'
        modem = self._modem()
        self.assertEqual(modem.get_operator_id(), "46697")
        mock_send.assert_called_once_with("AT+COPS=3,2", timeout=5)


class TestResetRecoveryHelpers(unittest.TestCase):
    def _modem(self):
        return wcac.ModemAtController("/dev/ttyUSB2")

    @patch("wwan_connection_at_command.ModemAtController.send_command")
    def test_send_reset_pass_and_fail(self, mock_send):
        modem = self._modem()
        mock_send.return_value = (0, "OK")
        self.assertTrue(modem.send_reset())

        mock_send.return_value = (1, "ERROR")
        self.assertFalse(modem.send_reset())

    @patch("wwan_connection_at_command.ModemAtController.send_command")
    def test_verify_cops_pass_and_fail(self, mock_send):
        modem = self._modem()
        mock_send.return_value = (0, "+COPS: 0,,,7\nOK")
        self.assertTrue(modem.verify_cops(timeout=30))

        mock_send.return_value = (1, "")
        self.assertFalse(modem.verify_cops(timeout=30))

    @patch("time.sleep", return_value=None)
    @patch("wwan_connection_at_command.ModemAtController.send_command")
    def test_radio_cycle_sends_cfun_off_then_on(self, mock_send, mock_sleep):
        modem = self._modem()
        modem.radio_cycle(wait_seconds=45)
        sent_cmds = [call.args[0] for call in mock_send.call_args_list]
        self.assertEqual(sent_cmds, ["AT+CFUN=4", "AT+CFUN=1"])
        mock_sleep.assert_any_call(45)

    @patch("time.sleep", return_value=None)
    @patch("wwan_connection_at_command.ModemAtController.get_operator_id")
    @patch("wwan_connection_at_command.ModemAtController.get_registration")
    def test_wait_for_registration_passes_immediately(
        self, mock_get_reg, mock_get_op, mock_sleep
    ):
        mock_get_reg.return_value = "roaming"
        mock_get_op.return_value = "46697"
        modem = self._modem()
        ok, registration, operator_id = modem.wait_for_registration(
            timeout=120, radio_cycle_wait=45
        )
        self.assertTrue(ok)
        self.assertEqual(registration, "roaming")
        self.assertEqual(operator_id, "46697")

    @patch("wwan_connection_at_command.ModemAtController.radio_cycle")
    @patch("time.sleep", return_value=None)
    @patch(
        "wwan_connection_at_command.time.time",
        side_effect=itertools.count(1000, 200),
    )
    @patch("wwan_connection_at_command.ModemAtController.get_operator_id")
    @patch("wwan_connection_at_command.ModemAtController.get_registration")
    def test_wait_for_registration_cycles_radio_once_then_passes(
        self,
        mock_get_reg,
        mock_get_op,
        mock_time,
        mock_sleep,
        mock_radio_cycle,
    ):
        # denied first (triggers exactly one radio cycle), then roaming
        mock_get_reg.side_effect = ["denied", "roaming"]
        mock_get_op.side_effect = [None, "46697"]
        modem = self._modem()
        ok, registration, operator_id = modem.wait_for_registration(
            timeout=120, radio_cycle_wait=45
        )
        self.assertTrue(ok)
        self.assertEqual(registration, "roaming")
        mock_radio_cycle.assert_called_once_with(45)

    @patch("wwan_connection_at_command.ModemAtController.radio_cycle")
    @patch("time.sleep", return_value=None)
    @patch(
        "wwan_connection_at_command.time.time",
        side_effect=itertools.count(1000, 200),
    )
    @patch(
        "wwan_connection_at_command.ModemAtController.get_operator_id",
        return_value=None,
    )
    @patch(
        "wwan_connection_at_command.ModemAtController.get_registration",
        return_value="denied",
    )
    def test_wait_for_registration_fails_after_one_cycle(
        self,
        mock_get_reg,
        mock_get_op,
        mock_time,
        mock_sleep,
        mock_radio_cycle,
    ):
        modem = self._modem()
        ok, registration, operator_id = modem.wait_for_registration(
            timeout=120, radio_cycle_wait=45
        )
        self.assertFalse(ok)
        self.assertEqual(registration, "denied")
        mock_radio_cycle.assert_called_once_with(45)


class TestResetAndRecover(unittest.TestCase):
    @patch(
        "wwan_connection_at_command.ModemAtController" ".wait_for_registration"
    )
    @patch(
        "wwan_connection_at_command.ModemAtController.verify_cops",
        return_value=True,
    )
    @patch("wwan_connection_at_command.ModemAtController.open_polling")
    @patch(
        "wwan_connection_at_command.ModemAtController.send_reset",
        return_value=True,
    )
    @patch("wwan_connection_at_command.ModemAtController.close")
    @patch("wwan_connection_at_command.ModemAtController.open")
    def test_happy_path(
        self,
        mock_open,
        mock_close,
        mock_send_reset,
        mock_poll,
        mock_verify_cops,
        mock_wait_registration,
    ):
        mock_wait_registration.return_value = (True, "roaming", "46697")
        self.assertTrue(wcac.reset_and_recover("/dev/ttyUSB2"))
        mock_send_reset.assert_called_once()
        self.assertEqual(mock_close.call_count, 2)
        mock_verify_cops.assert_called_once()
        mock_wait_registration.assert_called_once()

    @patch(
        "wwan_connection_at_command.ModemAtController.send_reset",
        return_value=False,
    )
    @patch("wwan_connection_at_command.ModemAtController.close")
    @patch("wwan_connection_at_command.ModemAtController.open")
    def test_fails_fast_when_reset_command_rejected(
        self, mock_open, mock_close, mock_send_reset
    ):
        self.assertFalse(wcac.reset_and_recover("/dev/ttyUSB2"))

    @patch(
        "wwan_connection_at_command.ModemAtController.open_polling",
        return_value=None,
    )
    @patch(
        "wwan_connection_at_command.ModemAtController.send_reset",
        return_value=True,
    )
    @patch("wwan_connection_at_command.ModemAtController.close")
    @patch("wwan_connection_at_command.ModemAtController.open")
    def test_fails_when_control_port_never_reappears(
        self, mock_open, mock_close, mock_send_reset, mock_poll
    ):
        self.assertFalse(wcac.reset_and_recover("/dev/ttyUSB2"))

    @patch(
        "wwan_connection_at_command.ModemAtController.verify_cops",
        return_value=False,
    )
    @patch("wwan_connection_at_command.ModemAtController.open_polling")
    @patch(
        "wwan_connection_at_command.ModemAtController.send_reset",
        return_value=True,
    )
    @patch("wwan_connection_at_command.ModemAtController.close")
    @patch("wwan_connection_at_command.ModemAtController.open")
    def test_fails_when_cops_never_responds(
        self,
        mock_open,
        mock_close,
        mock_send_reset,
        mock_poll,
        mock_verify_cops,
    ):
        self.assertFalse(wcac.reset_and_recover("/dev/ttyUSB2"))


class TestRunPing(unittest.TestCase):
    @patch("wwan_connection_at_command.run_cmd")
    def test_fails_fast_when_link_up_fails(self, mock_run_cmd):
        mock_run_cmd.return_value = (1, "", "no such device")
        self.assertFalse(wcac.run_ping("enx0", MagicMock()))

    @patch("wwan_connection_at_command.deprioritize_default_route")
    @patch("wwan_connection_at_command.run_cmd")
    def test_passes_when_ip_and_ping_succeed(
        self, mock_run_cmd, mock_deprioritize
    ):
        def fake_run_cmd(args):
            if args[:3] == ["ip", "link", "set"]:
                return (0, "", "")
            if args[:2] == ["nmcli", "device"]:
                return (0, "", "")
            if args[:3] == ["ip", "addr", "show"]:
                return (0, "inet 192.168.0.100/24 brd 192.168.0.255\n", "")
            if args[0] == "ping":
                return (0, "4 packets transmitted, 4 received, 0% loss\n", "")
            return (0, "", "")

        mock_run_cmd.side_effect = fake_run_cmd
        self.assertTrue(wcac.run_ping("enx0", MagicMock()))
        mock_deprioritize.assert_called_once_with("enx0")

    @patch("time.sleep", return_value=None)
    @patch("wwan_connection_at_command.run_cmd")
    def test_fails_when_no_ip_assigned(self, mock_run_cmd, mock_sleep):
        def fake_run_cmd(args):
            if args[:3] == ["ip", "link", "set"]:
                return (0, "", "")
            if args[:2] == ["nmcli", "device"]:
                return (0, "", "")
            if args[:3] == ["ip", "addr", "show"]:
                return (0, "no inet here\n", "")
            return (0, "", "")

        mock_run_cmd.side_effect = fake_run_cmd
        modem = MagicMock()
        with patch("os.environ.get", return_value="0"):
            self.assertFalse(wcac.run_ping("enx0", modem))
        modem.log_connection_diagnostics.assert_called_once_with("enx0")


if __name__ == "__main__":
    unittest.main()
