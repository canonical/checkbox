=================
Provider Template
=================

PlainBox comes with a built-in template for a new provider. You can use it to
quickly start working on your own collection of tests.

This is not the :doc:`tutorial`, mind you, this is the actual template. It is
here though as a additional learning resource. To create this template locally,
for easier editing / experiments, just run::
    
    plainbox startprovider 2013.com.example:template

Provider Template Layout
========================

The following files and directories are generated::

    2013.com.example:template/
    ├── bin
    │   ├── custom-executable
    │   └── README.md
    ├── data
    │   ├── example.dat
    │   └── README.md
    ├── jobs
    │   ├── examples-intermediate.txt
    │   ├── examples-normal.txt
    │   └── examples-trivial.txt
    ├── manage.py
    ├── po
    │   └── POTFILES.in
    ├── README.md
    └── whitelists
        ├── normal.whitelist
        └── trivial.whitelist

Generated Content
=================

README.md
---------

::

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

manage.py
---------

::

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
        name='2013.com.example:template',
        version="1.0",
        description=N_("The 2013.com.example:template provider"),
        gettext_domain="2013_com_example_template",
    )

bin/README.md
-------------

::

    Container for arbitrary executables needed by tests
    ===================================================

    You can execute files from this directory without any additional
    setup, they are automatically added to the PATH of the executing
    job examples/bin-access for details.

    You should delete this file as anything here is automatically
    distributed in the source tarball or installed.

bin/custom-executable
---------------------

::

    #!/bin/sh
    echo "Custom script executed"

data/README.md
--------------

::

    Container for arbitrary data needed by tests
    ============================================

    You can refer to files from this directory, in your scripts, using
    the $PLAINBOX\_PROVIDER\_DATA environment variable. See the job
    examples/data-access for details.

    You should delete this file as anything here is automatically
    distributed in the source tarball or installed.

data/example.dat
----------------

::

    DATA

examples-trivial.txt
--------------------

::

    # Two example jobs, both using the 'shell' "plugin". See the
    # documentation for examples of other test cases including
    # interactive tests, "resource" tests and a few other types.
    #
    # The summary and description keys are prefixed with _
    # to indicate that they can be translated.
    #
    # http://plainbox.rtfd.org/en/latest/author/jobs.html
    id: examples/trivial/always-pass
    _summary: A test that always passes
    _description:
       A test that always passes
       .
       This simple test will always succeed, assuming your
       platform has a 'true' command that returns 0.
    plugin: shell
    estimated_duration: 0.01
    command: true

    id: examples/trivial/always-fail
    _summary: A test that always fails
    _description:
       A test that always fails
       .
       This simple test will always fail, assuming your
       platform has a 'false' command that returns 1.
    plugin: shell
    estimated_duration: 0.01
    command: false

jobs/examples-normal.txt
------------------------

::

    id: examples/normal/data-access
    _summary: Example job using provider-specific data
    _description:
       This test illustrates that custom data can be accessed using
       the $PLAINBOX_PROVIDER_DATA environment variable. It points to
       the absolute path of the data directory of the provider.
    plugin: shell
    estimated_duration: 0.01
    command:
       test "$(cat $PLAINBOX_PROVIDER_DATA/example.dat)" = "DATA"

    id: examples/normal/bin-access
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

    id: examples/normal/info-collection
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

jobs/examples-intermediate.txt
------------------------------

::

    id: examples/intermediate/dependency-target
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

    id: examples/intermediate/dependency-source
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
    id: detected_device
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

    id: examples/intermediate/test-webcam
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


po/PORFILES.in
--------------

::

    [encoding: UTF-8]
    [type: gettext/rfc822deb] jobs/examples-trivial.txt
    [type: gettext/rfc822deb] jobs/examples-normal.txt
    [type: gettext/rfc822deb] jobs/examples-intermediate.txt
    manage.py

whitelists/trivial.whitelist
----------------------------

::

    # select two trivial jobs by directly selecting their names
    examples/trivial/always-pass
    examples/trivial/always-fail

whitelists/normal.whitelist
---------------------------

::

    # use regular expression to select all normal jobs
    examples/normal/.*
