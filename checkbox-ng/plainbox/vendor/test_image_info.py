from unittest import TestCase
from unittest.mock import patch
from plainbox.vendor import image_info


class TestDCDStringToInfo(TestCase):
    def test_len_5(self):
        example = "canonical-oem-pinktiger-noble-hwe-20240709-33.iso"
        info = image_info.dcd_string_to_info(example)

        self.assertEqual(info["project"], "pinktiger")
        self.assertEqual(info["series"], "noble")

    def test_len_6(self):
        example = "canonical-oem-pinktiger-noble-oem-24.04a-20240709-33.iso"
        info = image_info.dcd_string_to_info(example)

        self.assertEqual(info["project"], "pinktiger")
        self.assertEqual(info["series"], "noble")

    def test_len_7(self):
        example = (
            "canonical-oem-pinktiger-noble-oem-24.04a-proposed-20240709-33.iso"
        )
        info = image_info.dcd_string_to_info(example)

        self.assertEqual(info["project"], "pinktiger")
        self.assertEqual(info["series"], "noble")

    def test_len_wrong(self):
        with self.assertRaises(SystemExit):
            image_info.dcd_string_to_info("canonical-oem-test-stub-dcd")

        with self.assertRaises(SystemExit):
            image_info.dcd_string_to_info("")


class TestDCDStringE2E(TestCase):
    @patch("subprocess.check_output")
    def test_ok_output(self, mock_check_output):
        mock_check_output.return_value = """{
          "Version": "24.04",
          "OEM": {
            "Vendor": "Some Inc.",
            "Product": "13312",
            "Family": "NOFAMILY",
            "DCD": "canonical-oem-pinktiger-noble-oem-24.04a-20240823-74"
          },
          "BIOS": {
            "Vendor": "Some Inc.",
            "Version": "0.1.20"
          },
          "Arch": "amd64",
          "HwCap": "x86-64-v3",
          "GPU": [
            {
              "Vendor": "0000",
              "Model": "0000"
            }
          ],
          "RAM": 16,
          "Partitions": [
            477.7,
            1.1
          ],
          "Autologin": true,
          "LivePatch": false,
          "Session": {
            "DE": "",
            "Name": "",
            "Type": "tty"
          },
          "Language": "en_US",
          "Timezone": "Etc/UTC",
          "Install": {
            "Type": "Flutter",
            "OEM": false,
            "Media": "Ubuntu OEM 24.04.1 LTS",
            "Stages": {
              "20": "loading",
              "218": "done"
            }
          }
        }"""
        image_info.main([])

    @patch("subprocess.check_output")
    def test_fail_no_dcd_output(self, mock_check_output):
        mock_check_output.return_value = """{
          "Version": "24.04",
          "BIOS": {
            "Vendor": "Some Inc.",
            "Version": "0.1.20"
          },
          "Arch": "amd64",
          "HwCap": "x86-64-v3",
          "GPU": [
            {
              "Vendor": "0000",
              "Model": "0000"
            }
          ],
          "RAM": 16,
          "Partitions": [
            477.7,
            1.1
          ],
          "Autologin": true,
          "LivePatch": false,
          "Session": {
            "DE": "",
            "Name": "",
            "Type": "tty"
          },
          "Language": "en_US",
          "Timezone": "Etc/UTC",
          "Install": {
            "Type": "Flutter",
            "OEM": false,
            "Media": "Ubuntu OEM 24.04.1 LTS",
            "Stages": {
              "20": "loading",
              "218": "done"
            }
          }
        }"""
        with self.assertRaises(SystemExit):
            image_info.main([])
