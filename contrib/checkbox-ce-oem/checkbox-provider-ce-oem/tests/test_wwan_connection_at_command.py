import itertools
import unittest
from unittest.mock import patch

import wwan_connection_at_command as wcac


class TestParseResponse(unittest.TestCase):
    def test_extracts_quoted_value(self):
        output = "response: '+COPS: 0,,,7'\n"
        self.assertEqual(wcac.parse_response(output), "+COPS: 0,,,7")

    def test_extracts_empty_value(self):
        output = "response: ''\n"
        self.assertEqual(wcac.parse_response(output), "")

    def test_returns_none_when_missing(self):
        output = "error: couldn't find modem\n"
        self.assertIsNone(wcac.parse_response(output))


class TestGetField(unittest.TestCase):
    MMCLI_OUTPUT = (
        "  --------------------------------\n"
        "  Hardware |         manufacturer: SIMCOM INCORPORATED\n"
        "           |         equipment id: 865031064538696\n"
        "  --------------------------------\n"
        "  Status   |                state: disabled\n"
        "           |          power state: on\n"
        "  --------------------------------\n"
        "  3GPP     |         registration: roaming\n"
        "           |          operator id: 46697\n"
    )

    @patch("wwan_connection_at_command.run_cmd")
    def test_extracts_named_field(self, mock_run_cmd):
        mock_run_cmd.return_value = (0, self.MMCLI_OUTPUT, "")
        self.assertEqual(wcac.get_field(0, "equipment id"), "865031064538696")
        self.assertEqual(wcac.get_field(0, "registration"), "roaming")
        self.assertEqual(wcac.get_field(0, "operator id"), "46697")

    @patch("wwan_connection_at_command.run_cmd")
    def test_state_is_not_confused_with_power_state(self, mock_run_cmd):
        # Regression test: "power state: on" must not match a lookup
        # for the "state" field.
        mock_run_cmd.return_value = (0, self.MMCLI_OUTPUT, "")
        self.assertEqual(wcac.get_field(0, "state"), "disabled")

    @patch("wwan_connection_at_command.run_cmd")
    def test_returns_none_on_nonzero_rc(self, mock_run_cmd):
        mock_run_cmd.return_value = (1, "", "error")
        self.assertIsNone(wcac.get_field(0, "state"))

    @patch("wwan_connection_at_command.run_cmd")
    def test_returns_none_when_field_absent(self, mock_run_cmd):
        mock_run_cmd.return_value = (0, self.MMCLI_OUTPUT, "")
        self.assertIsNone(wcac.get_field(0, "nonexistent field"))


class TestModemDiscovery(unittest.TestCase):
    MMCLI_LIST_OUTPUT = (
        "/org/freedesktop/ModemManager1/Modem/0 [SIMCOM] SIM7672G-LNGV\n"
        "/org/freedesktop/ModemManager1/Modem/2 [SIMCOM] SIM7672G-LNGV\n"
    )

    @patch("wwan_connection_at_command.mmcli_list")
    def test_mmcli_modem_ids_parses_all_indices(self, mock_list):
        mock_list.return_value = (0, self.MMCLI_LIST_OUTPUT)
        self.assertEqual(wcac.mmcli_modem_ids(), [0, 2])

    @patch("wwan_connection_at_command.mmcli_list")
    def test_mmcli_modem_ids_exits_on_failure(self, mock_list):
        mock_list.return_value = (1, "")
        with self.assertRaises(SystemExit):
            wcac.mmcli_modem_ids()

    @patch("wwan_connection_at_command.get_equipment_id")
    @patch("wwan_connection_at_command.mmcli_modem_ids")
    def test_resolve_modem_index_matches_by_equipment_id(
        self, mock_ids, mock_eq_id
    ):
        mock_ids.return_value = [0, 2]
        mock_eq_id.side_effect = lambda mm_id: {
            0: "111111111111111",
            2: "865031064538696",
        }[mm_id]
        self.assertEqual(wcac.resolve_modem_index("865031064538696"), 2)

    @patch("wwan_connection_at_command.get_equipment_id")
    @patch("wwan_connection_at_command.mmcli_modem_ids")
    def test_resolve_modem_index_exits_when_not_found(
        self, mock_ids, mock_eq_id
    ):
        mock_ids.return_value = [0]
        mock_eq_id.return_value = "000000000000000"
        with self.assertRaises(SystemExit):
            wcac.resolve_modem_index("865031064538696")

    @patch("time.sleep", return_value=None)
    @patch("wwan_connection_at_command.get_equipment_id")
    @patch("wwan_connection_at_command.mmcli_modem_ids")
    def test_resolve_modem_index_polling_retries_then_finds(
        self, mock_ids, mock_eq_id, mock_sleep
    ):
        # First poll: modem hasn't re-enumerated yet. Second poll: found.
        mock_ids.side_effect = [[], [3]]
        mock_eq_id.return_value = "865031064538696"
        result = wcac.resolve_modem_index_polling(
            "865031064538696", timeout=10, interval=1
        )
        self.assertEqual(result, 3)
        mock_sleep.assert_called_once_with(1)

    @patch("time.sleep", return_value=None)
    @patch(
        "wwan_connection_at_command.time.time",
        side_effect=itertools.count(1000, 50),
    )
    @patch("wwan_connection_at_command.mmcli_modem_ids", return_value=[])
    def test_resolve_modem_index_polling_times_out(
        self, mock_ids, mock_time, mock_sleep
    ):
        result = wcac.resolve_modem_index_polling(
            "865031064538696", timeout=10
        )
        self.assertIsNone(result)


