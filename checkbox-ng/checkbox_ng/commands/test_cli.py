# This file is part of Checkbox.
#
# Copyright 2014 Canonical Ltd.
# Written by:
#   Sylvain Pineau <sylvain.pineau@canonical.com>
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
checkbox_ng.commands.test_cli
=============================

Test definitions for checkbox_ng.commands.cli module
"""

from unittest import TestCase

from plainbox.impl.job import JobDefinition
from plainbox.impl.secure.origin import JobOutputTextSource
from plainbox.impl.secure.origin import Origin
from plainbox.impl.secure.rfc822 import RFC822Record
from plainbox.impl.testing_utils import make_job

from checkbox_ng.commands.cli import SelectableJobTreeNode


class TestSelectableJobTreeNode(TestCase):

    def setUp(self):
        self.A = make_job('a', name='A')
        self.B = make_job('b', name='B', plugin='local', description='foo')
        self.C = make_job('c', name='C')
        self.D = self.B.create_child_job_from_record(
            RFC822Record(
                data={'id': 'd', 'name': 'D', 'plugin': 'shell'},
                origin=Origin(source=JobOutputTextSource(self.B),
                              line_start=1,
                              line_end=1)))
        self.E = self.B.create_child_job_from_record(
            RFC822Record(
                data={'id': 'e', 'name': 'E', 'plugin': 'shell'},
                origin=Origin(source=JobOutputTextSource(self.B),
                              line_start=1,
                              line_end=1)))
        self.F = make_job('f', name='F', plugin='resource', description='baz')
        self.tree = SelectableJobTreeNode.create_tree([
            self.A,
            self.B,
            self.C,
            self.D,
            self.E,
            self.F
        ], legacy_mode=True)

    def test_create_tree(self):
        self.assertIsInstance(self.tree, SelectableJobTreeNode)
        self.assertEqual(len(self.tree.categories), 1)
        [self.assertIsInstance(c, SelectableJobTreeNode)
            for c in self.tree.categories]
        self.assertEqual(len(self.tree.jobs), 2)
        [self.assertIsInstance(j, JobDefinition) for j in self.tree.jobs]
        self.assertTrue(self.tree.selected)
        [self.assertTrue(self.tree.job_selection[j])
            for j in self.tree.job_selection]
        self.assertTrue(self.tree.expanded)
        self.assertIsNone(self.tree.parent)
        self.assertEqual(self.tree.depth, 0)

    def test_get_node_by_index(self):
        self.assertEqual(self.tree.get_node_by_index(0)[0].name, 'foo')
        self.assertEqual(self.tree.get_node_by_index(1)[0].name, 'D')
        self.assertEqual(self.tree.get_node_by_index(2)[0].name, 'E')
        self.assertEqual(self.tree.get_node_by_index(3)[0].name, 'A')
        self.assertEqual(self.tree.get_node_by_index(4)[0].name, 'C')
        self.assertIsNone(self.tree.get_node_by_index(5)[0])

    def test_render(self):
        expected = ['[X] - foo',
                    '[X]      d',
                    '[X]      e',
                    '[X]   a',
                    '[X]   c']
        self.assertEqual(self.tree.render(), expected)

    def test_render_deselected_all(self):
        self.tree.set_descendants_state(False)
        expected = ['[ ] - foo',
                    '[ ]      d',
                    '[ ]      e',
                    '[ ]   a',
                    '[ ]   c']
        self.assertEqual(self.tree.render(), expected)

    def test_render_reselected_all(self):
        self.tree.set_descendants_state(False)
        self.tree.set_descendants_state(True)
        expected = ['[X] - foo',
                    '[X]      d',
                    '[X]      e',
                    '[X]   a',
                    '[X]   c']
        self.assertEqual(self.tree.render(), expected)

    def test_render_with_child_collapsed(self):
        self.tree.categories[0].expanded = False
        expected = ['[X] + foo',
                    '[X]   a',
                    '[X]   c']
        self.assertEqual(self.tree.render(), expected)

    def test_set_ancestors_state(self):
        self.tree.set_descendants_state(False)
        node = self.tree.categories[0]
        node.job_selection[self.E] = True
        node.update_selected_state()
        node.set_ancestors_state(node.selected)
        expected = ['[X] - foo',
                    '[ ]      d',
                    '[X]      e',
                    '[ ]   a',
                    '[ ]   c']
        self.assertEqual(self.tree.render(), expected)
        node.selected = not(node.selected)
        node.set_ancestors_state(node.selected)
        node.set_descendants_state(node.selected)
        expected = ['[ ] - foo',
                    '[ ]      d',
                    '[ ]      e',
                    '[ ]   a',
                    '[ ]   c']
        self.assertEqual(self.tree.render(), expected)

    def test_selection(self):
        self.tree.set_descendants_state(False)
        node = self.tree.categories[0]
        node.job_selection[self.D] = True
        node.update_selected_state()
        node.set_ancestors_state(node.selected)
        # Note that in addition to the selected (D) test, we need the
        # tree selection to contain the resource (F), even though the
        # user never saw it in the previous tests for visual presentation.
        self.assertEqual(self.tree.selection, [self.D, self.F])
