import unittest
from unittest.mock import patch, mock_open
import cpu_idle as cpu


class TestCpuIdle(unittest.TestCase):
    @patch("os.path.exists")
    def test_read_attr(self, mock_exists):
        mock_exists.return_value = True
        with patch("builtins.open", mock_open(read_data="test")):
            self.assertEqual(cpu.read_attr("test_path"), "test")

    @patch("os.path.exists")
    def test_read_attr_no_file(self, mock_exists):
        mock_exists.return_value = False
        self.assertEqual(cpu.read_attr("test_path"), "")

    @patch("cpu_idle.read_attr")
    def test_read_attr_num(self, mock_read_attr):
        mock_read_attr.return_value = "10"
        self.assertEqual(cpu.read_attr_num("test_path"), 10)

    @patch("cpu_idle.read_attr")
    def test_read_attr_num_no_file(self, mock_read_attr):
        mock_read_attr.return_value = ""
        self.assertEqual(cpu.read_attr_num("test_path"), -1)

    @patch("cpu_idle.read_attr")
    def test_read_attr_num_str(self, mock_read_attr):
        mock_read_attr.return_value = "test"
        with self.assertRaises(ValueError):
            cpu.read_attr_num("test_path")

    @patch("cpu_idle.read_attr")
    def test_read_idle_attr(self, mock_read_attr):
        mock_read_attr.return_value = "test"
        self.assertEqual(cpu.read_idle_attr(0, 0, "name"), "test")
        mock_read_attr.assert_called_once_with("cpu0/cpuidle/state0/name")

    @patch("cpu_idle.read_attr_num")
    def test_read_idle_attr_num(self, mock_read_attr_num):
        mock_read_attr_num.return_value = 10
        self.assertEqual(cpu.read_idle_attr_num(0, 0, "usage"), 10)
        mock_read_attr_num.assert_called_once_with("cpu0/cpuidle/state0/usage")

    @patch("builtins.print")
    def test_error_handler_with_name(self, mock_print):
        cpu.error_handler("name", "path/to/node", "expect", "reality")
        mock_print.assert_called_once_with(
            "Failed: the expected name value of node 'path/to/node' should be "
            "'expect' but got 'reality'"
        )

    @patch("builtins.print")
    def test_error_handler_with_disable(self, mock_print):
        cpu.error_handler("disable", "path/to/node", "expect", "reality")
        mock_print.assert_called_once_with(
            "Failed: the expected disable value of node 'path/to/node' "
            "should be 'expect' but got 'reality'"
        )

    @patch("builtins.print")
    def test_error_handler_with_usage(self, mock_print):
        cpu.error_handler("usage", "path/to/node", "expect", "reality")
        mock_print.assert_called_once_with(
            "Failed: the expected usage value of node 'path/to/node' "
            "should grater than 0"
        )

    def test_output_checker(self):
        result = cpu.output_checker(0, 0, ("test", "test"), (0, 0), 1)
        self.assertEqual(result, None)

    @patch("cpu_idle.error_handler")
    def test_output_checker_name_mismatch(self, mock_error_handler):
        with self.assertRaises(SystemExit):
            cpu.output_checker(0, 0, ("test", "expected"), (0, 0), 1)

    @patch("cpu_idle.error_handler")
    def test_output_checker_disable_mismatch(self, mock_error_handler):
        with self.assertRaises(SystemExit):
            cpu.output_checker(0, 0, ("test", "test"), (0, 1), 1)

    @patch("cpu_idle.error_handler")
    def test_output_checker_usage_zero(self, mock_error_handler):
        with self.assertRaises(SystemExit):
            cpu.output_checker(0, 0, ("test", "test"), (0, 0), 0)

    @patch("cpu_idle.read_idle_attr")
    @patch("cpu_idle.read_idle_attr_num")
    @patch("cpu_idle.output_checker")
    def test_mt8395_cases(
        self, mock_output_checker, mock_read_attr_num, mock_read_attr
    ):
        mock_read_attr.side_effect = ["WFI", "0"]
        mock_read_attr_num.return_value = 1
        cpu.test_wfi()
        mock_output_checker.assert_called_with(
            0, 0, name=("WFI", "WFI"), disable=("0", "0"), usage=1
        )

        self.assertEqual(cpu.test_mcdi_cpu("mt8395"), None)

        self.assertEqual(cpu.test_mcdi_cluster("mt8395"), None)

        self.assertEqual(cpu.test_dpidle("mt8395"), None)

        mock_read_attr.side_effect = ["clusteroff_l", "0"]
        mock_read_attr_num.return_value = 1
        cpu.test_clusteroff_l("mt8395")
        mock_output_checker.assert_called_with(
            0,
            2,
            name=("clusteroff_l", "clusteroff_l"),
            disable=("0", "0"),
            usage=1,
        )

        mock_read_attr.side_effect = ["clusteroff_b", "0"]
        mock_read_attr_num.return_value = 1
        cpu.test_clusteroff_b("mt8395")
        mock_output_checker.assert_called_with(
            4,
            2,
            name=("clusteroff_b", "clusteroff_b"),
            disable=("0", "0"),
            usage=1,
        )

        mock_read_attr.side_effect = ["cpuoff_l", "0"]
        mock_read_attr_num.return_value = 1
        cpu.test_cpuoff_l("mt8395")
        mock_output_checker.assert_called_with(
            0, 1, name=("cpuoff_l", "cpuoff_l"), disable=("0", "0"), usage=1
        )

        mock_read_attr.side_effect = ["cpuoff_b", "0"]
        mock_read_attr_num.return_value = 1
        cpu.test_cpuoff_b("mt8395")
        mock_output_checker.assert_called_with(
            4, 1, name=("cpuoff_b", "cpuoff_b"), disable=("0", "0"), usage=1
        )

    @patch("cpu_idle.read_idle_attr")
    @patch("cpu_idle.read_idle_attr_num")
    @patch("cpu_idle.output_checker")
    def test_mt8390_cases(
        self, mock_output_checker, mock_read_attr_num, mock_read_attr
    ):
        mock_read_attr.side_effect = ["WFI", "0"]
        mock_read_attr_num.return_value = 1
        cpu.test_wfi()
        mock_output_checker.assert_called_with(
            0, 0, name=("WFI", "WFI"), disable=("0", "0"), usage=1
        )

        self.assertEqual(cpu.test_mcdi_cpu("mt8390"), None)

        self.assertEqual(cpu.test_mcdi_cluster("mt8390"), None)

        self.assertEqual(cpu.test_dpidle("mt8390"), None)

        mock_read_attr.side_effect = ["clusteroff-l", "0"]
        mock_read_attr_num.return_value = 1
        cpu.test_clusteroff_l("mt8390")
        mock_output_checker.assert_called_with(
            0,
            2,
            name=("clusteroff-l", "clusteroff-l"),
            disable=("0", "0"),
            usage=1,
        )

        mock_read_attr.side_effect = ["clusteroff-b", "0"]
        mock_read_attr_num.return_value = 1
        cpu.test_clusteroff_b("mt8390")
        mock_output_checker.assert_called_with(
            6,
            2,
            name=("clusteroff-b", "clusteroff-b"),
            disable=("0", "0"),
            usage=1,
        )

        mock_read_attr.side_effect = ["cpuoff-l", "0"]
        mock_read_attr_num.return_value = 1
        cpu.test_cpuoff_l("mt8390")
        mock_output_checker.assert_called_with(
            0, 1, name=("cpuoff-l", "cpuoff-l"), disable=("0", "0"), usage=1
        )

        mock_read_attr.side_effect = ["cpuoff-b", "0"]
        mock_read_attr_num.return_value = 1
        cpu.test_cpuoff_b("mt8390")
        mock_output_checker.assert_called_with(
            6, 1, name=("cpuoff-b", "cpuoff-b"), disable=("0", "0"), usage=1
        )

    @patch("cpu_idle.read_idle_attr")
    @patch("cpu_idle.read_idle_attr_num")
    @patch("cpu_idle.output_checker")
    def test_mt8365_cases(
        self, mock_output_checker, mock_read_attr_num, mock_read_attr
    ):
        mock_read_attr.side_effect = ["WFI", "0"]
        mock_read_attr_num.return_value = 1
        cpu.test_wfi()
        mock_output_checker.assert_called_with(
            0, 0, name=("WFI", "WFI"), disable=("0", "0"), usage=1
        )

        mock_read_attr.side_effect = ["mcdi-cpu", "0"]
        mock_read_attr_num.return_value = 1
        cpu.test_mcdi_cpu("mt8365")
        mock_output_checker.assert_called_with(
            0, 1, name=("mcdi-cpu", "mcdi-cpu"), disable=("0", "0"), usage=1
        )

        mock_read_attr.side_effect = ["mcdi-cluster", "0"]
        mock_read_attr_num.return_value = 1
        cpu.test_mcdi_cluster("mt8365")
        mock_output_checker.assert_called_with(
            0,
            2,
            name=("mcdi-cluster", "mcdi-cluster"),
            disable=("0", "0"),
            usage=1,
        )

        mock_read_attr.side_effect = ["dpidle", "0"]
        mock_read_attr_num.return_value = 1
        cpu.test_dpidle("mt8365")
        mock_output_checker.assert_called_with(
            0, 3, name=("dpidle", "dpidle"), disable=("0", "0"), usage=1
        )

        self.assertEqual(cpu.test_clusteroff_l("mt8365"), None)

        self.assertEqual(cpu.test_clusteroff_b("mt8365"), None)

        self.assertEqual(cpu.test_cpuoff_l("mt8365"), None)

        self.assertEqual(cpu.test_cpuoff_b("mt8365"), None)

    def test_main_cases(self):
        cases = {
            "mcdi-cpu": "test_mcdi_cpu",
            "mcdi-cluster": "test_mcdi_cluster",
            "dpidle": "test_dpidle",
            "clusteroff-l": "test_clusteroff_l",
            "clusteroff-b": "test_clusteroff_b",
            "cpuoff-l": "test_cpuoff_l",
            "cpuoff-b": "test_cpuoff_b",
        }

        args = ["soc", "mt8395", "--case", "wfi"]
        with patch("cpu_idle.test_wfi") as mock_test:
            with patch("sys.argv", args):
                cpu.main()
            mock_test.assert_called_once_with()

        for case, func in cases.items():
            args = ["soc", "mt8395", "--case", case]
            with patch("cpu_idle." + func) as mock_test:
                with patch("sys.argv", args):
                    cpu.main()
                mock_test.assert_called_once_with("mt8395")

    @patch("cpu_idle.test_wfi", return_value=None)
    def test_main_wrong_soc(self, mock_test_wfi):
        with self.assertRaises(SystemExit):
            with patch("sys.argv", ["soc", "bad_soc", "--case", "wfi"]):
                cpu.main()

    def test_main_wrong_case(self):
        with self.assertRaises(SystemExit):
            with patch("sys.argv", ["soc", "mt8395", "--case", "bad_case"]):
                cpu.main()