class TestRunAtStep(unittest.TestCase):
    ENV = {"WWAN_APN": "internet", "WWAN_NET_IF": "enx0"}

    @patch("wwan_connection_at_command.mmcli_at")
    def test_plain_string_step_passes_on_any_response(self, mock_at):
        mock_at.return_value = (0, "response: ''\n", "")
        self.assertTrue(
            wcac.run_at_step(0, "Set auto-dial", "AT+DIALMODE=0", self.ENV)
        )

    @patch("wwan_connection_at_command.mmcli_at")
    def test_plain_string_step_fails_on_nonzero_rc(self, mock_at):
        mock_at.return_value = (1, "", "error: couldn't find modem")
        self.assertFalse(
            wcac.run_at_step(0, "Set auto-dial", "AT+DIALMODE=0", self.ENV)
        )

    @patch("wwan_connection_at_command.mmcli_at")
    def test_apn_placeholder_is_substituted(self, mock_at):
        mock_at.return_value = (0, "response: ''\n", "")
        wcac.run_at_step(0, "Set APN", 'AT+CGDCONT=1,"IP","{APN}"', self.ENV)
        sent_cmd = mock_at.call_args[0][1]
        self.assertEqual(sent_cmd, 'AT+CGDCONT=1,"IP","internet"')

    @patch("wwan_connection_at_command.mmcli_at")
    def test_expect_substring_pass_and_fail(self, mock_at):
        spec = {"cmd": "AT+CPIN?", "expect": "READY"}
        mock_at.return_value = (0, "response: '+CPIN: READY'\n", "")
        self.assertTrue(wcac.run_at_step(0, "SIM status", spec, self.ENV))

        mock_at.return_value = (0, "response: '+CPIN: SIM PIN'\n", "")
        self.assertFalse(wcac.run_at_step(0, "SIM status", spec, self.ENV))

    @patch("wwan_connection_at_command.mmcli_at")
    def test_expect_nonempty_pass_and_fail(self, mock_at):
        spec = {"cmd": "AT+CGPADDR=1", "expect_nonempty": True}
        mock_at.return_value = (0, "response: '10.0.0.5'\n", "")
        self.assertTrue(wcac.run_at_step(0, "Verify IP", spec, self.ENV))

        mock_at.return_value = (0, "response: ''\n", "")
        self.assertFalse(wcac.run_at_step(0, "Verify IP", spec, self.ENV))

    @patch("wwan_connection_at_command.mmcli_at")
    def test_expect_min_pass_and_fail(self, mock_at):
        spec = {"cmd": "AT+CSQ", "expect_min": 10}
        mock_at.return_value = (0, "response: '+CSQ: 15,0'\n", "")
        self.assertTrue(wcac.run_at_step(0, "Signal quality", spec, self.ENV))

        mock_at.return_value = (0, "response: '+CSQ: 3,0'\n", "")
        self.assertFalse(wcac.run_at_step(0, "Signal quality", spec, self.ENV))

    @patch("time.sleep", return_value=None)
    @patch("wwan_connection_at_command.mmcli_at")
    def test_poll_retries_until_pass(self, mock_at, mock_sleep):
        spec = {"cmd": "AT+CGATT?", "expect": "CGATT: 1", "poll": True}
        mock_at.side_effect = [
            (0, "response: '+CGATT: 0'\n", ""),
            (0, "response: '+CGATT: 1'\n", ""),
        ]
        self.assertTrue(
            wcac.run_at_step(0, "Verify GPRS attachment", spec, self.ENV)
        )
        self.assertEqual(mock_at.call_count, 2)
        mock_sleep.assert_called_once()

    @patch("time.sleep", return_value=None)
    @patch(
        "wwan_connection_at_command.time.time",
        side_effect=itertools.count(1000, 50),
    )
    @patch("wwan_connection_at_command.mmcli_at")
    def test_poll_gives_up_after_deadline(
        self, mock_at, mock_time, mock_sleep
    ):
        spec = {"cmd": "AT+CGATT?", "expect": "CGATT: 1", "poll": True}
        mock_at.return_value = (0, "response: '+CGATT: 0'\n", "")
        self.assertFalse(
            wcac.run_at_step(0, "Verify GPRS attachment", spec, self.ENV)
        )


