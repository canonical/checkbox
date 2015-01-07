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

from unittest import TestCase

from plainbox.impl.job import JobTreeNode
from plainbox.impl.session import SessionState
from plainbox.impl.testing_utils import make_job
from plainbox.impl.unit.job import JobDefinition


class TestJobTreeNode(TestCase):

    def setUp(self):
        A = make_job('A')
        B = make_job('B', plugin='local', description='foo')
        C = make_job('C')
        D = make_job('D', plugin='shell')
        E = make_job('E', plugin='local', description='bar')
        F = make_job('F', plugin='shell')
        G = make_job('G', plugin='local', description='baz')
        R = make_job('R', plugin='resource')
        Z = make_job('Z', plugin='local', description='zaz')
        state = SessionState([A, B, C, D, E, F, G, R, Z])
        # D and E are a child of B
        state.job_state_map[D.id].via_job = B
        state.job_state_map[E.id].via_job = B
        # F is a child of E
        state.job_state_map[F.id].via_job = E
        self.tree = JobTreeNode.create_tree(
            state, [R, B, C, D, E, F, G, A, Z])

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
