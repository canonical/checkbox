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


logger = getLogger("checkbox.ng.commands.cli")


class JobTreeNode:

    r"""
    JobTreeNode class is used to store a tree structure.

    A tree consists of a collection of JobTreeNode instances connected in a
    hierarchical way where nodes are used as categories, jobs belonging to a
    category are listed in the node leaves.

    Example::
               / Job A
         Root-|
              |                 / Job B
               \--- Category X |
                                \ Job C
    """

    def __init__(self, name=None):
        """ Initialize the job tree node with a given name. """
        self._name = name if name else 'Root'
        self._parent = None
        self._categories = []
        self._jobs = []

    @property
    def name(self):
        """ name of this node. """
        return self._name

    @property
    def parent(self):
        """ parent node for this node. """
        return self._parent

    @property
    def categories(self):
        """ list of sub categories. """
        return self._categories

    @property
    def jobs(self):
        """ job(s) belonging to this node/category. """
        return self._jobs

    @property
    def depth(self):
        """ level of depth for this node. """
        return (self._parent.depth + 1) if self._parent else 0

    def __str__(self):
        """ same as self.name. """
        return self.name

    def __repr__(self):
        """ Get a representation of this node for debugging. """
        return "<JobTreeNode name:{!r}>".format(self.name)

    def add_category(self, category):
        """
        Add a new category to this node.

        :param category:
            The node instance to be added as a category.
        """
        self._categories.append(category)
        # Always keep this list sorted to easily find a given child by index
        self._categories.sort(key=lambda item: item.name)
        category._parent = self

    def add_job(self, job):
        """
        Add a new job to this node.

        :param job:
            The job instance to be added to this node.
        """
        self._jobs.append(job)
        # Always keep this list sorted to easily find a given leaf by index
        # Note bisect.insort(a, x) cannot be used here as JobDefinition are
        # not sortable
        self._jobs.sort(key=lambda item: item.id)

    def get_ancestors(self):
        """ Get the list of ancestors from here to the root of the tree.  """
        ancestors = []
        node = self
        while node.parent is not None:
            ancestors.append(node.parent)
            node = node.parent
        return ancestors

    def get_descendants(self):
        """ Return a list of all descendant category nodes.  """
        descendants = []
        for category in self.categories:
            descendants.append(category)
            descendants.extend(category.get_descendants())
        return descendants

    @classmethod
    def create_tree(cls, session_state, job_list):
        """
        Build a rooted JobTreeNode from a job list.

        :argument session_state:
            A session state object
        :argument job_list:
            List of jobs to consider for building the tree.
        """
        builder = TreeBuilder(session_state, cls)
        for job in job_list:
            builder.auto_add_job(job)
        return builder.root_node

    @classmethod
    def create_simple_tree(cls, sa, job_list):
        """
        Build a rooted JobTreeNode from a job list.

        :argument sa:
            A session assistant object
        :argument job_list:
            List of jobs to consider for building the tree.
        """
        root_node = cls()
        for job in job_list:
            cat_name = sa.get_category(job.category_id).tr_name()
            matches = [n for n in root_node.categories if n.name == cat_name]
            if not matches:
                node = cls(cat_name)
                root_node.add_category(node)
            else:
                node = matches[0]
            node.add_job(job)
        return root_node


class TreeBuilder:

    """
    Builder for :class:`JobTreeNode`.


    Helper class that assists in building a tree of :class:`JobTreeNode`
    objects out of job definitions and their associations, as expressed by
    :attr:`JobState.via_job` associated with each job.

    The builder is a single-use object and should be re-created for each new
    construct. Internally it stores the job_state_map of the
    :class:`SessionState` it was created with as well as additional helper
    state.
    """

    def __init__(self, session_state: "SessionState", node_cls):
        self._job_state_map = session_state.job_state_map
        self._node_cls = node_cls
        self._root_node = node_cls()
        self._category_node_map = {}  # id -> node

    @property
    def root_node(self):
        return self._root_node

    def auto_add_job(self, job):
        """
        Add a job to the tree, automatically creating category nodes as needed.

        :param job:
            The job definition to add.
        """
        if job.plugin == 'local':
            # For local jobs, just create the category node but don't add the
            # local job itself there.
            self.get_or_create_category_node(job)
        else:
            # For all other jobs, look at the parent job (if any) and create
            # the category node out of that node. This never fails as "None" is
            # the root_node object.
            state = self._job_state_map[job.id]
            node = self.get_or_create_category_node(state.via_job)
            # Then add that job to the category node
            node.add_job(job)

    def get_or_create_category_node(self, category_job):
        """
        Get a category node for a given job.

        Get or create a :class:`JobTreeNode` that corresponds to the
        category defined (somehow) by the job ``category_job``.

        :param category_job:
            The job that describes the category. This is either a
            plugin="local" job or a plugin="resource" job. This can also be
            None, which is a shorthand to say "root node".
        :returns:
            The ``root_node`` if ``category_job`` is None. A freshly
            created node, created with :func:`create_category_node()` if
            the category_job was never seen before (as recorded by the
            category_node_map).
        """
        logger.debug("get_or_create_category_node(%r)", category_job)
        if category_job is None:
            return self._root_node
        if category_job.id not in self._category_node_map:
            category_node = self.create_category_node(category_job)
            # The category is added to its parent, that's either the root
            # (if we're standalone) or the non-root category this one
            # belongs to.
            category_state = self._job_state_map[category_job.id]
            if category_state.via_job is not None:
                parent_category_node = self.get_or_create_category_node(
                    category_state.via_job)
            else:
                parent_category_node = self._root_node
            parent_category_node.add_category(category_node)
        else:
            category_node = self._category_node_map[category_job.id]
        return category_node

    def create_category_node(self, category_job):
        """
        Create a category node for a given job.

        Create a :class:`JobTreeNode` that corresponds to the category defined
        (somehow) by the job ``category_job``.

        :param category_job:
            The job that describes the node to create.
        :returns:
            A fresh node with appropriate data.
        """
        logger.debug("create_category_node(%r)", category_job)
        if category_job.summary == category_job.partial_id:
            category_node = self._node_cls(category_job.description)
        else:
            category_node = self._node_cls(category_job.summary)
        self._category_node_map[category_job.id] = category_node
        return category_node


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
                title = job.tr_summary()
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
        return self._selection_list

    @property
    def resource_jobs(self):
        """Return all the resource jobs."""
        return self._resource_jobs

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
