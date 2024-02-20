import unittest
from unittest.mock import patch, MagicMock


from storage_test import mountpoint

class TestMountpoint(unittest.TestCase):
    @patch("psutil.disk_partitions")
    def test_mountpoint_nominal(self, mock_disk_partitions):

        sdiskpart = MagicMock()
        sdiskpart.device = '/dev/sda1'
        sdiskpart.mountpoint = '/'
        mock_disk_partitions.return_value = [sdiskpart]
        self.assertEqual(mountpoint("/dev/sda1"), "/")

    @patch("psutil.disk_partitions")
    def test_mountpoint_nominal_multiple(self, mock_disk_partitions):

        mock_disk_partitions.return_value = [
            MagicMock(device='/dev/sda1', mountpoint='/'),
            MagicMock(device='/dev/sda2', mountpoint='/boot')
        ]
        self.assertEqual(mountpoint("/dev/sda2"), "/boot")


    @patch("psutil.disk_partitions")
    def test_mountpoint_empty(self, mock_disk_partitions):
        mock_disk_partitions.return_value = []
        self.assertEqual(mountpoint('/dev/sda1'), None)
