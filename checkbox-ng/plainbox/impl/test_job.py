# This file is part of Checkbox.
#
# Copyright 2012 Canonical Ltd.
# Written by:
#   Zygmunt Krynicki <zygmunt.krynicki@canonical.com>
#
# Checkbox is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3,
# as published by the Free Software Foundation.

#
# Checkbox is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Checkbox.  If not, see <http://www.gnu.org/licenses/>.

"""
plainbox.impl.test_job
======================

Test definitions for plainbox.impl.job module
"""

from unittest import TestCase, expectedFailure

from plainbox.impl.job import JobTreeNode
from plainbox.impl.secure.origin import JobOutputTextSource
from plainbox.impl.secure.origin import Origin
from plainbox.impl.secure.rfc822 import RFC822Record
from plainbox.impl.testing_utils import make_job
from plainbox.impl.unit.job import JobDefinition


class TestJobTreeNode_legacy(TestCase):

    def setUp(self):
        A = make_job('A')
        B = make_job('B', plugin='local', description='foo')
        C = make_job('C')
        D = B.create_child_job_from_record(
            RFC822Record(
                data={'id': 'D', 'plugin': 'shell'},
                origin=Origin(source=JobOutputTextSource(B),
                              line_start=1,
                              line_end=1)))
        E = B.create_child_job_from_record(
            RFC822Record(
                data={'id': 'E', 'plugin': 'local', 'description': 'bar'},
                origin=Origin(source=JobOutputTextSource(B),
                              line_start=1,
                              line_end=1)))
        F = E.create_child_job_from_record(
            RFC822Record(
                data={'id': 'F', 'plugin': 'shell'},
                origin=Origin(source=JobOutputTextSource(E),
                              line_start=1,
                              line_end=1)))
        G = make_job('G', plugin='local', description='baz')
        R = make_job('R', plugin='resource')
        Z = make_job('Z', plugin='local', description='zaz')

        self.tree = JobTreeNode.create_tree([R, B, C, D, E, F, G, A, Z],
                                            legacy_mode=True)

    def test_create_tree(self):
        self.assertIsInstance(self.tree, JobTreeNode)
        self.assertEqual(len(self.tree.categories), 3)
        [self.assertIsInstance(c, JobTreeNode) for c in self.tree.categories]
        self.assertEqual(len(self.tree.jobs), 3)
        [self.assertIsInstance(j, JobDefinition) for j in self.tree.jobs]
        self.assertIsNone(self.tree.parent)
        self.assertEqual(self.tree.depth, 0)
        node = self.tree.categories[1]
        self.assertEqual(node.name, 'foo')
        self.assertEqual(len(node.categories), 1)
        [self.assertIsInstance(c, JobTreeNode) for c in node.categories]
        self.assertEqual(len(node.jobs), 1)
        [self.assertIsInstance(j, JobDefinition) for j in node.jobs]


class TestNewJoB:
    """
    Simple Job definition to demonstrate the categories property and how it
    could be used to create a JobTreeNode
    """
    def __init__(self, name, categories={}):
        self.name = name
        self.categories = categories


class TestJobTreeNodeExperimental(TestCase):

    def brokenSetUp(self):
        A = TestNewJoB('A', {'Audio'})
        B = TestNewJoB('B', {'Audio', 'USB'})
        C = TestNewJoB('C', {'USB'})
        D = TestNewJoB('D', {'Wireless'})
        E = TestNewJoB('E', {})
        F = TestNewJoB('F', {'Wireless'})

        # Populate the tree with a existing hierarchy as plainbox does not
        # provide yet a way to build such categorization
        root = JobTreeNode()
        MM = JobTreeNode('Multimedia')
        Audio = JobTreeNode('Audio')
        root.add_category(MM)
        MM.add_category(Audio)
        self.tree = JobTreeNode.create_tree([A, B, C, D, E, F], root, link='')

    # This test fails is not using job definitions where it assumes jobs are
    # being handled and now it crashes inside JobTreeNode.add_job() which
    # receives a non-job object.
    @expectedFailure
    def test_create_tree(self):
        self.brokenSetUp()
        self.assertIsInstance(self.tree, JobTreeNode)
        self.assertEqual(len(self.tree.categories), 3)
        [self.assertIsInstance(c, JobTreeNode) for c in self.tree.categories]
        self.assertEqual(len(self.tree.jobs), 1)
        [self.assertIsInstance(j, TestNewJoB) for j in self.tree.jobs]
        self.assertIsNone(self.tree.parent)
        self.assertEqual(self.tree.depth, 0)
        node = self.tree.categories[0]
        self.assertEqual(node.name, 'Multimedia')
        self.assertEqual(len(node.categories), 1)
        [self.assertIsInstance(c, JobTreeNode) for c in node.categories]
        self.assertEqual(len(node.jobs), 0)
        node = node.categories[0]
        self.assertEqual(node.name, 'Audio')
        self.assertEqual(len(node.categories), 0)
        self.assertEqual(len(node.jobs), 2)
        self.assertIn('B', [job.name for job in node.jobs])
        [self.assertIsInstance(j, TestNewJoB) for j in node.jobs]
        node = self.tree.categories[1]
        self.assertEqual(node.name, 'USB')
        self.assertIn('B', [job.name for job in node.jobs])
        node = self.tree.categories[2]
        self.assertEqual(node.name, 'Wireless')
        self.assertEqual(len(node.categories), 0)
        self.assertEqual(len(node.jobs), 2)
        [self.assertIsInstance(j, TestNewJoB) for j in node.jobs]
