import os
from unittest.mock import patch
import unittest
from WIFI_phy import (parse_iw_dev_output, parse_phy_info_output,
                      check_sta_support, check_freq_support,
                      create_phy_interface_mapping, main)

class WIFIphyData():
    @staticmethod
    def get_text(filenmae):
        full_path = os.path.join(
            os.path.dirname(os.path.realpath(__file__)),
            "test_WIFI_phy_data",
            filenmae
        )
        with open(full_path, 'r', encoding='UTF-8') as stream:
            return stream.read()


class WIFITest(unittest.TestCase, WIFIphyData):

    def setUp(self):
        self.iw_dev_file_list = ["iw_dev.log", "iw_dev2.log"]
        self.phy_info_file_list = ["RTL8821CE_AC.log", "QCNFA765_AX_6G.log",
                                   "BE200_AX.log", "BE200_BE.log"]

    @patch('WIFI_phy.check_output')
    def test_parse_iw_dev_output(self, mock_check_output):
        expected_result = {
            "iw_dev.log": [('phy#0', 'wlp2s0')],
            "iw_dev2.log": [('phy#0', 'wlp3s0f0'),
                            ('phy#1', 'wlp3s0f1')]
        }

        for file in self.iw_dev_file_list:
            mock_check_output.return_value = WIFIphyData.get_text(file)
            result = parse_iw_dev_output()
            self.assertEqual(result, expected_result[file])

    @patch('WIFI_phy.check_output')
    def test_create_phy_interface_mapping(self, mock_check_output):
        iw_dev_file = self.iw_dev_file_list[0]
        iw_dev_output = WIFIphyData.get_text(iw_dev_file)
        excvected_result = {
            "RTL8821CE_AC.log": {
                'wlp2s0': {
                    'PHY': 'phy#0',
                    'Bands': {
                        '1': ['2412 MHz [1] (30.0 dBm)'],
                        '2': ['5180 MHz [36] (23.0 dBm)']
                    },
                    'FREQ_Supported': {
                        '2.4GHz': 'supported',
                        '5GHz': 'supported',
                        '6GHz': 'unsupported'
                    },
                    'STA_Supported': {
                        'BE': 'unsupported',
                        'AX': 'unsupported',
                        'AC': 'supported'
                    }
                }
            },
            "QCNFA765_AX_6G.log": {
                'wlp2s0': {
                    'PHY': 'phy#0',
                    'Bands': {
                        '1': ['2412 MHz [1] (30.0 dBm)'],
                        '2': ['5180 MHz [36] (24.0 dBm)'],
                        '4': ['5955 MHz [1] (30.0 dBm)']
                    },
                    'FREQ_Supported': {
                        '2.4GHz': 'supported',
                        '5GHz': 'supported',
                        '6GHz': 'supported'
                    },
                    'STA_Supported': {
                        'BE': 'unsupported',
                        'AX': 'supported',
                        'AC': 'supported'
                    }
                }
            },
            "BE200_AX.log": {
                'wlp2s0': {
                    'PHY': 'phy#0',
                    'Bands': {
                        '1': ['2412 MHz [1] (22.0 dBm)'],
                        '2': ['5180 MHz [36] (22.0 dBm)'],
                        '4': []
                    },
                    'FREQ_Supported': {
                        '2.4GHz': 'supported',
                        '5GHz': 'supported',
                        '6GHz': 'unsupported'
                    },
                    'STA_Supported': {
                        'BE': 'unsupported',
                        'AX': 'supported',
                        'AC': 'supported'
                    }
                }
            },
            "BE200_BE.log": {
                'wlp2s0': {
                    'PHY': 'phy#0',
                    'Bands': {
                        '1': ['2412 MHz [1] (22.0 dBm)'],
                        '2': ['5180 MHz [36] (22.0 dBm)'],
                        '4': []
                    },
                    'FREQ_Supported': {
                        '2.4GHz': 'supported',
                        '5GHz': 'supported',
                        '6GHz': 'unsupported'
                    },
                    'STA_Supported': {
                        'BE': 'supported',
                        'AX': 'supported',
                        'AC': 'supported'
                    }
                }
            }
        }
        for file in self.phy_info_file_list:
            phy_info_output = WIFIphyData.get_text(file)
            mock_check_output.side_effect = [iw_dev_output, phy_info_output]
            phy_interface = parse_iw_dev_output()
            result = create_phy_interface_mapping(phy_interface)
            self.assertDictEqual(result, excvected_result[file])

    def test_parse_phy_info_output(self):
        phy_info_output = WIFIphyData.get_text(self.phy_info_file_list[0])
        result = parse_phy_info_output(phy_info_output)

        expected_result = {
            '1': ['2412 MHz [1] (30.0 dBm)'],
            '2': ['5180 MHz [36] (23.0 dBm)']
        }
        self.assertDictEqual(result, expected_result)

    def test_check_sta_support(self):
        phy_info_output = WIFIphyData.get_text(self.phy_info_file_list[0])
        result = check_sta_support(phy_info_output)

        expected_result = {
            'BE': 'unsupported',
            'AX': 'unsupported',
            'AC': 'supported'
        }
        self.assertDictEqual(result, expected_result)

    def test_check_freq_support(self):
        bands = {
            '1': ['2412 MHz [1] (30.0 dBm)'],
            '2': ['5180 MHz [36] (23.0 dBm)']
        }
        result = check_freq_support(bands)
        expected_result = {
            '2.4GHz': 'supported',
            '5GHz': 'supported',
            '6GHz': 'unsupported'
        }
        self.assertDictEqual(result, expected_result)

    @patch('WIFI_phy.print')
    @patch('WIFI_phy.check_output')
    def test_main(self, mock_check_output, mock_print):
        iw_dev_output = WIFIphyData.get_text(self.iw_dev_file_list[0])
        phy_info_output = WIFIphyData.get_text(self.phy_info_file_list[0])
        mock_check_output.side_effect = [iw_dev_output, phy_info_output]
        main()
        expected_calls = [
            unittest.mock.call('wlp2s0_2.4GHz: supported'),
            unittest.mock.call('wlp2s0_5GHz: supported'),
            unittest.mock.call('wlp2s0_6GHz: unsupported'),
            unittest.mock.call('wlp2s0_be: unsupported'),
            unittest.mock.call('wlp2s0_ax: unsupported'),
            unittest.mock.call('wlp2s0_ac: supported')
        ]
        mock_print.assert_has_calls(expected_calls, any_order=True)


if __name__ == '__main__':
    unittest.main()
