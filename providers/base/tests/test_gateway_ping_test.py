import unittest
import textwrap
import subprocess
from unittest.mock import patch, MagicMock, mock_open
from gateway_ping_test import (
    main,
    parse_args,
    ping,
    Route,
    is_reachable,
    get_default_gateway_reachable_on,
    get_any_host_reachable_on,
    get_host_to_ping,
    get_default_gateways,
    is_cable_interface,
)


class TestRoute(unittest.TestCase):
    @patch("subprocess.check_output")
    def test__get_default_gateway_from_ip_nominal(self, mock_check_output):
        ok_output = (
            "default via 192.168.1.1 proto dhcp src 192.168.1.119 metric 100"
        )
        mock_check_output.return_value = ok_output
        expected_gateway = "192.168.1.1"
        self_mock = MagicMock()
        self_mock.interface = "eth0"
        self.assertEqual(
            Route._get_default_gateway_from_ip(self_mock), expected_gateway
        )

    @patch("subprocess.check_output")
    def test__get_default_gateway_from_ip_noroute(self, mock_check_output):
        mock_check_output.return_value = ""
        self_mock = MagicMock()
        self_mock.interface = "eth0"
        self.assertIsNone(Route._get_default_gateway_from_ip(self_mock))

    @patch("subprocess.check_output")
    def test__get_default_gateway_from_ip_invalid_route(
        self, mock_check_output
    ):
        invalid_output = "invalid routing information"
        mock_check_output.return_value = invalid_output
        self_mock = MagicMock()
        self_mock.interface = "eth0"
        self.assertIsNone(Route._get_default_gateway_from_ip(self_mock))

    @patch("subprocess.check_output")
    def test__get_default_gateway_from_ip_crash(self, mock_check_output):
        mock_check_output.side_effect = subprocess.CalledProcessError(1, "")
        self_mock = MagicMock()
        self_mock.interface = "eth0"
        self.assertIsNone(Route._get_default_gateway_from_ip(self_mock))

    def test__get_default_gateway_from_proc_nominal(self):
        self_mock = MagicMock()

        def _num_to_dotted_quad(x):
            return Route._num_to_dotted_quad(None, x)

        self_mock._num_to_dotted_quad = _num_to_dotted_quad
        self_mock.interface = "eth0"
        expected_gateway = "192.168.1.1"
        output_sample = textwrap.dedent(
            """
            Iface Destination Gateway Flags RefCnt Use Metric Mask MTU Window IRTT
            eth0 00000000 0101A8C0 0003 0 0 0 00000000 0 0 0
            """
        )
        with patch(
            "builtins.open", new_callable=mock_open, read_data=output_sample
        ):
            self.assertEqual(
                Route._get_default_gateway_from_proc(self_mock),
                expected_gateway,
            )

    def test__get_default_gateway_from_proc_file_error(self):
        self_mock = MagicMock()

        def _num_to_dotted_quad(x):
            return Route._num_to_dotted_quad(None, x)

        self_mock._num_to_dotted_quad = _num_to_dotted_quad
        self_mock.interface = "eth0"
        with patch(
            "builtins.open", side_effect=FileNotFoundError("File not found")
        ):
            self.assertIsNone(
                Route._get_default_gateway_from_proc(self_mock),
            )

    @patch("gateway_ping_test.get_default_gateways")
    def test__get_default_gateway_from_bin_route_nominal(self, mock_get_d_gws):
        mock_get_d_gws.return_value = {
            "enp5s0": "192.168.1.1",
            "wlan0": "192.168.1.100",
        }
        self_mock = MagicMock()
        self_mock.interface = "wlan0"
        gateway = Route._get_default_gateway_from_bin_route(self_mock)
        self.assertEqual(gateway, "192.168.1.100")

    @patch("gateway_ping_test.get_default_gateways")
    def test__get_default_gateway_from_bin_route_if_not_found(
        self, mock_get_d_gws
    ):
        mock_get_d_gws.return_value = {
            "enp5s0": "192.168.1.1",
            "wlan0": "192.168.1.100",
        }
        self_mock = MagicMock()
        self_mock.interface = "enp1s0"
        gateway = Route._get_default_gateway_from_bin_route(self_mock)
        self.assertIsNone(gateway)

    @patch("gateway_ping_test.get_default_gateways")
    def test__get_default_gateway_from_bin_route_empty(self, mock_get_d_gws):
        mock_get_d_gws.return_value = {}
        self_mock = MagicMock()
        self_mock.interface = "enp1s0"
        gateway = Route._get_default_gateway_from_bin_route(self_mock)
        self.assertIsNone(gateway)

    def test_get_broadcast(self):
        self_mock = MagicMock()
        self_mock.interface = "enp5s0"
        self_mock._get_ip_addr_info.return_value = textwrap.dedent(
            """
            1: lo    inet 127.0.0.1/8 scope host lo\\ valid_lft forever ...
            3: wlan0    inet 192.168.1.115/24 brd 192.168.1.255 scope ...
            4: enp5s0    inet 192.168.1.119/24 brd 192.168.1.255 scope ...
            """
        )
        self.assertEqual(Route.get_broadcast(self_mock), "192.168.1.255")

    def test_get_broadcast_not_found(self):
        self_mock = MagicMock()
        self_mock.interface = "eth0"
        self_mock._get_ip_addr_info.return_value = textwrap.dedent(
            """
            1: lo    inet 127.0.0.1/8 scope host lo\\ valid_lft forever ...
            3: wlan0    inet 192.168.1.115/24 brd 192.168.1.255 scope ...
            4: enp5s0    inet 192.168.1.119/24 brd 192.168.1.255 scope ...
            """
        )
        with self.assertRaises(ValueError):
            Route.get_broadcast(self_mock)

    @patch("subprocess.check_output")
    def test__get_default_gateway_from_networkctl_ok(self, mock_check_output):
        mock_check_output.return_value = textwrap.dedent(
            """
            systemd-networkd is not running, output might be incomplete.
            Failed to query link bit rates: Could not activate remote peer:
                activation request failed: unknown unit.
            Failed to query link DHCP leases: Could not activate remote peer:
                activation request failed: unknown unit.

            ● 4: enp5s0
                               Link File: /usr/lib/systemd/network/99-default.link
                                 Address: 192.168.1.119
                                          fe80::eb41:84fa:6da5:c815
                                 Gateway: 192.168.1.1

            feb 00 00:00:00 ... systemd-resolved[1430]: enp5s0: Systemd log line
            """
        )
        def_gateway = Route("enp5s0")._get_default_gateway_from_networkctl()
        self.assertEqual(def_gateway, "192.168.1.1")

    @patch("subprocess.check_output")
    def test__get_default_gateway_from_networkctl_no_gateway(
        self, mock_check_output
    ):
        mock_check_output.return_value = textwrap.dedent(
            """
            systemd-networkd is not running, output might be incomplete.
            Failed to query link bit rates: Could not activate remote peer:
                activation request failed: unknown unit.
            Failed to query link DHCP leases: Could not activate remote peer:
                activation request failed: unknown unit.

            ● 4: enp5s0
                               Link File: /usr/lib/systemd/network/99-default.link
                                 Address: 192.168.1.119
                                          fe80::eb41:84fa:6da5:c815

            feb 00 00:00:00 ... systemd-resolved[1430]: enp5s0: Systemd log line
            """
        )
        def_gateway = Route("enp5s0")._get_default_gateway_from_networkctl()
        self.assertIsNone(def_gateway)

    @patch("subprocess.check_output")
    def test__get_default_gateway_from_networkctl_failure(
        self, mock_check_output
    ):
        mock_check_output.side_effect = subprocess.CalledProcessError(1, "")
        def_gateway = Route("enp5s0")._get_default_gateway_from_networkctl()
        self.assertIsNone(def_gateway)

    @patch("subprocess.check_output")
    def test__get_default_gateway_from_bin_route_exception(
        self, mock_check_output
    ):
        mock_check_output.side_effect = subprocess.CalledProcessError(1, "")
        self_mock = MagicMock()
        self_mock.interface = "enp1s0"
        gateway = Route._get_default_gateway_from_bin_route(self_mock)
        self.assertIsNone(gateway)

    def test_get_default_gateways(self):
        self_mock = MagicMock()
        self_mock._get_default_gateway_from_ip.return_value = "192.168.1.1"
        self_mock._get_default_gateway_from_proc.return_value = "192.168.1.1"
        self_mock._get_default_gateway_from_bin_route.return_value = None
        self_mock._get_default_gateway_from_networkctl.return_value = None

        self.assertEqual(
            Route.get_default_gateways(self_mock), {"192.168.1.1"}
        )

    @patch("logging.warning")
    def test_get_default_gateways_warns(self, mock_warn):
        self_mock = MagicMock()
        self_mock._get_default_gateway_from_ip.return_value = None
        self_mock._get_default_gateway_from_proc.return_value = None
        self_mock._get_default_gateway_from_bin_route.return_value = (
            "192.168.1.1"
        )
        self_mock._get_default_gateway_from_networkctl.return_value = (
            "192.168.1.2"
        )

        self.assertEqual(
            Route.get_default_gateways(self_mock),
            {"192.168.1.1", "192.168.1.2"},
        )
        self.assertTrue(mock_warn.called)

    @patch(
        "subprocess.check_output",
        return_value="192.168.1.203 dev enp5s0 src 192.168.1.119 uid 1000",
    )
    def test_get_interface_from_ip_ok(self, mock_check_output):
        self.assertEqual(
            Route.get_interface_from_ip("192.168.1.203"), "enp5s0"
        )

    @patch("subprocess.check_output", return_value="")
    def test_get_interface_from_ip_no_route(self, mock_check_output):
        with self.assertRaises(ValueError):
            Route.get_interface_from_ip("192.168.1.203")

    @patch("subprocess.check_output")
    def test_get_any_interface_from_ip_ok(self, mock_check_output):
        mock_check_output.return_value = textwrap.dedent(
            """
            default via 192.168.1.1 dev enp5s0 proto dhcp src 192.168.1.119 metric 100
            default via 192.168.1.1 dev wlan0 proto dhcp src 192.168.1.115 metric 600
            """
        )
        self.assertEqual(Route.get_any_interface(), "enp5s0")

    @patch("subprocess.check_output", return_value="")
    def test_get_any_interface_from_ip_not_found(self, mock_check_output):
        with self.assertRaises(ValueError):
            Route.get_any_interface()

    @patch("gateway_ping_test.Route.get_interface_from_ip")
    def test_from_ip(self, mock_get_interface_from_ip):
        mock_get_interface_from_ip.return_value = "enp6s0"
        self.assertEqual(Route.from_ip("192.168.3.3").interface, "enp6s0")
        self.assertTrue(mock_get_interface_from_ip.called)

    @patch("gateway_ping_test.Route.get_any_interface")
    def test_from_ip_none(self, mock_get_interface_from_ip):
        mock_get_interface_from_ip.return_value = "enp6s0"
        self.assertEqual(Route.from_ip(None).interface, "enp6s0")
        self.assertTrue(mock_get_interface_from_ip.called)

    @patch("subprocess.check_output", return_value="")
    def test_get_ip_addr_info(self, mock_check_output):
        self_mock = MagicMock()
        self.assertEqual(Route._get_ip_addr_info(self_mock), "")
        mock_check_output.assert_called_once_with(
            ["ip", "-o", "addr", "show"], universal_newlines=True
        )


