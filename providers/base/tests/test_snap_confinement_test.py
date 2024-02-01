import logging
import unittest
from unittest.mock import patch, MagicMock
from snap_confinement_test import SnapsConfinementVerifier, main


class TestSnapsConfinementVerifier(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        logging.disable(logging.CRITICAL)

    @classmethod
    def tearDownClass(cls):
        logging.disable(logging.NOTSET)

    def setUp(self):
        self.verifier = SnapsConfinementVerifier()

    def test_snap_in_allow_list_from_config_var(self):
        with patch.dict(
            'os.environ', {"SNAP_CONFINEMENT_ALLOWLIST": "sp1, sp2"}
        ):
            verifier = SnapsConfinementVerifier()
            result = verifier._is_snap_in_allow_list("sp2")
            self.assertTrue(result)

    def test_snap_in_official_allow_list(self):
        result = self.verifier._is_snap_in_allow_list("bugit")
        self.assertTrue(result)

    def test_snap_not_in_allow_list(self):
        result = self.verifier._is_snap_in_allow_list("non_allowed_snap")
        self.assertFalse(result)

    def test_is_snap_confinement_not_strict_catchs_none_strict_snap(self):
        result = self.verifier._is_snap_confinement_not_strict("classic")
        self.assertTrue(result)

    def test_is_snap_confinement_not_strict_success(self):
        result = self.verifier._is_snap_confinement_not_strict("strict")
        self.assertFalse(result)

    def test_is_snap_devmode_catchs_devmode_snap(self):
        result = self.verifier._is_snap_devmode(True)
        self.assertTrue(result)

    def test_is_snap_devmode_success(self):
        result = self.verifier._is_snap_devmode(False)
        self.assertFalse(result)

    def test_is_snap_sideloaded_revision_catchs_sideload_snap(self):
        result = self.verifier._is_snap_sideloaded_revision("x123")
        self.assertTrue(result)

    def test_is_snap_sideloaded_revision_success(self):
        result = self.verifier._is_snap_sideloaded_revision("y456")
        self.assertFalse(result)

    def test_extract_attributes_from_snap_success(self):
        self.verifier._desired_attributes = ["hello"]
        mock_snap = {"hello": "world", "foo": "bar"}
        result = self.verifier._extract_attributes_from_snap(mock_snap)
        self.assertEqual(result, (False, {"hello": "world"}))

    def test_extract_attributes_from_snap_missing_desired_attribute(self):
        self.verifier._desired_attributes = ["name", "nonexistent_attr"]
        mock_snap = {"name": "test_snap"}
        result = self.verifier._extract_attributes_from_snap(mock_snap)
        self.assertEqual(result, (True, {"name": "test_snap"}))

    @patch("snap_confinement_test.Snapd.list")
    def test_verify_snap_no_snaps_from_snapd_list(self, mock_snapd_list):
        mock_snapd_list.return_value = []
        self.assertEqual(0, self.verifier.verify_snap())

    @patch("snap_confinement_test.SnapsConfinementVerifier._extract_attributes_from_snap")   # noqa E501
    @patch("snap_confinement_test.Snapd.list")
    def test_verify_snap_fail_without_desired_attribute_in_a_snap(
        self,
        mock_snapd_list,
        mock_extract_attributes_from_snap
    ):
        mock_snapd_list.return_value = [{"foo": "bar"}]
        mock_extract_attributes_from_snap.return_value = (True, {})
        self.assertEqual(1, self.verifier.verify_snap())

    @patch("snap_confinement_test.SnapsConfinementVerifier._is_snap_in_allow_list")   # noqa E501
    @patch("snap_confinement_test.SnapsConfinementVerifier._extract_attributes_from_snap")   # noqa E501
    @patch("snap_confinement_test.Snapd.list")
    def test_verify_snap_pass_if_snap_in_allow_list(
        self,
        mock_snapd_list,
        mock_extract_attributes_from_snap,
        mock_is_snap_in_allow_list
    ):
        snap_info = {"name": "foo"}
        mock_snapd_list.return_value = [snap_info]
        mock_extract_attributes_from_snap.return_value = (False, snap_info)
        mock_is_snap_in_allow_list.return_value = True
        result = self.verifier.verify_snap()
        mock_is_snap_in_allow_list.assert_called_once_with(
            snap_info.get("name"))
        self.assertEqual(0, result)

    @patch("snap_confinement_test.SnapsConfinementVerifier._is_snap_sideloaded_revision")   # noqa E501
    @patch("snap_confinement_test.SnapsConfinementVerifier._is_snap_devmode")   # noqa E501
    @patch("snap_confinement_test.SnapsConfinementVerifier._is_snap_confinement_not_strict")   # noqa E501
    @patch("snap_confinement_test.SnapsConfinementVerifier._is_snap_in_allow_list")   # noqa E501
    @patch("snap_confinement_test.SnapsConfinementVerifier._extract_attributes_from_snap")   # noqa E501
    @patch("snap_confinement_test.Snapd.list")
    def test_verify_snap_success(
        self,
        mock_snapd_list,
        mock_extract_attributes_from_snap,
        mock_is_snap_in_allow_list,
        mock_is_snap_confinement_not_strict,
        mock_is_snap_devmode,
        mock_is_snap_sideloaded_revision,
    ):
        """
        Check verify_snap return 0 if a snap mach all the check criteria
        """
        snap_info = {
            "name": "foo-snap",
            "devmode": False,
            "confinement": "strict",
            "revision": "999"
        }
        mock_snapd_list.return_value = [snap_info]
        mock_extract_attributes_from_snap.return_value = (False, snap_info)
        mock_is_snap_in_allow_list.return_value = False
        mock_is_snap_confinement_not_strict.return_value = False
        mock_is_snap_devmode.return_value = False
        mock_is_snap_sideloaded_revision.return_value = False

        result = self.verifier.verify_snap()
        mock_extract_attributes_from_snap.assert_called_once_with(
            target_snap=snap_info
        )
        mock_is_snap_in_allow_list.assert_called_once_with(
            snap_info.get("name"))
        mock_is_snap_confinement_not_strict.assert_called_once_with(
            snap_info.get("confinement"))
        mock_is_snap_devmode.assert_called_once_with(
            snap_info.get("devmode"))
        mock_is_snap_sideloaded_revision.assert_called_once_with(
            snap_info.get("revision"))
        self.assertEqual(0, result)

    @patch("snap_confinement_test.SnapsConfinementVerifier._is_snap_sideloaded_revision")   # noqa E501
    @patch("snap_confinement_test.SnapsConfinementVerifier._is_snap_devmode")   # noqa E501
    @patch("snap_confinement_test.SnapsConfinementVerifier._is_snap_confinement_not_strict")   # noqa E501
    @patch("snap_confinement_test.SnapsConfinementVerifier._is_snap_in_allow_list")   # noqa E501
    @patch("snap_confinement_test.SnapsConfinementVerifier._extract_attributes_from_snap")   # noqa E501
    @patch("snap_confinement_test.Snapd.list")
    def test_verify_snap_fail_to_match_pass_criteria(
        self,
        mock_snapd_list,
        mock_extract_attributes_from_snap,
        mock_is_snap_in_allow_list,
        mock_is_snap_confinement_not_strict,
        mock_is_snap_devmode,
        mock_is_snap_sideloaded_revision,
    ):
        """
        Check verify_snap return 1 if a snap doesn't reach out the check
        criteria
        """
        snap_info = {
            "name": "foo-snap",
            "devmode": True,
            "confinement": "not-strict",
            "revision": "999"
        }
        mock_snapd_list.return_value = [snap_info]
        mock_extract_attributes_from_snap.return_value = (False, snap_info)
        mock_is_snap_in_allow_list.return_value = False
        mock_is_snap_confinement_not_strict.return_value = True
        mock_is_snap_devmode.return_value = True
        mock_is_snap_sideloaded_revision.return_value = False
        result = self.verifier.verify_snap()
        mock_extract_attributes_from_snap.assert_called_once_with(
            target_snap=snap_info
        )
        mock_is_snap_in_allow_list.assert_called_once_with(
            snap_info.get("name"))
        mock_is_snap_confinement_not_strict.assert_called_once_with(
            snap_info.get("confinement"))
        mock_is_snap_devmode.assert_called_once_with(
            snap_info.get("devmode"))
        mock_is_snap_sideloaded_revision.assert_called_once_with(
            snap_info.get("revision"))
        self.assertEqual(1, result)


class TestMainFunction(unittest.TestCase):
    @patch('snap_confinement_test.test_system_confinement')
    @patch('snap_confinement_test.SnapsConfinementVerifier.verify_snap')
    @patch('snap_confinement_test.argparse.ArgumentParser')
    def test_main_execute_snaps_command(
        self,
        mock_arg_parser,
        mock_verify_snap,
        mock_test_system_confinement
    ):
        mock_args = MagicMock(subcommand='snaps')
        mock_arg_parser.return_value.parse_args.return_value = mock_args
        result = main()
        mock_verify_snap.assert_called_once_with()
        mock_test_system_confinement.assert_not_called()
        self.assertEqual(result, mock_verify_snap.return_value)

    @patch('snap_confinement_test.test_system_confinement')
    @patch('snap_confinement_test.SnapsConfinementVerifier.verify_snap')
    @patch('snap_confinement_test.argparse.ArgumentParser')
    def test_main_execute_system_command(
        self,
        mock_arg_parser,
        mock_verify_snap,
        mock_test_system_confinement
    ):
        mock_args = MagicMock(subcommand='system')
        mock_arg_parser.return_value.parse_args.return_value = mock_args
        result = main()
        mock_test_system_confinement.assert_called_once_with()
        mock_verify_snap.assert_not_called()
        self.assertEqual(result, mock_test_system_confinement.return_value)


if __name__ == '__main__':
    unittest.main()
