# This file is part of Checkbox.
#
# Copyright 2013-2014 Canonical Ltd.
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
:mod:`checkbox_ng.misc` -- Other stuff
======================================

.. warning::

    THIS MODULE DOES NOT HAVE STABLE PUBLIC API
"""

from logging import getLogger

from plainbox.impl.job import JobTreeNode


logger = getLogger("checkbox.ng.commands.cli")


class SelectableJobTreeNode(JobTreeNode):
    """
    Implementation of a node in a tree that can be selected/deselected
    """
    def __init__(self, job=None):
        super().__init__(job)
        self.selected = True
        self.job_selection = {}
        self.expanded = True
        self.current_index = 0
        self._resource_jobs = []

    def get_node_by_index(self, index, tree=None):
        """
        Return the node found at the position given by index considering the
        tree from a top-down list view.
        """
        if tree is None:
            tree = self
        if self.expanded:
            for category in self.categories:
                if index == tree.current_index:
                    tree.current_index = 0
                    return (category, None)
                else:
                    tree.current_index += 1
                result = category.get_node_by_index(index, tree)
                if result != (None, None):
                    return result
            for job in self.jobs:
                if index == tree.current_index:
                    tree.current_index = 0
                    return (job, self)
                else:
                    tree.current_index += 1
        return (None, None)

    def render(self, cols=80):
        """
        Return the tree as a simple list of categories and jobs suitable for
        display. Jobs are properly indented to respect the tree hierarchy
        and selection marks are added automatically at the beginning of each
        element.

        The node titles should not exceed the width of a the terminal and
        thus are cut to fit inside.
        """
        self._flat_list = []
        if self.expanded:
            for category in self.categories:
                prefix = '[ ]'
                if category.selected:
                    prefix = '[X]'
                line = ''
                title = category.name
                if category.jobs or category.categories:
                    if category.expanded:
                        line = prefix + self.depth * '   ' + ' - ' + title
                    else:
                        line = prefix + self.depth * '   ' + ' + ' + title
                else:
                    line = prefix + self.depth * '   ' + '   ' + title
                if len(line) > cols:
                    col_max = cols - 4  # includes len('...') + a space
                    line = line[:col_max] + '...'
                self._flat_list.append(line)
                self._flat_list.extend(category.render(cols))
            for job in self.jobs:
                prefix = '[ ]'
                if self.job_selection[job]:
                    prefix = '[X]'
                title = job.summary
                line = prefix + self.depth * '   ' + '   ' + title
                if len(line) > cols:
                    col_max = cols - 4  # includes len('...') + a space
                    line = line[:col_max] + '...'
                self._flat_list.append(line)
        return self._flat_list

    def add_job(self, job):
        if job.plugin == 'resource':
            # I don't want the user to see resources but I need to keep
            # track of them to put them in the final selection. I also
            # don't want to add them to the tree.
            self._resource_jobs.append(job)
            return
        super().add_job(job)
        self.job_selection[job] = True

    @property
    def selection(self):
        """
        Return all the jobs currently selected
        """
        self._selection_list = []
        for category in self.categories:
            self._selection_list.extend(category.selection)
        for job in self.job_selection:
            if self.job_selection[job]:
                self._selection_list.append(job)
        # Don't forget to append the collected resource jobs to the final
        # selection
        self._selection_list.extend(self._resource_jobs)
        return self._selection_list

    def set_ancestors_state(self, new_state):
        """
        Set the selection state of all ancestors consistently
        """
        # If child is set, then all ancestors must be set
        if new_state:
            parent = self.parent
            while parent:
                parent.selected = new_state
                parent = parent.parent
        # If child is not set, then all ancestors mustn't be set
        # unless another child of the ancestor is set
        else:
            parent = self.parent
            while parent:
                if any((category.selected
                        for category in parent.categories)):
                    break
                if any((parent.job_selection[job]
                        for job in parent.job_selection)):
                    break
                parent.selected = new_state
                parent = parent.parent

    def update_selected_state(self):
        """
        Update the category state according to its job selection
        """
        if any((self.job_selection[job] for job in self.job_selection)):
            self.selected = True
        else:
            self.selected = False

    def set_descendants_state(self, new_state):
        """
        Set the selection state of all descendants recursively
        """
        self.selected = new_state
        for job in self.job_selection:
            self.job_selection[job] = new_state
        for category in self.categories:
            category.set_descendants_state(new_state)