class TestUtilityFunctions(unittest.TestCase):
    @patch("gateway_ping_test.ping")
    def test_is_reachable(self, mock_ping):
        mock_ping.return_value = {"transmitted": 3, "received": 2}
        self.assertTrue(is_reachable("10.0.0.1", "eth0"))

    @patch("gateway_ping_test.ping")
    def test_is_reachable_false(self, mock_ping):
        mock_ping.return_value = {"transmitted": 0, "received": 0}
        self.assertFalse(is_reachable("10.0.0.1", "eth0"))


class TestReachabilityFunctions(unittest.TestCase):
    @patch("gateway_ping_test.Route")
    @patch("gateway_ping_test.is_reachable", return_value=True)
    def test_get_default_gateway_reachable_on_gateway_reachable(
        self, mock_is_reachable, mock_route
    ):
        mock_route.return_value.get_default_gateways.return_value = [
            "192.168.1.1"
        ]
        interface = "eth0"
        result = get_default_gateway_reachable_on(interface)
        self.assertEqual(result, "192.168.1.1")
        mock_route.assert_called_once_with(interface=interface)
        mock_is_reachable.assert_called_once_with("192.168.1.1", interface)

    def test_get_default_gateway_reachable_on_interface_none(self):
        interface = None
        with self.assertRaises(ValueError) as context:
            get_default_gateway_reachable_on(interface)
        self.assertTrue(
            "Unable to ping on interface None" in str(context.exception)
        )

    @patch("gateway_ping_test.Route")
    @patch("gateway_ping_test.is_reachable", return_value=False)
    def test_get_default_gateway_reachable_on_no_reachable_gateway(
        self, mock_is_reachable, mock_route
    ):
        mock_route.return_value.get_default_gateways.return_value = [
            "192.168.1.1",
            "192.168.1.2",
        ]
        interface = "eth0"
        with self.assertRaises(ValueError) as context:
            get_default_gateway_reachable_on(interface)
        self.assertTrue(
            "Unable to reach any estimated gateway of interface eth0"
            in str(context.exception)
        )
        mock_route.assert_called_once_with(interface=interface)
        self.assertEqual(
            mock_is_reachable.call_count, len(["192.168.1.1", "192.168.1.2"])
        )

    @patch("gateway_ping_test.subprocess.check_output")
    @patch("gateway_ping_test.ping")
    @patch("gateway_ping_test.Route")
    @patch("gateway_ping_test.is_reachable", return_value=True)
    def test_get_any_host_reachable_on_host_reachable(
        self, mock_is_reachable, mock_route, mock_ping, mock_subprocess_output
    ):
        mock_route.return_value.get_broadcast.return_value = "192.168.1.255"
        mock_subprocess_output.return_value = (
            "? (192.168.1.100) at ab:cd:ef:12:34:56 [ether] on eth0\n"
        )
        interface = "eth0"
        expected_host = "192.168.1.100"
        result = get_any_host_reachable_on(interface)
        self.assertEqual(result, expected_host)

    def test_get_any_host_reachable_on_interface_none(self):
        interface = None
        with self.assertRaises(ValueError) as context:
            get_any_host_reachable_on(interface)
        self.assertTrue(
            "Unable to ping on interface None" in str(context.exception)
        )

    @patch("gateway_ping_test.subprocess.check_output")
    @patch("gateway_ping_test.ping")
    @patch("gateway_ping_test.Route")
    @patch("gateway_ping_test.is_reachable", return_value=False)
    @patch("gateway_ping_test.time.sleep")  # Mock sleep to speed up the test
    def test_get_any_host_reachable_on_no_reachable_host(
        self,
        mock_sleep,
        mock_is_reachable,
        mock_route,
        mock_ping,
        mock_subprocess_output,
    ):
        mock_route.return_value.get_broadcast.return_value = "192.168.1.255"
        mock_subprocess_output.return_value = (
            "? (192.168.1.100) at ab:cd:ef:12:34:56 [ether] on eth0\n"
        )
        interface = "eth0"
        with self.assertRaises(ValueError) as context:
            get_any_host_reachable_on(interface)
        self.assertTrue(
            "Unable to reach any host on interface eth0"
            in str(context.exception)
        )

    @patch("gateway_ping_test.is_reachable", return_value=True)
    def test_get_host_to_ping_priority_target(self, _):
        self.assertEqual(get_host_to_ping("eth0", "10.0.0.1"), "10.0.0.1")

    @patch("gateway_ping_test.is_reachable", return_value=False)
    @patch(
        "gateway_ping_test.get_default_gateway_reachable_on",
        return_value="10.0.0.20",
    )
    @patch("gateway_ping_test.Route")
    def test_get_host_to_ping_priority_default_gateway(
        self, mock_route, mock_default_gateway_rechable_on, _
    ):
        # default gateway is on the same interface as the route target
        # 10.0.0.1 but 10.0.0.1 is not reachable
        self.assertEqual(get_host_to_ping(None, "10.0.0.1"), "10.0.0.20")

    @patch("gateway_ping_test.is_reachable", return_value=False)
    @patch(
        "gateway_ping_test.get_any_host_reachable_on", return_value="10.0.1.2"
    )
    @patch(
        "gateway_ping_test.get_default_gateway_reachable_on",
        side_effect=ValueError,
    )
    @patch("gateway_ping_test.Route")
    def test_get_host_to_ping_priority_any_route(
        self,
        mock_route,
        mock_default_gateway_rechable_on,
        mock_get_any_host_reachable_on,
        _,
    ):
        # default gateway is on the same interface as the route target
        # but both are unreachable, the test should try to get any reachable
        # tagets on the interface
        self.assertEqual(get_host_to_ping(None, "10.0.0.1"), "10.0.1.2")

    @patch("gateway_ping_test.is_reachable", return_value=False)
    @patch(
        "gateway_ping_test.get_any_host_reachable_on", side_effect=ValueError
    )
    @patch(
        "gateway_ping_test.get_default_gateway_reachable_on",
        side_effect=ValueError,
    )
    @patch("gateway_ping_test.Route")
    def test_get_host_to_ping_priority_failure(
        self,
        mock_route,
        mock_default_gateway_rechable_on,
        mock_get_any_host_reachable_on,
        _,
    ):
        # we are unable to reach any target on the interface that should
        # reach 10.0.0.1
        self.assertIsNone(get_host_to_ping(None, "10.0.0.1"))


