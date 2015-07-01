# This file is part of Checkbox.
#
# Copyright 2012-2014 Canonical Ltd.
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
:mod:`plainbox.impl.commands.inv_startprovider` -- startprovider sub-command
============================================================================
"""
import inspect
import logging
import os
import re

from plainbox.i18n import gettext as _
from plainbox.impl.secure.providers.v1 import IQNValidator

logger = logging.getLogger("plainbox.commands.startprovider")


class IQN(str):
    """
    A string subclass that validates values with the IQNValidator
    """

    _validator = IQNValidator()

    def __new__(mcls, value):
        problem = mcls._validator(None, value)
        if problem:
            raise ValueError(problem)
        return super().__new__(mcls, value)


class SomethingInTheWay(Exception):
    """
    Exception raised if a file or directory that we were hoping to create
    already exists. To avoid overwriting data this exception is raised instead
    """

    def __init__(self, filename):
        self.filename = filename

    def __str__(self):
        return _("refusing to overwrite {!a}").format(self.filename)


class File:
    """
    A helper class to create files from a text template.

    The generated file can have some custom content interpolated with the
    python format syntax. All keyword arguments passed to :meth:`instantiate()`
    are used as formatting variables.

    The generated file can be placed in a parent directory (just plain
    directory name), not the :class:`Directory` class. The name undergoes the
    same template expansion as the contents.

    The generated file can be marked as executable, if applicable for the given
    platform.
    """

    def __init__(self, name, parent=None, executable=False, full_text=""):
        self.name = name
        self.parent = parent
        self.executable = executable
        self.full_text = inspect.cleandoc(full_text)

    def instantiate(self, root, **kwargs):
        if self.parent:
            filename = os.path.join(
                root, self.parent, self.name.format(**kwargs))
        else:
            filename = os.path.join(root, self.name.format(**kwargs))
        if os.path.exists(filename):
            raise SomethingInTheWay(filename)
        with open(filename, "wt", encoding="UTF-8") as stream:
            content = self.full_text.format(**kwargs)
            stream.write(content)
        if self.executable:
            os.chmod(filename, 0o775)


class Directory:
    """
    A helper class to create a directory from a simple template.

    The generated directory can be placed in a parent directory (just plain
    directory name), not the :class:`Directory` class. The name undergoes the
    same template expansion as the contents.
    """

    def __init__(self, name):
        self.name = name

    def __enter__(self):
        return self.name

    def __exit__(self, *args):
        pass

    def instantiate(self, root, **kwargs):
        dirname = os.path.join(root, self.name.format(**kwargs))
        if os.path.exists(dirname):
            raise SomethingInTheWay(dirname)
        os.mkdir(dirname)


class Skeleton(Directory):
    """
    A helper class to create a directory with other files and directories.

    The class may define the ``things`` attribute (a list). All items of that
    list are instantiated, just like File and Directory can.
    """

    things = []

    def instantiate(self, root, **kwargs):
        super().instantiate(root, **kwargs)
        for thing in self.things:
            thing.instantiate(
                os.path.join(root, self.name.format(**kwargs)), **kwargs)


class ProviderSkeleton(Skeleton):
    """
    A skeleton with various content created for the startprovider command.
    """

    things = []

    units_dir = Directory("units")
    things.append(units_dir)

    whitelists_dir = Directory("whitelists")
    things.append(whitelists_dir)

    data_dir = Directory("data")
    things.append(data_dir)

    bin_dir = Directory("bin")
    things.append(bin_dir)

    po_dir = Directory("po")
    things.append(po_dir)

    things.append(File("README.md", full_text="""
         Skeleton for a new PlainBox provider
         ====================================

         This is a skeleton PlainBox provider that was generated using
         ``plainbox startprovider ...``.

         It is just the starting point, there is nothing here of value to you
         yet. If you know how this works then just remove this file along with
         other example content and start working on your new tests,
         otherwise, read on.

         Inside the ``jobs/`` directory you will find several files that define
         a number of "jobs" (more than one job per file actually). A job, in
         PlainBox parlance, is the smallest piece of executable test code. Each
         job has a name and a number of other attributes.

         Jobs can be arranged in lists, test plans if you will that are known
         as "whitelists". Those are defined in the ``whitelists/`` directory,
         this time one per file. You can create as many whitelists as you need,
         referring to arbitrary subsets of your jobs.

         Then there are the ``bin/`` and ``data/`` directories. Those are
         entirely for custom content you may need. You can put arbitrary
         executables in ``bin/``, and those will be available to your job
         definitions. Similarly you can keep any data your jobs might need
         inside the ``data/`` directory. Referring to that directory at runtime
         is a little bit trickier but one of the examples generated in this
         skeleton shows how to do that.

         Lastly there is the ``manage.py`` script. It requires python3 to run.
         It depends on the python3-plainbox Debian package (or just the
         PlainBox 0.5 upstream package) installed. This script can automate and
         simplify a number of tasks that you will want to do as a test
         developer.

         Run ``./manage.py --help`` to see what sub-commands are available. You
         can additionally pass ``--help`` to each sub command, for example
         ``./manage.py install --help`` will print the description of the
         install command and all the arguments it supports.

         That is it for now. You should check out the official documentation
         for test authors at
         http://plainbox.readthedocs.org/en/latest/author/index.html

         If you find bugs or would like to see additional features developed
         you can file bugs on the parent project page:
         https://bugs.launchpad.net/checkbox/+filebug
         """))

    with units_dir as parent:

        things.append(File("examples-trivial.pxu", parent, full_text="""
             # Two example jobs, both using the 'shell' "plugin". See the
             # documentation for examples of other test cases including
             # interactive tests, "resource" tests and a few other types.
             #
             # The summary and description keys are prefixed with _
             # to indicate that they can be translated.
             #
             # http://plainbox.rtfd.org/en/latest/author/jobs.html
             unit: category
             id: examples/trivial
             _name: Examples/trivial


             unit: job
             id: always-pass
             category_id: examples/trivial
             _summary: A test that always passes
             _description:
                A test that always passes
                .
                This simple test will always succeed, assuming your
                platform has a 'true' command that returns 0.
             plugin: shell
             estimated_duration: 0.01
             command: true

             unit: job
             id: always-fail
             category_id: examples/trivial
             _summary: A test that always fails
             _description:
                A test that always fails
                .
                This simple test will always fail, assuming your
                platform has a 'false' command that returns 1.
             plugin: shell
             estimated_duration: 0.01
             command: false
             """))

        things.append(File("examples-normal.pxu", parent, full_text="""
            unit: category
            id: examples/normal
            _name: Examples/normal

             unit: job
             id: data-access
             category_id: examples/normal
             _summary: Example job using provider-specific data
             _description:
                This test illustrates that custom data can be accessed using
                the $PLAINBOX_PROVIDER_DATA environment variable. It points to
                the absolute path of the data directory of the provider.
             plugin: shell
             estimated_duration: 0.01
             command:
                test "$(cat $PLAINBOX_PROVIDER_DATA/example.dat)" = "DATA"

             unit: job
             id: bin-access
             category_id: examples/normal
             _summary: Example job using provider-specific executable
             _description:
                This test illustrates that custom executables can be accessed
                directly, if placed in the bin/ directory of the provider.
                .
                Those are made available in the PATH, at runtime. This job
                succeeds because the custom-executable script returns 0.
             plugin: shell
             estimated_duration: 0.01
             command: custom-executable

             unit: job
             id: info-collection
             category_id: examples/normal
             _summary: Example job attaching command output to results
             _description:
                This test illustrates that output of a job may be collected
                for analysis using the plugin type ``attachment``
                .
                Attachment jobs may fail and behave almost the same as shell
                jobs (exit status decides their outcome)
                .
                The output is saved but, depending on how tests are how results
                are handled, may not be displayed. You can save attachments
                using, for example, the JSON test result exporter, like this:
                ``plainbox run -f json -p with-attachments``
             plugin: attachment
             estimated_duration: 0.01
             command: cat /proc/cpuinfo
             """))

        things.append(File("examples-intermediate.pxu", parent, full_text="""
            unit: category
            id: examples/intermediate
            _name: Examples/intermediate

             unit: job
             id: dependency-target
             category_id: examples/intermediate
             _summary: Example job that some other job depends on
             _description:
                This test illustrates how a job can be a dependency of another
                job. The dependency graph can be arbitrarily complex, it just
                cannot have any cycles. PlainBox will discover various problems
                related to dependencies, including cyclic dependencies and
                jobs that are depended upon, without a definition.
                .
                This job simply "passes" all the time but realistic examples
                may include multi-stage manipulation (detect a device, set it
                up, perform some automatic and some manual tests and summarise
                the results, for example)
             plugin: shell
             command: true
             estimated_duration: 0.01

             unit: job
             id: dependency-source
             category_id: examples/intermediate
             _summary: Example job that depends on another job
             _description:
                This test illustrates how a job can depend on another job.
                .
                If you run this example unmodified (selecting just this job)
                you will see that PlainBox will automatically run the
                'dependency-target' job before attempting to run this one.
                This will happen, even if you explicitly order the jobs
                incorrectly.
                .
                If you edit the 'dependency-target' job to run 'false' instead
                of 'true' and rerun this job you will see that it automatically
                fails without being started. This is because of a rule which
                automatically fails any job that has a failed dependency.
             plugin: shell
             command: true
             depends: examples/intermediate/dependency-target
             estimated_duration: 0.01

             # TODO: this should be possible:
             # name: examples/intermediate/detected-device
             # resource-object: examples.intermediate.detected_device
             unit: job
             id: detected_device
             category_id: examples/intermediate
             _summary: Example job producing structured resource data
             _description:
                This job illustrates that not all jobs are designed to be a
                "test". PlainBox has a system of the so-called resources.
                .
                Technically a resource is a list of records with named fields.
                Any program that prints RFC822-like output can be considered a
                valid resource. Here a hypothetical resource program has
                detected (fake) two devices which are represented as records
                with the field ``device``.
                .
                Resources are ran on demand, their output parsed and stored.
                All resources are made available to jobs that use resource
                programs. See the next job for an example of how that can be
                useful.
             plugin: resource
             command:
                echo "type: WEBCAM"
                echo ""
                echo "type: WIFI"
             estimated_duration: 0.03

             unit: job
             id: test-webcam
             category_id: examples/intermediate
             _summary: Example job depending on structured resource
             _description:
                This test illustrates two concepts. It is the first test that
                uses manual jobs (totally not automated test type). It also
                uses a resource dependency, via a resource program, to limit
                this test only on a machine that has a hypothetical webcam.
                .
                If you run this example unmodified (selecting just this job)
                you will see that PlainBox will automatically run the
                'detected_device' job before attempting to run this one. This
                will happen, even if you explicitly order the jobs incorrectly.
                .
                If you edit the resource job to not print information about the
                hypothetical WEBCAM device (just remove that line) and rerun
                this job you will see that it automatically gets skipped
                without being started. This is because of a rule which
                automatically skips any job that has unmet requirement.
                .
                Resources are documented in detail here:
                http://plainbox.rtfd.org/en/latest/search.html?q=resources
                Please look at the ``Resources`` chapter there (it may move so
                a search link is more reliable)
             plugin: manual
             requires:
                 detected_device.type == "WEBCAM"
             estimated_duration: 30
             """))

    with whitelists_dir as parent:

        things.append(File("trivial.whitelist", parent, full_text="""
             # select two trivial jobs by directly selecting their names
             examples/trivial/always-pass
             examples/trivial/always-fail
             """))

        things.append(File("normal.whitelist", parent, full_text="""
             # use regular expression to select all normal jobs
             examples/normal/.*
             """))

    with po_dir as parent:

        things.append(File("POTFILES.in", parent, full_text="""
            [encoding: UTF-8]
            [type: gettext/rfc822deb] jobs/examples-trivial.txt
            [type: gettext/rfc822deb] jobs/examples-normal.txt
            [type: gettext/rfc822deb] jobs/examples-intermediate.txt
            manage.py
        """))

    with data_dir as parent:

        things.append(File("README.md", parent, full_text="""
             Container for arbitrary data needed by tests
             ============================================

             You can refer to files from this directory, in your scripts, using
             the $PLAINBOX\\_PROVIDER\\_DATA environment variable. See the job
             examples/data-access for details.

             You should delete this file as anything here is automatically
             distributed in the source tarball or installed.
             """))

        things.append(File("example.dat", parent, full_text="DATA"))

    with bin_dir as parent:

        things.append(File("README.md", parent, full_text="""
             Container for arbitrary executables needed by tests
             ===================================================

             You can execute files from this directory without any additional
             setup, they are automatically added to the PATH of the executing
             job examples/bin-access for details.

             You should delete this file as anything here is automatically
             distributed in the source tarball or installed.
             """))

        things.append(File("custom-executable", parent, True, full_text="""
             #!/bin/sh
             echo "Custom script executed"
             """))

    things.append(File("manage.py", executable=True, full_text="""
        #!/usr/bin/env python3
        from plainbox.provider_manager import setup, N_

        # You can inject other stuff here but please don't go overboard.
        #
        # In particular, if you need comprehensive compilation support to get
        # your bin/ populated then please try to discuss that with us in the
        # upstream project IRC channel #checkbox on irc.freenode.net.

        # NOTE: one thing that you could do here, that makes a lot of sense,
        # is to compute version somehow. This may vary depending on the
        # context of your provider. Future version of PlainBox will offer git,
        # bzr and mercurial integration using the versiontools library
        # (optional)

        setup(
            name={name!r},
            version="1.0",
            description=N_("The {name} provider"),
            gettext_domain="{gettext_domain}",
        )
        """))

    things.append(File(".gitignore", full_text="dist/*.tar.gz\nbuild/mo/*\n"))

    things.append(File(".bzrignore", full_text="dist/*.tar.gz\nbuild/mo/*\n"))


class StartProviderInvocation:

    def __init__(self, name):
        self.name = name

    def run(self):
        try:
            ProviderSkeleton(self.name).instantiate(
                '.', name=self.name,
                gettext_domain=re.sub("[.:]", "_", self.name))
        except SomethingInTheWay as exc:
            raise SystemExit(exc)
