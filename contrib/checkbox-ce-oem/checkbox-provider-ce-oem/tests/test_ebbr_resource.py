import io
import unittest
from unittest.mock import MagicMock, patch

import ebbr_resource

EBBR_OUTPUT = """EBBR tests:
 dt_base         Base device tree validity check
 uefirtvariable  UEFI Runtime service variable interface tests.
 uefivarinfo     UEFI variable info query.

"""

UTILS_OUTPUT = """Utilities:
 uefidump        Dump UEFI variables.
 uefivarinfo     UEFI variable info query.

"""


class TestEbbrResource(unittest.TestCase):
    @patch("ebbr_resource.runcmd")
    @patch("sys.stdout", new_callable=io.StringIO)
    def test_utilities_are_marked(self, mock_stdout, mock_runcmd):
        mock_runcmd.side_effect = [
            MagicMock(stdout=EBBR_OUTPUT),
            MagicMock(stdout=UTILS_OUTPUT),
        ]

        ebbr_resource.main()

        self.assertEqual(
            mock_stdout.getvalue(),
            "case: dt_base\n"
            "description: Base device tree validity\n"
            "fwts_type: EBBR\n\n"
            "case: uefirtvariable\n"
            "description: UEFI Runtime service variable interface\n"
            "fwts_type: EBBR\n\n"
            "case: uefivarinfo\n"
            "description: UEFI variable info\n"
            "fwts_type: Utilities\n\n",
        )

    @patch("ebbr_resource.runcmd")
    def test_no_ebbr_tests_raises(self, mock_runcmd):
        mock_runcmd.return_value = MagicMock(
            stdout="",
            stderr="The --ebbr option is not available on this architecture",
        )

        with self.assertRaises(SystemExit) as cm:
            ebbr_resource.main()

        self.assertIn("not available on this architecture", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