class TestPingFunction(unittest.TestCase):
    @patch("subprocess.check_output")
    def test_ping_ok(self, mock_check_output):
        mock_check_output.return_value = (
            "4 packets transmitted, 4 received, 0% packet loss"
        )
        result = ping("8.8.8.8", "eth0")
        self.assertEqual(result["transmitted"], 4)
        self.assertEqual(result["received"], 4)
        self.assertEqual(result["pct_loss"], 0)

    @patch("subprocess.check_output")
    def test_ping_malformed_output(self, mock_check_output):
        mock_check_output.return_value = "Malformed output"
        result = ping("8.8.8.8", "eth0")
        self.assertIn("Failed to parse", result["cause"])

    @patch("subprocess.check_output")
    def test_ping_no_ping(self, mock_check_output):
        mock_check_output.side_effect = FileNotFoundError("ping not found")
        result = ping("8.8.8.8", "eth0")
        self.assertEqual(result["cause"], str(mock_check_output.side_effect))

    @patch("subprocess.check_output")
    def test_ping_failure(self, mock_check_output):
        mock_check_output.side_effect = MagicMock(
            side_effect=subprocess.CalledProcessError(
                1, "ping", "ping: unknown host"
            )
        )
        result = ping("invalid.host", None)
        # Since the function does not return a detailed error for general
        # failures, we just check for non-success
        self.assertNotEqual(
            result["received"], 4
        )  # Assuming failure means not all packets are received

    @patch("subprocess.check_output")
    def test_ping_failure_broadcast(self, mock_check_output):
        # Simulate broadcast ping which always fails
        mock_check_output.side_effect = MagicMock(
            side_effect=subprocess.CalledProcessError(
                1, "ping", stderr="SO_BINDTODEVICE: Operation not permitted"
            )
        )
        result = ping("255.255.255.255", None, broadcast=True)
        self.assertIsNone(result)


