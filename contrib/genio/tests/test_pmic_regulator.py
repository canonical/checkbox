import unittest
from unittest.mock import patch, mock_open
import pmic_regulator


class TestRegulator(unittest.TestCase):

    @patch("os.path.exists")
    @patch("builtins.open", new_callable=mock_open, read_data="attr_1")
    def test_read_attr(self, mock_file, mock_exists):
        mock_exists.return_value = True
        result = pmic_regulator.read_attr("attribute")
        self.assertEqual(result, "attr_1")

    @patch("os.path.exists")
    @patch("builtins.open", new_callable=mock_open, read_data="")
    def test_read_attr_not_exists(self, mock_file, mock_exists):
        mock_exists.return_value = False
        result = pmic_regulator.read_attr("attribute")
        self.assertEqual(result, "")

    @patch("pmic_regulator.read_attr")
    def test_read_all_name(self, mock_read_attr):
        mock_read_attr.side_effect = ["node1", "node2", ""]
        result = pmic_regulator.read_all_name()
        self.assertEqual(result, {"node1", "node2"})

    @patch("pmic_regulator.read_all_name")
    def test_regulator(self, mock_read_all_name):
        mock_read_all_name.return_value = pmic_regulator.mt8365_MAIN_REGULATORS
        result = pmic_regulator.test_regulator("mt8365")
        self.assertEqual(result, None)

    @patch("pmic_regulator.read_all_name")
    def test_regulator_mt8390(self, mock_read_all_name):
        mock_read_all_name.return_value = pmic_regulator.MAIN_REGULATORS
        result = pmic_regulator.test_regulator("mt8390")
        self.assertEqual(result, None)

    @patch("pmic_regulator.read_all_name")
    def test_regulator_missing_node(self, mock_read_all_name):
        mock_read_all_name.return_value = ["wrong_node"]
        with self.assertRaises(SystemExit):
            pmic_regulator.test_regulator("mt8365")

    @patch("pmic_regulator.test_regulator")
    def test_main(self, mock_test_regulator):
        with patch("sys.argv", ["script_name", "mt8395"]):
            result = pmic_regulator.main()
        self.assertEqual(mock_test_regulator.call_count, 1)
        self.assertEqual(result, None)

    @patch("pmic_regulator.test_regulator")
    def test_main_bad_args(self, mock_test_regulator):
        with patch("sys.argv", ["script_name", "bad_soc"]):
            with self.assertRaises(SystemExit):
                pmic_regulator.main()
        mock_test_regulator.assert_not_called()

    @patch("pmic_regulator.test_regulator")
    def test_main_wrong_serialcheck(self, mock_test_regulator):
        mock_test_regulator.side_effect = SystemExit(1)
        with patch("sys.argv", ["script_name", "mt8395"]):
            with self.assertRaises(SystemExit):
                pmic_regulator.main()
        mock_test_regulator.assert_called_once_with("mt8395")
