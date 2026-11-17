from io import StringIO
from pathlib import Path
from subprocess import CompletedProcess, PIPE
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import call, patch

import bluetooth_obex_send

PEER = "20:0B:74:59:73:5D"
OTHER_PEER = "A0:E7:0B:83:00:49"
IMAGE = "/test data/custom image.jpg"


class BluetoothObexSendTests(unittest.TestCase):
    def setUp(self):
        self.output = StringIO()
        stdout_patch = patch("sys.stdout", self.output)
        stdout_patch.start()
        self.addCleanup(stdout_patch.stop)
        run_patch = patch("bluetooth_obex_send.run", autospec=True)
        self.run = run_patch.start()
        self.addCleanup(run_patch.stop)
        self.run.return_value = CompletedProcess(
            args=[],
            returncode=0,
            stdout="[NEW] Device {} receiver".format(PEER),
        )
        transfer_patch = patch(
            "bluetooth_obex_send.ObexFTPTest", autospec=True
        )
        self.transfer = transfer_patch.start()
        self.addCleanup(transfer_patch.stop)
        self.transfer.return_value.send.return_value = 0

    def test_scan_notice_precedes_bluetoothctl(self):
        result = self.run.return_value

        def scan(*args, **kwargs):
            self.assertIn(
                "Scanning for available OBEX targets (up to 30 seconds)...",
                self.output.getvalue(),
            )
            return result

        self.run.side_effect = scan
        self.assertEqual(
            bluetooth_obex_send.scan_available_target(), result.stdout
        )
        self.run.assert_called_once_with(
            ["bluetoothctl", "--timeout", "30", "scan", "bredr"],
            stdout=PIPE,
            universal_newlines=True,
        )

    def test_failed_scan_does_not_transfer_to_printed_peer(self):
        self.run.return_value.returncode = 1
        with self.assertRaisesRegex(
            RuntimeError, "Bluetooth discovery failed"
        ):
            bluetooth_obex_send.obex_test(IMAGE, PEER)
        self.transfer.assert_not_called()

    def test_missing_bluetoothctl_reports_discovery_error(self):
        self.run.side_effect = FileNotFoundError("bluetoothctl not found")
        with self.assertRaisesRegex(
            RuntimeError, "Bluetooth discovery failed: bluetoothctl not found"
        ):
            bluetooth_obex_send.obex_test(IMAGE, PEER)
        self.transfer.assert_not_called()

    def test_normalizes_address_and_uses_existing_transfer_api(self):
        self.run.return_value.stdout = self.run.return_value.stdout.lower()
        self.assertTrue(
            bluetooth_obex_send.obex_test(IMAGE, "  " + PEER.lower() + "  ")
        )
        self.transfer.assert_called_once_with(IMAGE, PEER)
        self.transfer.return_value.send.assert_called_once_with()

    def test_undiscovered_peer_is_not_sent_image(self):
        self.run.return_value.stdout = "Discovery started"
        self.assertFalse(bluetooth_obex_send.obex_test(IMAGE, PEER))
        self.transfer.assert_not_called()
        self.assertIn(
            "No available BT devices found in scan.", self.output.getvalue()
        )

    def test_only_discovered_configured_targets_are_listed_and_tried(self):
        self.assertTrue(
            bluetooth_obex_send.obex_test(
                IMAGE, "{},{}".format(OTHER_PEER, PEER)
            )
        )
        self.transfer.assert_called_once_with(IMAGE, PEER)
        self.assertIn(
            "Discovered configured OBEX targets: " + PEER,
            self.output.getvalue(),
        )
        self.assertNotIn(OTHER_PEER, self.output.getvalue())

    def test_failed_transfer_tries_next_peer_without_rescanning(self):
        self.run.return_value.stdout += "\n[NEW] Device " + OTHER_PEER
        self.transfer.return_value.send.side_effect = [1, 0]
        self.assertTrue(
            bluetooth_obex_send.obex_test(
                IMAGE, "{},{}".format(PEER, OTHER_PEER)
            )
        )
        self.run.assert_called_once()
        self.assertEqual(
            self.transfer.call_args_list,
            [call(IMAGE, PEER), call(IMAGE, OTHER_PEER)],
        )
        output = self.output.getvalue()
        notice = "Discovered configured OBEX targets: {}, {}".format(
            PEER, OTHER_PEER
        )
        self.assertIn(notice, output)
        self.assertLess(
            output.index(notice), output.index("OBEX server BTDEVADDR:")
        )

    def test_transfer_oserror_tries_next_peer(self):
        self.run.return_value.stdout += "\n[NEW] Device " + OTHER_PEER
        transfer = self.transfer.return_value
        self.transfer.side_effect = [OSError("image unavailable"), transfer]
        self.assertTrue(
            bluetooth_obex_send.obex_test(
                IMAGE, "{},{}".format(PEER, OTHER_PEER)
            )
        )
        self.assertIn("image unavailable", self.output.getvalue())
        transfer.send.assert_called_once_with()

    def test_unsuccessful_transfer_is_not_reported_as_success(self):
        for result in (1, None):
            with self.subTest(result=result):
                self.transfer.return_value.send.return_value = result
                self.assertFalse(bluetooth_obex_send.obex_test(IMAGE, PEER))
        self.assertIn(
            "No available BT devices succeeded in OBEX transfer.",
            self.output.getvalue(),
        )


