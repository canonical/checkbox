import unittest as ut
from unittest.mock import MagicMock, patch, call
from v4l2_ioctl_resource import main
from checkbox_support.parsers.v4l2_compliance import TEST_NAME_TO_IOCTL_MAP


class TestV4L2IoctlResource(ut.TestCase):
    @patch("v4l2_ioctl_resource.check_output")
    def test_all_ioctl_names_are_generated(self, mock_check_output: MagicMock):
        mock_check_output.return_value = "\n".join(
            [
                "path: /devices/pci0000:00/0000:00:14.0/usb3/3-9/3-9:1.0/video4linux/video0",
                "name: video0",
                "bus: video4linux",
                "category: CAPTURE",
                "driver: uvcvideo",
                "product_id: 22782",
                "vendor_id: 3034",
                "product: Integrated_Webcam_HD: Integrate",
                "vendor: CN0PW36V8LG009BQA0YWA00",
                "product_slug: Integrated_Webcam_HD__Integrate",
                "vendor_slug: CN0PW36V8LG009BQA0YWA00",
            ]
        )
        main()
        
