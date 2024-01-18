import logging
import unittest
from unittest.mock import patch
from snap_confinement_test import SnapsConfinementVerifier


class TestSnapsConfinementVerifier(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        logging.disable(logging.CRITICAL)

    @classmethod
    def tearDownClass(cls):
        logging.disable(logging.NOTSET)

    @patch("snap_confinement_test.logging")
    def test_extract_attributes_from_snap_success(self, mock_logging):
        verifier = SnapsConfinementVerifier()
        mock_snap = {
            "name": "test_snap", "confinement": "strict", "devmode": False,
            "revision": "123", "foo": "bar"}

        # Test when all desired attributes are present in the snap
        desired_attributes = ["name", "confinement", "devmode", "revision"]
        result = verifier._extract_attributes_from_snap(
            mock_snap, desired_attributes)

        self.assertEqual(result, mock_snap)
        mock_logging.assert_not_called()

    @patch("snap_confinement_test.logging")
    def test_extract_attributes_from_snap_missing_attribute(self, mock_logging):
        verifier = SnapsConfinementVerifier()
        mock_snap = {"name": "test_snap", "confinement": "strict"}

        # Test when some desired attributes are missing
        desired_attributes = ["name", "nonexistent_attr", "confinement"]
        result = verifier._extract_attributes_from_snap(
            mock_snap, desired_attributes)

        expected_result = {"name": "test_snap", "confinement": "strict"}
        self.assertEqual(result, expected_result)
        mock_logging.assert_called_once_with(
            "Snap 'nonexistent_attr' not found in the snap data."
        )


if __name__ == '__main__':
    unittest.main()