class TestMainFunction(unittest.TestCase):
    @patch("gateway_ping_test.get_host_to_ping")
    @patch("gateway_ping_test.ping")
    def test_no_internet_connection_no_cause(
        self, mock_ping, mock_get_host_to_ping
    ):
        mock_get_host_to_ping.return_value = "1.1.1.1"
        mock_ping.return_value = {
            "received": 0,
            "transmitted": 0,
        }
        result = main(["1.1.1.1"])
        self.assertEqual(result, 1)

    @patch("gateway_ping_test.get_host_to_ping")
    @patch("gateway_ping_test.ping")
    def test_no_internet_connection_auto_cause(
        self, mock_ping, mock_get_host_to_ping
    ):
        mock_get_host_to_ping.return_value = None
        mock_ping.return_value = {"received": 0}
        result = main(["1.1.1.1"])
        self.assertEqual(result, 1)

    @patch("gateway_ping_test.get_host_to_ping")
    @patch("gateway_ping_test.ping")
    def test_no_internet_connection_cause(
        self, mock_ping, mock_get_host_to_ping
    ):
        mock_ping.return_value = {
            "received": 0,
            "transmitted": 0,
            "cause": "Test cause",
        }
        result = main(["1.1.1.1"])
        self.assertEqual(result, 1)

    @patch("gateway_ping_test.get_host_to_ping")
    @patch("gateway_ping_test.ping")
    def test_spotty_connection_with_cause(
        self, mock_ping, mock_get_host_to_ping
    ):
        mock_ping.return_value = {
            "received": 1,
            "transmitted": 2,
            "pct_loss": 50,
            "cause": "Test cause",
        }
        result = main(["1.1.1.1"])
        self.assertEqual(result, 1)

    @patch("gateway_ping_test.get_host_to_ping")
    @patch("gateway_ping_test.ping")
    def test_some_packet_loss(self, mock_ping, mock_get_host_to_ping):
        mock_ping.return_value = {
            "transmitted": 100,
            "received": 95,
            "pct_loss": 5,
        }
        result = main(["1.1.1.1"])
        self.assertEqual(result, 1)

    @patch("gateway_ping_test.get_host_to_ping")
    @patch("gateway_ping_test.ping")
    def test_full_connectivity(self, mock_ping, mock_get_host_to_ping):
        mock_ping.return_value = {
            "transmitted": 100,
            "received": 100,
            "pct_loss": 0,
        }
        result = main(["1.1.1.1"])
        self.assertEqual(result, 0)

    @patch("gateway_ping_test.is_reachable", return_value=True)
    @patch("gateway_ping_test.get_default_gateways")
    @patch("gateway_ping_test.ping")
    def test_main_any_cable(self, mock_ping, mock_get_default_gateways, _):
        mock_get_default_gateways.return_value = {
            "enp5s0": "192.168.1.1",
            "wlan0": "192.168.1.2",
        }
        mock_ping.return_value = {
            "transmitted": 100,
            "received": 100,
            "pct_loss": 0,
        }
        main(["--any-cable-interface"])
        mock_ping.assert_called_once_with("192.168.1.1", "enp5s0")

    @patch("gateway_ping_test.is_reachable", return_value=True)
    @patch("gateway_ping_test.get_default_gateways")
    @patch("gateway_ping_test.ping")
    def test_main_any_cable_no_iface(
        self, mock_ping, mock_get_default_gateways, _
    ):
        mock_get_default_gateways.return_value = {
            "wlan0": "192.168.1.2",
        }
        with self.assertRaises(SystemExit):
            main(["--any-cable-interface"])


