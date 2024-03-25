import subprocess
import unittest
from unittest.mock import patch, MagicMock
import spidev_test as spidev


class TestSpidev(unittest.TestCase):

    @patch("spidev_test.subprocess.run")
    def test_runcmd(self, mock_run):
        mock_run.return_value = MagicMock(
            stdout="output", stderr="error", returncode=0
        )
        result = spidev.runcmd("echo Hello")

        mock_run.assert_called_once_with(
            "echo Hello",
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding="utf-8",
            timeout=1,
        )
        self.assertEqual(result.stdout, "output")
        self.assertEqual(result.stderr, "error")
        self.assertEqual(result.returncode, 0)

    @patch("spidev_test.os.path.exists")
    def test_check_spi_node(self, mock_exists):
        mock_exists.return_value = True
        result = spidev.check_spi_node("/dev/spidev0.0")
        self.assertEqual(result, None)

    @patch("spidev_test.os.path.exists")
    def test_check_spi_node_fail(self, mock_exists):
        mock_exists.return_value = False
        with self.assertRaises(SystemExit):
            spidev.check_spi_node("/dev/spidev0.0")

    @patch("spidev_test.PLAINBOX_PROVIDER_DATA", "/tmp")
    @patch("spidev_test.runcmd")
    @patch("spidev_test.check_spi_node")
    def test_test_spi_content(self, mock_check_spi, mock_runcmd):
        mock_check_spi.return_value = None
        mock_runcmd.return_value = MagicMock(
            stdout=(
                "TX | FF FF FF FF FF FF | ......\n"
                "RX | FF FF FF FF FF FF | ......\n"
            ),
            stderr="",
            returncode=0,
        )

        result = spidev.test_spi_content_consistency("G1200-evk")
        self.assertEqual(result, None)
        mock_runcmd.assert_called_with(
            [
                "genio-test-tool.spidev-test -D /dev/spidev1.0 -s 400000 -i "
                "/tmp/spi/test.bin -v",
            ],
        )

    @patch("spidev_test.PLAINBOX_PROVIDER_DATA", "/tmp")
    @patch("spidev_test.runcmd")
    @patch("spidev_test.check_spi_node")
    def test_test_spi_content_G700(self, mock_check_spi, mock_runcmd):
        mock_check_spi.return_value = None
        mock_runcmd.return_value = MagicMock(
            stdout=(
                "TX | FF FF FF FF FF FF | ......\n"
                "RX | FF FF FF FF FF FF | ......\n"
            ),
            stderr="",
            returncode=0,
        )

        result = spidev.test_spi_content_consistency("G700")
        self.assertEqual(result, None)
        mock_runcmd.assert_called_with(
            [
                "genio-test-tool.spidev-test -D /dev/spidev0.0 -s 400000 -i "
                "/tmp/spi/test.bin -v",
            ],
        )

    @patch("spidev_test.PLAINBOX_PROVIDER_DATA", "/tmp")
    @patch("spidev_test.runcmd")
    @patch("spidev_test.check_spi_node")
    def test_test_spi_content_no_packets(self, mock_check_spi, mock_runcmd):
        mock_check_spi.return_value = None
        mock_runcmd.return_value = MagicMock(
            stdout="",
            stderr="",
            returncode=0,
        )
        with self.assertRaises(SystemExit):
            spidev.test_spi_content_consistency("G1200-evk")

    @patch("spidev_test.PLAINBOX_PROVIDER_DATA", "/tmp")
    @patch("spidev_test.runcmd")
    @patch("spidev_test.check_spi_node")
    def test_test_spi_content_no_consistency(
        self, mock_check_spi, mock_runcmd
    ):
        mock_check_spi.return_value = None
        mock_runcmd.return_value = MagicMock(
            stdout=(
                "TX | FF FF FF FF FF FF | ......\n"
                "RX | 31 31 31 31 31 31 | 111111\n"
            ),
            stderr="",
            returncode=0,
        )
        with self.assertRaises(SystemExit):
            spidev.test_spi_content_consistency("G1200-evk")

    @patch("spidev_test.test_spi_content_consistency")
    def test_main(self, mock_spi_content):
        mock_spi_content.return_value = 0
        with patch("sys.argv", ["platform", "G1200-evk"]):
            result = spidev.main()
        self.assertEqual(mock_spi_content.call_count, 1)
        self.assertEqual(result, None)

    @patch("spidev_test.test_spi_content_consistency")
    def test_main_bad_args(self, mock_spi_content):
        mock_spi_content.return_value = 1
        with patch("sys.argv", ["script_name", "bad_soc"]):
            with self.assertRaises(SystemExit):
                spidev.main()
        mock_spi_content.assert_not_called()

    @patch("spidev_test.test_spi_content_consistency")
    def test_main_wrong_serialcheck(self, mock_spi_content):
        mock_spi_content.side_effect = SystemExit(1)
        with patch("sys.argv", ["script_name", "G1200-evk"]):
            with self.assertRaises(SystemExit):
                spidev.main()
        self.assertEqual(mock_spi_content.call_count, 1)
