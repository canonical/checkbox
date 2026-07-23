#!/usr/bin/env python3

import json
import os
import tempfile
import unittest
from unittest.mock import patch

import general_utils


class TestLoadJsonFile(unittest.TestCase):
    def test_load_json_file_reads_relative_path_from_provider_data(self):
        with tempfile.TemporaryDirectory() as provider_dir:
            rel_path = "validation/config.json"
            full_dir = os.path.join(provider_dir, "validation")
            os.makedirs(full_dir, exist_ok=True)
            full_path = os.path.join(full_dir, "config.json")
            payload = {"result": "from-provider"}

            with open(full_path, "w", encoding="utf-8") as file_obj:
                json.dump(payload, file_obj)

            with patch.object(general_utils, "PLAINBOX_PROVIDER_DATA", provider_dir):
                data = general_utils.load_json_file(rel_path)

            self.assertEqual(data, payload)

    def test_load_json_file_reads_absolute_path_even_with_provider_data(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            abs_path = os.path.join(tmp_dir, "config.json")
            payload = {"result": "absolute-path"}

            with open(abs_path, "w", encoding="utf-8") as file_obj:
                json.dump(payload, file_obj)

            with patch.object(general_utils, "PLAINBOX_PROVIDER_DATA", "/tmp/provider"):
                data = general_utils.load_json_file(abs_path)

            self.assertEqual(data, payload)

    def test_load_json_file_returns_empty_dict_when_file_missing(self):
        with patch.object(general_utils, "PLAINBOX_PROVIDER_DATA", ""):
            data = general_utils.load_json_file("missing-file.json")

        self.assertEqual(data, {})

    def test_load_json_file_returns_empty_dict_and_logs_on_invalid_json(self):
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as temp_file:
            temp_file.write("{invalid json")
            bad_json_path = temp_file.name

        try:
            with patch.object(general_utils, "PLAINBOX_PROVIDER_DATA", ""):
                with patch("general_utils.logging.warning") as mock_warning:
                    data = general_utils.load_json_file(
                        bad_json_path, enable_loggder=True
                    )

            self.assertEqual(data, {})
            mock_warning.assert_called_once()
        finally:
            os.remove(bad_json_path)


if __name__ == "__main__":
    unittest.main()
