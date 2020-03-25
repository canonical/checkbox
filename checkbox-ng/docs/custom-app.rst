.. _custom-apps:

Creating a custom Checkbox application for Ubuntu Core testing
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

This guide describes how to create a custom Checkbox application for testing a
new project (project meaning a new system that we want to test with Checkbox).

Preparing a new Checkbox Project snap
=====================================

Checkbox-Configure is a tool that generates a snap skeleton for a project.
It uses autoconf, so make sure you've got it installed.

.. code-block:: bash

    $ sudo apt install autoconf

Getting the tool.

.. code-block:: bash

    $ git clone https://git.launchpad.net/~checkbox-dev/checkbox/+git/checkbox-configure
    $ cd checkbox-configure
    $ autoconf

Let's create a Checkbox Snap for project called "myproject".

.. code-block:: bash

    $ ./configure --with-provider-included project=myproject base=18 && ./cleanup.sh

This creates all the files necessary to use Snapcraft to build the
new snap.

The skeleton comes with some units defined, but you need to add the
project-specific ones.


Adding new test jobs
====================

Edit the checkbox-provider-myproject provider by adding jobs and particularly
test plans that list all the jobs that you want to run.

By convention units reside in .pxu files in the ``units`` directory of the
provider.

.. code-block:: bash

    $ cd checkbox-provider-myproject

Let's add a job from :ref:`tutorials`

.. code-block:: none
    :caption: units/jobs.pxu

    id: my-first-job
    _summary: Is 10GB available in $HOME
    _description:
        this test checks if there's at least 10gb of free space in user's home
            directory
    plugin: shell
    estimated_duration: 0.01
    command: [ `df -B 1G --output=avail $HOME |tail -n1` -gt 10 ]

You may read more on how to write jobs here: :ref:`job`

Reusing existing provider(s)
============================

It's best not to duplicate stuff, so if the test you want to run already exists
in another provider it is best to reference that provider in the snap, and
include the test, or whole test plans from that provider in your new testing
project.

Let's reuse disk tests from the "plainbox-provider-snappy" provider that we
can use from the checkbox generic snap. All we need to do is add chosen tests
to the ``include`` field of the test plan.

.. code-block:: none
    :caption: units/test-plan.pxu
    :name: test-plan.pxu-with-external
    :emphasize-lines: 7-9

    id: myproject-automated
    unit: test plan
    _name: Automated only QA tests for myproject
    _description:
    QA test plan for the myproject hardware. This test plan contains
    all of the automated tests used to validate the aproject device.
    include:
	com.canonical.certification::disk/encryption/detect
	com.canonical.certification::miscellanea/secure_boot_mode_.*
    (...)

You can also include the whole *external* test plan. Let's reuse the CPU
testing suite from plainbox-provider-snappy.

.. code-block:: none
    :caption: unit/test-plan.pxu
    :name: test-plan.pxu-with-nested
    :emphasize-lines: 14

    nested_part:
	device-connections-tp
	2016.com.intel.ipdt::ipdt-plan
	com.canonical.certification::usb-automated
	# com.canonical.certification::audio-automated # no working auto tests
	com.canonical.certification::cpu-automated
	com.canonical.certification::disk-automated
	com.canonical.certification::ethernet-automated
	com.canonical.certification::kernel-snap-automated
	com.canonical.certification::memory-automated
	com.canonical.certification::networking-automated
	com.canonical.certification::rtc-automated
	com.canonical.certification::snappy-snap-automated
	com.canonical.certification::cpu-full


Snapping the new checkbox-myproject snap
========================================


What's left is to snap it all together!

.. code-block:: bash

    $ snapcraft
