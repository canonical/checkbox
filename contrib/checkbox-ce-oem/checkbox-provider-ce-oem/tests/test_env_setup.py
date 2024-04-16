import unittest
from unittest.mock import patch, mock_open
import json
import env_setup


class TestGetConfig(unittest.TestCase):

    @patch("os.path.exists", return_value=True)
    def test_valid_config_file(self, mock_exists):
        config_path = "/path/to/valid_config.json"
        mock_file_content = '{"key": "value"}'
        config_file = {}
        with patch(
            "builtins.open", mock_open(read_data=mock_file_content)
        ) as mock_file:
            config = env_setup.get_config(config_file, config_path)

        mock_file.assert_called_once_with(config_path)
        self.assertEqual(config, {"key": "value"})

    def test_invalid_config_file(self):
        config_path = "/path/to/invalid_config.json"
        config_file = {
            "test-strict-confinement": {
                "channel": "edge",
                "plugs": {
                    "jace-bt-led": {
                        "gadget": "bt-led",
                    },
                },
            },
        }

        with patch("builtins.open", side_effect=json.JSONDecodeError):
            config = env_setup.get_config(config_file, config_path)

        self.assertEqual(
            config,
            {
                "test-strict-confinement": {
                    "channel": "edge",
                    "plugs": {
                        "jace-bt-led": {
                            "gadget": "bt-led",
                        },
                    },
                },
            },
        )

    def test_nonexistent_config_file(self):
        config_path = "/path/to/nonexistent_config.json"
        config_file = {
            "test-strict-confinement": {
                "channel": "edge",
                "plugs": {
                    "jace-bt-led": {
                        "gadget": "bt-led",
                    },
                },
            },
        }

        with patch("builtins.open", side_effect=FileNotFoundError):
            config = env_setup.get_config(config_file, config_path)

        self.assertEqual(
            config,
            {
                "test-strict-confinement": {
                    "channel": "edge",
                    "plugs": {
                        "jace-bt-led": {
                            "gadget": "bt-led",
                        },
                    },
                },
            },
        )
        # Additional checks/assertions if needed

    def test_empty_config_path(self):
        config_path = ""
        config_file = {
            "test-strict-confinement": {
                "channel": "edge",
                "plugs": {
                    "jace-bt-led": {
                        "gadget": "bt-led",
                    },
                },
            },
        }

        config = env_setup.get_config(config_file, config_path)

        self.assertEqual(
            config,
            {
                "test-strict-confinement": {
                    "channel": "edge",
                    "plugs": {
                        "jace-bt-led": {
                            "gadget": "bt-led",
                        },
                    },
                },
            },
        )
