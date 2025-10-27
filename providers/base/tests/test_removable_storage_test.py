import unittest
from unittest.mock import MagicMock

from removable_storage_test import DiskTest


class DiskTestTests(unittest.TestCase):

    def test_find_parent_ok(self):
        self_mock = MagicMock()
        self_mock.lsblk = {
            "blockdevices": [
                {
                    "kname": "nvme0n1",
                    "type": "disk",
                    "size": "1.8T",
                    "model": "WD_BLACK SN850X 2000GB",
                    "mountpoint": None,
                },
            ]
        }

        self.assertEqual(
            DiskTest._find_parent(self_mock, "nvme0n1"), "nvme0n1"
        )

    def test_find_parent_not(self):
        self_mock = MagicMock()
        self_mock.lsblk = {
            "blockdevices": [
                {
                    "kname": "nvme0n1",
                    "type": "disk",
                    "size": "1.8T",
                    "model": "WD_BLACK SN850X 2000GB",
                    "mountpoint": None,
                },
            ]
        }

        self.assertEqual(DiskTest._find_parent(self_mock, "sda"), False)