class TestDetectModule(unittest.TestCase):
    @patch("wwan_connection_at_command.mmcli_list")
    def test_matches_first_known_module(self, mock_list):
        mock_list.return_value = (
            0,
            "/org/.../Modem/0 [SIMCOM] SIM7672G-LNGV\n",
        )
        config = {"SIM7672G-LNGV": {"Set auto-dial": "AT+DIALMODE=0"}}
        name, steps = wcac.detect_module(config)
        self.assertEqual(name, "SIM7672G-LNGV")
        self.assertEqual(steps, config["SIM7672G-LNGV"])

    @patch("wwan_connection_at_command.mmcli_list")
    def test_exits_when_no_module_matches(self, mock_list):
        mock_list.return_value = (0, "/org/.../Modem/0 [OTHER] UNKNOWN\n")
        with self.assertRaises(SystemExit):
            wcac.detect_module({"SIM7672G-LNGV": {}})


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
                "sudo",
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


class TestResetRecoveryHelpers(unittest.TestCase):
    @patch("wwan_connection_at_command.mmcli_at")
    def test_send_reset_pass_and_fail(self, mock_at):
        mock_at.return_value = (0, "response: ''\n", "")
        self.assertTrue(wcac.send_reset(0))

        mock_at.return_value = (1, "", "error")
        self.assertFalse(wcac.send_reset(0))

    @patch("wwan_connection_at_command.mmcli_at")
    def test_verify_cops_pass_and_fail(self, mock_at):
        mock_at.return_value = (0, "response: '+COPS: 0,,,7'\n", "")
        self.assertTrue(wcac.verify_cops(0, timeout=30))

        mock_at.return_value = (1, "", "timed out")
        self.assertFalse(wcac.verify_cops(0, timeout=30))

    @patch("time.sleep", return_value=None)
    @patch("wwan_connection_at_command.mmcli_at")
    def test_radio_cycle_sends_cfun_off_then_on(self, mock_at, mock_sleep):
        wcac.radio_cycle(0, wait_seconds=45)
        sent_cmds = [call.args[1] for call in mock_at.call_args_list]
        self.assertEqual(sent_cmds, ["AT+CFUN=4", "AT+CFUN=1"])
        mock_sleep.assert_any_call(45)

    @patch("time.sleep", return_value=None)
    @patch("wwan_connection_at_command.get_field")
    def test_wait_for_registration_passes_immediately(
        self, mock_get_field, mock_sleep
    ):
        mock_get_field.side_effect = lambda mm_id, key: {
            "registration": "roaming",
            "operator id": "46697",
        }[key]
        ok, registration, operator_id = wcac.wait_for_registration(
            0, timeout=120, radio_cycle_wait=45
        )
        self.assertTrue(ok)
        self.assertEqual(registration, "roaming")
        self.assertEqual(operator_id, "46697")

    @patch("wwan_connection_at_command.radio_cycle")
    @patch("time.sleep", return_value=None)
    @patch(
        "wwan_connection_at_command.time.time",
        side_effect=itertools.count(1000, 200),
    )
    @patch("wwan_connection_at_command.get_field")
    def test_wait_for_registration_cycles_radio_once_then_passes(
        self, mock_get_field, mock_time, mock_sleep, mock_radio_cycle
    ):
        # denied first (triggers exactly one radio cycle), then roaming
        mock_get_field.side_effect = [
            "denied",
            None,
            "roaming",
            "46697",
        ]
        ok, registration, operator_id = wcac.wait_for_registration(
            0, timeout=120, radio_cycle_wait=45
        )
        self.assertTrue(ok)
        self.assertEqual(registration, "roaming")
        mock_radio_cycle.assert_called_once_with(0, 45)

    @patch("wwan_connection_at_command.radio_cycle")
    @patch("time.sleep", return_value=None)
    @patch(
        "wwan_connection_at_command.time.time",
        side_effect=itertools.count(1000, 200),
    )
    @patch("wwan_connection_at_command.get_field", return_value="denied")
    def test_wait_for_registration_fails_after_one_cycle(
        self, mock_get_field, mock_time, mock_sleep, mock_radio_cycle
    ):
        ok, registration, operator_id = wcac.wait_for_registration(
            0, timeout=120, radio_cycle_wait=45
        )
        self.assertFalse(ok)
        self.assertEqual(registration, "denied")
        mock_radio_cycle.assert_called_once_with(0, 45)


