import unittest
from unittest import mock
import check_vpu_device


class VPUDeviceCheckTests(unittest.TestCase):
    """
    Unit tests for Check VPU device test scripts
    """
    @mock.patch("pathlib.Path.read_text")
    @mock.patch("pathlib.Path.is_file")
    def test_soc_family_available(self, mock_is_file, mock_read_text):
        """
        Checking SoC family file is available
        """
        expected_soc_family = "Freescale i.MX"
        mock_is_file.return_value = True
        mock_read_text.return_value = expected_soc_family
        with self.assertLogs() as lc:
            soc_family = check_vpu_device.get_soc_family()

        self.assertEqual(
            "INFO:root:SoC family is {}".format(expected_soc_family),
            lc.output[-1])
        self.assertEqual(soc_family, expected_soc_family)

    @mock.patch("pathlib.Path.is_file")
    def test_soc_family_not_available(self, mock_is_file):
        """
        Checking SoC family file is not available
        """
        mock_is_file.return_value = False
        with self.assertRaises(FileNotFoundError):
            check_vpu_device.get_soc_family()

    @mock.patch("pathlib.Path.read_text")
    @mock.patch("pathlib.Path.is_file")
    def test_soc_id_available(self, mock_is_file, mock_read_text):
        """
        Checking SoC ID file is available
        """
        expected_soc_id = "i.MX8MQ"
        mock_is_file.return_value = True
        mock_read_text.return_value = expected_soc_id
        with self.assertLogs() as lc:
            soc_id = check_vpu_device.get_soc_id()

        self.assertEqual(
            "INFO:root:SoC ID is {}".format(expected_soc_id),
            lc.output[-1])
        self.assertEqual(soc_id, expected_soc_id)

    @mock.patch("pathlib.Path.is_file")
    def test_soc_id_not_available(self, mock_is_file):
        """
        Checking SoC ID file is not available
        """
        mock_is_file.return_value = False
        with self.assertRaises(FileNotFoundError):
            check_vpu_device.get_soc_id()

    @mock.patch("pathlib.Path.read_text")
    @mock.patch("pathlib.Path.is_file")
    def test_kernel_version_available(self, mock_is_file, mock_read_text):
        """
        Checking kernel version file is available
        """
        kernel_raw_data = (
            "Linux version 5.15.0-89-generic (buildd@lcy02-amd64-004) "
            "(gcc (Ubuntu 9.4.0-1ubuntu1~20.04.2) 9.4.0, "
            "GNU ld (GNU Binutils for Ubuntu) 2.34) "
            "#99~20.04.1-Ubuntu SMP Thu Nov 2 15:16:47 UTC 2023"
        )
        expected_ver = "5.15"
        mock_is_file.return_value = True
        mock_read_text.return_value = kernel_raw_data
        kernel_ver = check_vpu_device.get_kernel_version()

        self.assertEqual(kernel_ver, expected_ver)

    @mock.patch("pathlib.Path.read_text")
    @mock.patch("pathlib.Path.is_file")
    def test_kernel_version_mismatch(self, mock_is_file, mock_read_text):
        """
        Checking kernel version format mismatch
        """
        kernel_raw_data = "Linux version 5.1-89-generic (amd64-004)"
        mock_is_file.return_value = True
        mock_read_text.return_value = kernel_raw_data
        with self.assertRaises(ValueError):
            check_vpu_device.get_kernel_version()

    @mock.patch("pathlib.Path.is_file")
    def test_kernel_file_not_available(self, mock_is_file):
        """
        Checking kernel version file is not available
        """
        mock_is_file.return_value = False
        with self.assertRaises(FileNotFoundError):
            check_vpu_device.get_kernel_version()

    def test_imx8mm_vpus(self):
        """
        Checking expected VPU devices for i.MX8MM running 5.4 kernel
        """
        expected_devices = ["ion", "mxc_hantro", "mxc_hantro_h1"]
        self.assertListEqual(
            check_vpu_device.determine_expected_imx_vpu("i.MX8MM", "5.4"),
            expected_devices
        )

    def test_imx8ml_vpus_515(self):
        """
        Checking expected VPU devices for i.MX8ML running 5.15 kernel
        """
        expected_devices = ["mxc_hantro", "mxc_hantro_h1"]
        self.assertListEqual(
            check_vpu_device.determine_expected_imx_vpu("i.MX8ML", "5.15"),
            expected_devices
        )

    def test_imx8mq_vpus(self):
        """
        Checking expected VPU devices for i.MX8MQ running 5.4 kernel
        """
        expected_devices = ["ion", "mxc_hantro"]
        self.assertListEqual(
            check_vpu_device.determine_expected_imx_vpu("i.MX8MQ", "5.4"),
            expected_devices
        )

    def test_imx8mp_vpus(self):
        """
        Checking expected VPU devices for i.MX8MQ running 5.4 kernel
        """
        expected_devices = ["ion", "mxc_hantro", "mxc_hantro_vc8000e"]
        self.assertListEqual(
            check_vpu_device.determine_expected_imx_vpu("i.MX8MP", "5.4"),
            expected_devices
        )

    def test_imx_chip_mismatch(self):
        """
        Checking i.MX chip mismatch
        """
        with self.assertRaisesRegex(
            SystemExit,
            "Supported VPU devices for i.MX8MX is not defined"
        ):
            check_vpu_device.determine_expected_imx_vpu("i.MX8MX", "5.4")

    @mock.patch("pathlib.Path.iterdir")
    @mock.patch("check_vpu_device.get_soc_id")
    @mock.patch("check_vpu_device.get_kernel_version")
    @mock.patch("check_vpu_device.determine_expected_imx_vpu")
    def test_imx8mm_vpu_device_exist(
            self,
            mock_expected_imx_vpu,
            mock_kernel_ver,
            mock_soc_id,
            mock_listdir):
        """
        Checking i.MX8MM VPU device is available
        """
        prefix = "INFO:root:The {} device is available"
        expected_imx_vpus = [
            "ion", "mxc_hantro", "mxc_hantro_h1"
        ]

        mock_expected_imx_vpu.return_value = expected_imx_vpus
        mock_kernel_ver.return_value = "5.4"
        mock_soc_id.return_value = "i.MX8MM"
        mock_result = [mock.Mock(), mock.Mock(), mock.Mock()]
        mock_result[0].name = "ion"
        mock_result[1].name = "mxc_hantro"
        mock_result[2].name = "mxc_hantro_h1"
        mock_listdir.return_value = mock_result

        with self.assertLogs() as lc:
            check_vpu_device.check_imx_vpu_devices()

        for index, value in enumerate(expected_imx_vpus):
            self.assertEqual(
                prefix.format(value), lc.output[index])
        self.assertIn("# VPU devices check: Passed", lc.output[-1])

    @mock.patch("pathlib.Path.iterdir")
    @mock.patch("check_vpu_device.get_soc_id")
    @mock.patch("check_vpu_device.get_kernel_version")
    @mock.patch("check_vpu_device.determine_expected_imx_vpu")
    def test_imx8mm_vpu_device_not_exist(
            self,
            mock_expected_imx_vpu,
            mock_kernel_ver,
            mock_soc_id,
            mock_listdir):
        """
        Checking i.MX8MM VPU device is exists
        """
        mock_kernel_ver.return_value = "5.4"
        mock_soc_id.return_value = "i.MX8MM"
        mock_expected_imx_vpu.return_value = [
            "ion", "mxc_hantro", "mxc_hantro_h1"
        ]
        mock_result = [mock.Mock(), mock.Mock()]
        mock_result[0].name = "ion"
        mock_result[1].name = "mxc_hantro"
        mock_listdir.return_value = mock_result

        with self.assertRaises(SystemExit), \
             self.assertLogs(level="ERROR") as lc:

            check_vpu_device.check_imx_vpu_devices()
        self.assertEqual(
            "ERROR:root:The mxc_hantro_h1 device is not exists!",
            lc.output[-1])

    @mock.patch("check_vpu_device.get_v4l2_devices")
    def test_mtk_vpu_devices(self, mock_v4l2_devices):
        """
        Checking MTK VPU VPU device is available
        """
        mock_v4l2_devices.return_value = [
            "mtk-vcodec-dec",
            "15050000.camsv video stream",
            "mtk-mdp:m2m",
            "mtk-vcodec-enc"
        ]
        expected_devices = [
            "mtk-vcodec-dec",
            "mtk-vcodec-enc",
            "mtk-mdp:m2m"
        ]
        prefix = "INFO:root:VPU {} device detected"

        with self.assertLogs() as lc:
            check_vpu_device.check_mtk_vpu_devices()

        for index, dev in enumerate(expected_devices):
            self.assertEqual(prefix.format(dev), lc.output[index])

        self.assertEqual(
            "INFO:root:# VPU devices check: Passed",
            lc.output[-1])

    @mock.patch("check_vpu_device.get_v4l2_devices")
    def test_mtk_vpu_devices_mismatch(self, mock_v4l2_devices):
        """
        Checking MTK VPU VPU devices is mismatch
        """
        mock_v4l2_devices.return_value = [
            "mtk-vcodec-dec",
            "15050000.camsv video stream",
            "mtk-vcodec-enc"
        ]

        with self.assertRaisesRegex(
            SystemExit,
            "# VPU devices check: Failed"
        ):
            check_vpu_device.check_mtk_vpu_devices()