class BluetoothObexArgumentsTests(unittest.TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.directory = Path(directory.name)
        self.image = self.directory / "custom image.jpg"
        self.image.write_bytes(b"test image")

    def parse(self, *arguments):
        with patch("sys.argv", ["bluetooth_obex_send.py", *arguments]):
            return bluetooth_obex_send.register_arguments()

    def assert_invalid(self, arguments, message):
        with patch("sys.stderr", new_callable=StringIO) as stderr:
            with self.assertRaises(SystemExit) as raised:
                self.parse(*arguments)
        self.assertEqual(raised.exception.code, 2)
        self.assertIn(message, stderr.getvalue())

    def test_accepts_comma_separated_targets_and_readable_image(self):
        targets = "  {},{}  ".format(PEER.lower(), OTHER_PEER)
        args = self.parse(targets, str(self.image))
        self.assertEqual(args.btdevaddr, targets)
        self.assertEqual(args.image, str(self.image))

    def test_required_arguments(self):
        self.assert_invalid([], "btdevaddr")
        self.assert_invalid([PEER], "image")

    def test_rejects_empty_address(self):
        self.assert_invalid(
            ["   ", str(self.image)], "btdevaddr must not be empty"
        )

    def test_rejects_malformed_target_lists(self):
        for address in (
            "AA:BB:CC:DD:EE",
            "AA:BB:CC:DD:EE:FF:00",
            "AA:BB:CC:DD:EE:GG",
            "AA-BB-CC-DD-EE-FF",
            "A:BB:CC:DD:EE:FF",
            PEER + ",",
            "," + PEER,
            PEER + ",," + PEER,
            PEER + ",invalid",
        ):
            with self.subTest(address=address):
                self.assert_invalid(
                    [address, str(self.image)], "AA:BB:CC:DD:EE:FF"
                )

    def test_rejects_missing_image_and_directory(self):
        for image in (self.directory / "missing.jpg", self.directory):
            with self.subTest(image=image):
                self.assert_invalid(
                    [PEER, str(image)],
                    "image must be an existing regular file",
                )

    def test_rejects_unreadable_image(self):
        with patch(
            "builtins.open", side_effect=PermissionError("Permission denied")
        ):
            self.assert_invalid(
                [PEER, str(self.image)],
                "image cannot be read: Permission denied",
            )

    def test_invalid_image_stops_main_before_bluetooth_activity(self):
        with patch("bluetooth_obex_send.run") as scan, patch(
            "bluetooth_obex_send.ObexFTPTest"
        ) as transfer, patch(
            "sys.argv",
            ["bluetooth_obex_send.py", PEER, str(self.directory / "missing")],
        ), patch(
            "sys.stderr", new_callable=StringIO
        ):
            with self.assertRaises(SystemExit) as raised:
                bluetooth_obex_send.main()
        self.assertEqual(raised.exception.code, 2)
        scan.assert_not_called()
        transfer.assert_not_called()

    def test_main_maps_transfer_outcome_to_exit_status(self):
        with patch(
            "sys.argv", ["bluetooth_obex_send.py", PEER, str(self.image)]
        ), patch("bluetooth_obex_send.logging.basicConfig"), patch(
            "bluetooth_obex_send.obex_test"
        ) as transfer:
            for success, exit_status in ((True, 0), (False, 1)):
                with self.subTest(success=success):
                    transfer.return_value = success
                    self.assertEqual(bluetooth_obex_send.main(), exit_status)
            transfer.assert_called_with(str(self.image), PEER)

    def test_main_reports_scan_failure_without_traceback(self):
        with patch(
            "sys.argv", ["bluetooth_obex_send.py", PEER, str(self.image)]
        ), patch("bluetooth_obex_send.logging.basicConfig"), patch(
            "bluetooth_obex_send.obex_test",
            side_effect=RuntimeError("Bluetooth discovery failed"),
        ), patch(
            "sys.stderr", new_callable=StringIO
        ) as stderr:
            self.assertEqual(bluetooth_obex_send.main(), 1)
        self.assertEqual(stderr.getvalue(), "Bluetooth discovery failed\n")
