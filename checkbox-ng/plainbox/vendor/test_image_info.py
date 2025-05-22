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


class TestDCDStringToInfoIoT(TestCase):
    def test_valid_dcd_with_all_fields(self):
        example = (
            "canonical-oem-carlsbad:element-v2-uc24:20241205.15:v2-uc24-x01"
        )
        info = image_info.dcd_string_to_info_iot(example)

        self.assertEqual(info["project"], "carlsbad")
        self.assertEqual(info["series"], "element-v2-uc24")
        self.assertEqual(info["build_id"], "20241205.15")
        self.assertEqual(
            info["url"],
            "https://oem-share.canonical.com/partners/carlsbad/share/element-v2-uc24/20241205.15/carlsbad-element-v2-uc24-20241205.15.tar.xz",
        )

    def test_valid_dcd_no_additional_info(self):
        example = "canonical-oem-shiner:x8high35-som-pdk:20250507-1170:"
        info = image_info.dcd_string_to_info_iot(example)

        self.assertEqual(info["project"], "shiner")
        self.assertEqual(info["series"], "x8high35-som-pdk")
        self.assertEqual(info["build_id"], "20250507-1170")
        self.assertEqual(
            info["url"],
            "https://oem-share.canonical.com/partners/shiner/share/x8high35-som-pdk/20250507-1170/shiner-x8high35-som-pdk-20250507-1170.tar.xz",
        )

    def test_invalid_dcd_formats(self):
        invalid_examples = [
            # Missing canonical-oem- prefix
            "projectalpha:series:20241210:",
            # Missing project name
            "canonical-oem-:series:20241210:",
            # Missing series
            "canonical-oem-project::",
            # Missing build ID
            "canonical-oem-project:series::",
            # Invalid project name (special chars)
            "canonical-oem-project@123:series:20241210:",
            # Invalid series (special chars)
            "canonical-oem-project:series@123:20241210:",
            # Invalid build ID (letters)
            "canonical-oem-project:series:abc123:",
            # Empty string
            "",
            # Wrong format
            "canonical-oem-test-stub-dcd",
        ]

        for example in invalid_examples:
            with self.assertRaises(
                ValueError, msg="Should fail for: {}".format(example)
            ):
                image_info.dcd_string_to_info_iot(example)


class TestDCDStringE2EIoT(TestCase):
    @patch("builtins.open")
    @patch("pathlib.Path.is_file")
    def test_dcd_info_iot_path_all_fields(self, mock_is_file, mock_open):
        mock_is_file.return_value = True
        mock_file = mock_open.return_value.__enter__.return_value
        mock_file.read.return_value = (
            "canonical-oem-carlsbad:element-v2-uc24:20241205.15:v2-uc24-x01"
        )

        info = image_info.dcd_info()

        self.assertEqual(info["project"], "carlsbad")
        self.assertEqual(info["series"], "element-v2-uc24")
        self.assertEqual(info["build_id"], "20241205.15")
        self.assertEqual(
            info["url"],
            "https://oem-share.canonical.com/partners/carlsbad/share/element-v2-uc24/20241205.15/carlsbad-element-v2-uc24-20241205.15.tar.xz",
        )

    @patch("builtins.open")
    @patch("pathlib.Path.is_file")
    def test_dcd_info_iot_path_no_additional_info(
        self, mock_is_file, mock_open
    ):
        mock_is_file.return_value = True
        mock_file = mock_open.return_value.__enter__.return_value
        mock_file.read.return_value = (
            "canonical-oem-shiner:x8high35-som-pdk:20250507-1170:"
        )

        info = image_info.dcd_info()

        self.assertEqual(info["project"], "shiner")
        self.assertEqual(info["series"], "x8high35-som-pdk")
        self.assertEqual(info["build_id"], "20250507-1170")
        self.assertEqual(
            info["url"],
            "https://oem-share.canonical.com/partners/shiner/share/x8high35-som-pdk/20250507-1170/shiner-x8high35-som-pdk-20250507-1170.tar.xz",
        )

    @patch("pathlib.Path.is_file")
    @patch("subprocess.check_output")
    def test_dcd_info_iot_path_not_exists(
        self, mock_check_output, mock_is_file
    ):
        mock_is_file.return_value = False
        mock_check_output.return_value = """{
          "Version": "24.04",
          "OEM": {
            "Vendor": "Some Inc.",
            "Product": "13312",
            "Family": "NOFAMILY",
            "DCD": "canonical-oem-pinktiger-noble-oem-24.04a-20240823-74"
          }
        }"""

        info = image_info.dcd_info()
        # Since iot dcd file is missing, this must be pc platform
        self.assertEqual(info["project"], "pinktiger")
        self.assertEqual(info["series"], "noble")
