import io
import unittest
from unittest.mock import patch

import compare_manifests


class CompareManifests(unittest.TestCase):
    def test_diff_manifests_different(self):
        m1 = [
            "com.canonical.certification::_hidden",
            "com.canonical.certification::normal",
        ]
        m2 = [
            "com.canonical.certification::_hidden",
            "com.canonical.certification::normal",
            "com.canonical.certification::_hidden_new",
        ]
        result = compare_manifests.diff_manifests(m1, m2)
        self.assertEqual(result, ["com.canonical.certification::_hidden_new"])

    def test_diff_manifests_similar(self):
        m1 = [
            "com.canonical.certification::_hidden",
            "com.canonical.certification::normal",
        ]
        m2 = [
            "com.canonical.certification::_hidden",
            "com.canonical.certification::normal",
        ]
        result = compare_manifests.diff_manifests(m1, m2)
        self.assertEqual(result, [])
