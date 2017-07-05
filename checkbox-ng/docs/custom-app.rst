.. _custom-apps:

Creating a custom Checkbox application for Ubuntu Core testing
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

This guide describes how to create a custom Checkbox application for testing a
new project (project meaning a new system that we want to test with Checkbox).

Initialize the project
======================

Creating your working directory and initializing the projects.  Make sure you
have at least snapcraft version 2.13 (available in Ubuntu 16.04 or newer).::

    mkdir checkbox-myproject
    cd checkbox-myproject
    snapcraft init
    git init

You will now have a ``snapcraft.yaml`` file in the ``snap`` directory.
Modify it and  insert your title, description, version.

.. code-block:: yaml
    :caption: snap/snapcraft.yaml
    :name: snapcraft.yaml-basic

    name: checkbox-myproject
    version: 1
    summary: Checkbox tool for MyProject
    description: Checkbox tool for MyProject
    grade: devel
    confinement: strict

Adding parts
============

Add the basic reusable snappy provider parts.

.. code-block:: yaml
    :caption: snap/snapcraft.yaml
    :name: snapcraft.yaml-with-parts

    (...)
    parts:
        plainbox-provider-snappy:
            after: [plainbox-provider-snappy-resource]
        plainbox-provider-snappy-resource:
            after: [plainbox-dev, checkbox-support-dev, checkbox-ng-dev]

        network-tools:
            plugin: nil
            stage-packages:
                - network-manager
                - modemmanager
                - hostapd
                - iw
            snap:
                - usr/bin/mmcli
                - usr/lib/*/libmm-glib.so*
                - usr/bin/nmcli
                - usr/lib/*/libnm*
                - usr/sbin/hostapd
                - sbin/iw


Create a device/project specific provider
=========================================

.. code-block:: bash

    $ plainbox startprovider --empty com.canonical.qa.myproject:
    plainbox-provider-myproject

The directory name for the provider is quite a mouthful, let's change it to
something more manageable.

.. code-block:: bash

    $ mv com.canonical.qa.myproject:plainbox-provider-myproject
    plainbox-provider-myproject

This new provider has to also be included as a part of the snap

.. code-block:: yaml

    :caption: snap/snapcraft.yaml
    :name: snapcraft.yaml-with-custom-provider

    (...)
    parts:
        plainbox-provider-myproject:
            plugin: plainbox-provider
            source: ./plainbox-provider-myproject
            after: [plainbox-provider-snappy]


Create your new test plans (and jobs to go in them)
===================================================

Edit the plainbox-provider-myproject provider by adding jobs and particularly
test plans that list all the jobs that you want to run.

By convention units reside in .pxu files in the ``units`` directory of the
provider. Let's create one

.. code-block:: bash

    $ cd plainbox-provider-myproject
    $ mkdir units

Let's add a job from :ref:`tutorials`

.. code-block:: none
    :caption: units/jobs.pxu

    id: my-first-job
    _summary: 10GB available in $HOME
    _description:
        this test checks if there's at least 10gb of free space in user's home
            directory
    plugin: shell
    estimated_duration: 0.01
    command: [ `df -B 1G --output=avail $HOME |tail -n1` -gt 10 ]

You may read more on how to write jobs here: :ref:`job`

It is a good practice to group jobs in test plans, here's one that will include
the ``my-first-job``

.. code-block:: none
    :caption: unit/test-plan.pxu
    :name: test-plan.pxu-basic

    unit: test plan
    id: my-project-custom
    _name: MyProject tests
    _description:
        This test plan includes all test related to MyProject
    include:
        my-first-job

You may read more on test plans here: :ref:`test-plan`

Reusing existing provider(s)
============================

It's best not to duplicate stuff, so if the test you want to run already exists
in another provider it is best to include that provider in the snap, and
include the test, or whole test plans from that provider in your new testing
project.

Let's reuse disk tests from the "plainbox-provider-snappy" provider that we
already have as a part of the snap. All we need is a test plan that will
include both reused disk tests and the new custom ones.

.. code-block:: none
    :caption: unit/test-plan.pxu
    :name: test-plan.pxu-with-external
    :emphasize-lines: 6-9

    id: my-project-all-tests
    _name: All MyProject tests
    _description:
        This test plan includes some disk tests from plainbox-provider-snappy
        and the my-first-job test.
    include:
        com.canonical.certification::disk/detect
        com.canonical.certification::disk/stats_.*
        my-first-job

You can also include the whole *external* test plan. Let's reuse the CPU
testing suite from plainbox-provider-snappy.

.. code-block:: none
    :caption: unit/test-plan.pxu
    :name: test-plan.pxu-with-nested
    :emphasize-lines: 10-11

    unit: test plan
    id: my-project-all-tests
    _name: All MyProject tests
    _description:
        This test plan includes some disk tests from plainbox-provider-snappy
        and the my-first-job test.
    include:
        com.canonical.certification::disk/detect
        com.canonical.certification::disk/stats_.*
        my-first-job
    nested_part:
        com.canonical.certification::cpu-full

Create Checkbox Launchers configurations
========================================

Launchers help to predefine how Checkbox should run. Read more here:
:ref:`launcher-tutorial`

First, let's leave the provider directory and go back to the
``checkbox-myproject``.

.. code-block:: bash

    $ cd ..

and write the first launcher

.. code-block:: none
    :caption: launchers/myproject-test-runner

    #!/usr/bin/env checkbox-cli-wrapper
    [launcher]
    app_id = com.canonical.qa.myproject:checkbox
    launcher_version = 1
    stock_reports = text, submission_files

    [test plan]
    filter = *myproject*, *tpm-smoke-tests

Create wrapper scripts
======================

We currently need wrapper scripts to discover providers, set up the execution
environment and work around a few other snappy issues. Add one like this:

.. code-block:: bash
    :caption: launchers/checkbox-cli-wrapper:

    #!/bin/bash

    export PATH="$PATH:$SNAP/usr/sbin"
    exec python3 $(which checkbox-cli) "$@"

Now we need to make the launchers executable

.. code-block:: bash

    chmod +x launchers/*


.. code-block:: yaml
    :caption: snap/snapcraft.yaml
    :name: snapcraft.yaml-with-launchers

    (...)
    launchers:
        plugin: dump
        source: launchers/
        organize:
            '*': bin/

Declare the launchers to be Apps that exist in your Snap
========================================================

.. code-block:: yaml
    :caption: snap/snapcraft.yaml
    :name: snapcraft.yaml-with-apps

    (...)
    apps:
        myproject-test-runner:
            command: bin/myproject-test-runner

What's left is to snap it all together!

.. code-block:: bash

    $ snapcraft