class GetDefaultGatewaysTests(unittest.TestCase):
    @patch("subprocess.check_output")
    def test_get_default_gateways_nominal(self, mock_check_output):
        mock_check_output.return_value = textwrap.dedent(
            """
            Kernel IP routing table
            Destination Gateway       Genmask  Flags Metric Ref Use Iface
            0.0.0.0     192.168.1.1   0.0.0.0  UG    100    0   0   enp5s0
            0.0.0.0     192.168.1.100 0.0.0.0  UG    600    0   0   wlan0
            """
        )
        gateways = get_default_gateways()
        self.assertDictEqual(
            gateways, {"enp5s0": "192.168.1.1", "wlan0": "192.168.1.100"}
        )

    @patch("subprocess.check_output")
    def test_get_default_gateways_no_default(self, mock_check_output):
        mock_check_output.return_value = textwrap.dedent(
            """
            Kernel IP routing table
            Destination Gateway       Genmask  Flags Metric Ref Use Iface
            192.168.1.0 192.168.1.1   0.0.0.0  UG    100    0   0   enp5s0
            """
        )
        gateways = get_default_gateways()
        self.assertDictEqual(gateways, {})

    @patch("subprocess.check_output")
    def test_get_default_gateways_cant_run_route(self, mock_check_output):
        mock_check_output.side_effect = subprocess.CalledProcessError(1, "")
        gateways = get_default_gateways()
        self.assertDictEqual(gateways, {})


class IsCableInterfaceTests(unittest.TestCase):
    def test_is_cable_interface_nominal(self):
        self.assertTrue(is_cable_interface("eth0"))

    def test_is_cable_interface_nominal_2(self):
        self.assertTrue(is_cable_interface("enp5s0"))

    def test_is_cable_interface_nominal_3(self):
        self.assertTrue(is_cable_interface("enp0s25"))

    def test_is_cable_interface_nope(self):
        self.assertFalse(is_cable_interface("wlan0"))

    def test_is_cable_interface_nope_2(self):
        self.assertFalse(is_cable_interface("wlp3s0"))

    def test_is_cable_interface_nope_3(self):
        self.assertFalse(is_cable_interface("wwan0"))

    def test_is_cable_interface_nope_4(self):
        self.assertFalse(is_cable_interface("tun0"))

    def test_is_cable_interface_nope_5(self):
        self.assertFalse(is_cable_interface("lo"))

    def test_is_cable_interface_empty(self):
        self.assertFalse(is_cable_interface(""))

    def test_is_cable_interface_not_string(self):
        self.assertFalse(is_cable_interface(123))
