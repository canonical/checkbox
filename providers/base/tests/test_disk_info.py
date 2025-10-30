import unittest
import textwrap
from contextlib import redirect_stdout
from io import StringIO
from unittest.mock import patch

import disk_info


class DiskInfoTests(unittest.TestCase):
    @patch("disk_info.get_lsblk_json")
    def test_disk_info_main_ok(self, mock_get_lsblk_json):
        mock_get_lsblk_json.return_value = {
            "blockdevices": [
                {
                    "kname": "loop17",
                    "type": "loop",
                    "size": "247.6M",
                    "model": None,
                    "mountpoint": "/snap/firefox/6966",
                },
                {
                    "kname": "sda",
                    "type": "disk",
                    "size": "111.8G",
                    "model": None,
                    "mountpoint": None,
                },
                {
                    "kname": "sda1",
                    "type": "part",
                    "size": "512M",
                    "model": None,
                    "mountpoint": None,
                },
                {
                    "kname": "sde",
                    "type": "disk",
                    "size": "1.8T",
                    "model": "ST2000DM008-2FR102",
                    "mountpoint": None,
                },
                {
                    "kname": "nvme1n1",
                    "type": "disk",
                    "size": "953.9G",
                    "model": "KXG70ZNV1T02 NVMe KIOXIA 1024GB",
                    "mountpoint": None,
                },
                {
                    "kname": "nvme0n1",
                    "type": "disk",
                    "size": "1.8T",
                    "model": "WD_BLACK SN850X 2000GB",
                    "mountpoint": None,
                },
                {
                    "kname": "sdf",
                    "type": "disk",
                    "size": "1.8T",
                    "model": "This should be skipped because it's snapd/save",
                    "mountpoint": "/snapd/save",
                },
                {
                    "kname": "mmcblk0",
                    "type": "disk",
                    "size": "4G",
                    "model": "This should be kept because it's seen as root partition",
                    "mountpoint": "/",
                },
                {
                    "kname": "mmcblk1",
                    "type": "disk",
                    "size": "4G",
                    "model": "This should be skipped because it's an eMMC",
                    "mountpoint": None,
                },
            ]
        }
        expected_output = textwrap.dedent(
            """\
            Name: /dev/sda
            	Model: 	Unknown
            	Size:  	111.8G
            Name: /dev/sde
            	Model: 	ST2000DM008-2FR102
            	Size:  	1.8T
            Name: /dev/nvme1n1
            	Model: 	KXG70ZNV1T02 NVMe KIOXIA 1024GB
            	Size:  	953.9G
            Name: /dev/nvme0n1
            	Model: 	WD_BLACK SN850X 2000GB
            	Size:  	1.8T
            Name: /dev/mmcblk0
            	Model: 	This should be kept because it's seen as root partition
            	Size:  	4G
            """
        )
        with redirect_stdout(StringIO()) as buffer:
            disk_info.main()

        self.assertEqual(buffer.getvalue(), expected_output)
