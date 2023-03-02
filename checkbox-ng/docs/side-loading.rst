.. _side-loading:

Side-loading Providers
^^^^^^^^^^^^^^^^^^^^^^

If you want to create a new job, or tweak an existing one without a need
to repackage the provider or the snap, you can use side-loaded providers.

If the path ``/var/tmp/checkbox-providers`` exists, Checkbox will load
providers from that path. If any given provider has the same namespace and the
same name as an existing (installed or supplied with the same snap) provider,
only the side-loaded one will be used.

You may override as many providers as you find necessary. There's also no limit
on the number of new providers supplied with side-loading.

.. note::
    side-loading is a means to quickly iterate when developing new jobs.
    Don't use it *in production*. Also remember to empty (or delete) the
    `/var/tmp/checkbox-providers` directory once you're done developing, so you
    don't get nasty surprises down the line.
    Checkbox will not submit any reports to Certification website if
    side-loaded providers have been used.

Example scenario
================

Goal: change the runtime of the stress/cpu_stress_ng_test job without rebuilding
snap.

Make sure that checkbox snap is installed. It comes with following providers
available::

    checkbox-provider-base
    checkbox-provider-docker
    checkbox-provider-resource
    checkbox-provider-sru
    checkbox-provider-tpm2

Create ``checkbox-providers`` directory in ``/var/tmp/``::

    mkdir /var/tmp/checkbox-providers

.. note::
    You may not have write permissions for ``/var/tmp/``. You may want to
    run mkdir with sudo and later ``chown`` that directory

Clone Checkbox repository and copy the base provider to the side-loaded
directory::

    cd $HOME
    git clone --depth=1 https://github.com/canonical/checkbox.git
    cp -r $HOME/checkbox/providers/base /var/tmp/checkbox-providers/

.. tip::
    --depth=1 tells git not to download all the history of the repo

When started, Checkbox should display following warning::

    $ checkbox.checkbox-cli
    Using sideloaded provider: checkbox-provider-base, version 2.1.0 from
    /var/tmp/checkbox-providers/base

Let's edit the job definition::

    $ vim /var/tmp/checkbox-providers/base/units/stress/jobs.pxu

Now let's run Checkbox::

    $ checkbox.checkbox-cli

The recently edited definition should be used.