class TestResetAndRecover(unittest.TestCase):
    @patch("wwan_connection_at_command.wait_for_registration")
    @patch("wwan_connection_at_command.verify_cops", return_value=True)
    @patch("wwan_connection_at_command.resolve_modem_index_polling")
    @patch("wwan_connection_at_command.send_reset", return_value=True)
    @patch("wwan_connection_at_command.resolve_modem_index", return_value=0)
    def test_happy_path(
        self,
        mock_resolve,
        mock_send_reset,
        mock_poll,
        mock_verify_cops,
        mock_wait_registration,
    ):
        mock_poll.return_value = 1
        mock_wait_registration.return_value = (True, "roaming", "46697")
        self.assertTrue(wcac.reset_and_recover("865031064538696"))
        mock_send_reset.assert_called_once_with(0)
        mock_verify_cops.assert_called_once()
        mock_wait_registration.assert_called_once()

    @patch("wwan_connection_at_command.send_reset", return_value=False)
    @patch("wwan_connection_at_command.resolve_modem_index", return_value=0)
    def test_fails_fast_when_reset_command_rejected(
        self, mock_resolve, mock_send_reset
    ):
        self.assertFalse(wcac.reset_and_recover("865031064538696"))

    @patch("wwan_connection_at_command.resolve_modem_index_polling")
    @patch("wwan_connection_at_command.send_reset", return_value=True)
    @patch("wwan_connection_at_command.resolve_modem_index", return_value=0)
    def test_fails_when_modem_never_reenumerates(
        self, mock_resolve, mock_send_reset, mock_poll
    ):
        mock_poll.return_value = None
        self.assertFalse(wcac.reset_and_recover("865031064538696"))

    @patch("wwan_connection_at_command.verify_cops", return_value=False)
    @patch("wwan_connection_at_command.resolve_modem_index_polling")
    @patch("wwan_connection_at_command.send_reset", return_value=True)
    @patch("wwan_connection_at_command.resolve_modem_index", return_value=0)
    def test_fails_when_cops_never_responds(
        self, mock_resolve, mock_send_reset, mock_poll, mock_verify_cops
    ):
        mock_poll.return_value = 1
        self.assertFalse(wcac.reset_and_recover("865031064538696"))


class TestRunPing(unittest.TestCase):
    @patch("wwan_connection_at_command.run_cmd")
    def test_fails_fast_when_link_up_fails(self, mock_run_cmd):
        mock_run_cmd.return_value = (1, "", "no such device")
        self.assertFalse(wcac.run_ping("enx0", 0))

    @patch("wwan_connection_at_command.deprioritize_default_route")
    @patch("wwan_connection_at_command.run_cmd")
    def test_passes_when_ip_and_ping_succeed(
        self, mock_run_cmd, mock_deprioritize
    ):
        def fake_run_cmd(args):
            if args[:3] == ["sudo", "ip", "link"]:
                return (0, "", "")
            if args[:2] == ["sudo", "nmcli"]:
                return (0, "", "")
            if args[:3] == ["ip", "addr", "show"]:
                return (0, "inet 192.168.0.100/24 brd 192.168.0.255\n", "")
            if args[0] == "ping":
                return (0, "4 packets transmitted, 4 received, 0% loss\n", "")
            return (0, "", "")

        mock_run_cmd.side_effect = fake_run_cmd
        self.assertTrue(wcac.run_ping("enx0", 0))
        mock_deprioritize.assert_called_once_with("enx0")

    @patch("wwan_connection_at_command.log_connection_diagnostics")
    @patch("time.sleep", return_value=None)
    @patch("wwan_connection_at_command.run_cmd")
    def test_fails_when_no_ip_assigned(
        self, mock_run_cmd, mock_sleep, mock_diag
    ):
        def fake_run_cmd(args):
            if args[:3] == ["sudo", "ip", "link"]:
                return (0, "", "")
            if args[:2] == ["sudo", "nmcli"]:
                return (0, "", "")
            if args[:3] == ["ip", "addr", "show"]:
                return (0, "no inet here\n", "")
            return (0, "", "")

        mock_run_cmd.side_effect = fake_run_cmd
        with patch("os.environ.get", return_value="0"):
            self.assertFalse(wcac.run_ping("enx0", 0))
        mock_diag.assert_called_once_with(0, "enx0")


if __name__ == "__main__":
    unittest.main()
