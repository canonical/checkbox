# This file is part of Checkbox.
#
# Copyright 2012, 2013 Canonical Ltd.
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
:mod:`plainbox.impl.job` -- job definition
==========================================

.. warning::

    THIS MODULE DOES NOT HAVE STABLE PUBLIC API
"""

import logging

from plainbox.impl.unit.job import JobDefinition

__all__ = ['JobDefinition', 'JobTreeNode']

logger = logging.getLogger("plainbox.job")


class JobTreeNode:
    """
    JobTreeNode class is used to store a tree structure. A tree consists of
    a collection of JobTreeNode instances connected in a hierarchical way
    where nodes are used as categories, jobs belonging to a category are
    listed in the node leaves.

    **Example:**

    ::

            / Job A
      Root-|
           |                 / Job B
            \--- Category X |
                             \ Job C

    """
    def __init__(self, name=None):
        self._name = name if name else 'Root'
        self._parent = None
        self._categories = []
        self._jobs = []

    @property
    def name(self):
        """
        node name
        """
        return self._name

    @property
    def parent(self):
        """
        parent node for this node
        """
        return self._parent

    @property
    def categories(self):
        """
        list of sub categories
        """
        return self._categories

    @property
    def jobs(self):
        """
        job(s) belonging to this node/category
        """
        return self._jobs

    @property
    def depth(self):
        """
        level of depth for this node
        """
        return (self._parent.depth + 1) if self._parent else 0

    def __str__(self):
        return self.name

    def __repr__(self):
        return "<JobTreeNode name:{!r}>".format(self.name)

    def add_category(self, category):
        """
        Adds a new category to this node.

        :argument category: the node instance to be added as a category.
        """
        self._categories.append(category)
        # Always keep this list sorted to easily find a given child by index
        self._categories = sorted(self._categories, key=lambda cat: cat.name)
        category._parent = self

    def add_job(self, job):
        """
        Adds a new job to this node.

        :argument job: the job instance to be added to this node.
        """
        self._jobs.append(job)
        # Always keep this list sorted to easily find a given leaf by index
        # Note bisect.insort(a, x) cannot be used here as JobDefinition are
        # not sortable
        self._jobs = sorted(self.jobs, key=lambda job: job.id)

    def get_ancestors(self):
        """
        Returns the list of all ancestor nodes from current node to the
        current tree root.
        """
        ancestors = []
        node = self
        while node.parent is not None:
            ancestors.append(node.parent)
            node = node.parent
        return ancestors

    def get_descendants(self):
        """
        Returns a list of all descendant category nodes.
        """
        descendants = []
        for category in self.categories:
            descendants.append(category)
            descendants.extend(category.get_descendants())
        return descendants

    @classmethod
    def create_tree(cls, job_list, node=None, link=None, legacy_mode=False):
        """
        Build a rooted JobTreeNode from a job list

        :argument job_list:
            List of jobs to consider for building the tree.
        :argument None node:
            Parent node to start with.
        :argument None link:
            Parent-child link used to create the descendants.
        :argument False legacy_mode:
            Whether local jobs are used to build the tree or a new experimental
            job metadata (categories).
        """
        if node is None:
            node = cls()
        if legacy_mode:  # using local jobs
            for job in [j for j in job_list if j.via == link]:
                if job.plugin == 'local':
                    if job.summary == job.partial_id:
                        category = cls(job.description)
                    else:
                        category = cls(job.summary)
                    cls.create_tree(job_list, category, job.checksum,
                                    legacy_mode)
                    node.add_category(category)
                else:
                    node.add_job(job)
        else:  # EXPERIMENTAL: Using a new Job property, categories
            for job in job_list:
                if job.categories:
                    for category in job.categories:
                        for d in node.get_descendants():
                            if d.name == category:
                                d.add_job(job)
                                break
                        else:
                            category = cls(category)
                            category.add_job(job)
                            node.add_category(category)
                else:
                    node.add_job(job)
        return node
