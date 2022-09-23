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
    `~/provider` directory once you're done developing, so you don't get nasty
    surprises down the line.
    Checkbox will not submit any reports to Certification website if
    side-loaded providers have been used.

Example scenario
================

Goal: change the runtime of the stress/cpu_stress_ng_test job without rebuilding
snap.

Make sure that checkbox-snappy snap is installed. It comes with following
providers available::

    plainbox-provider-checkbox
    plainbox-provider-docker
    2017.com.canonical.se:engineering-tests
    plainbox-provider-ipdt
    plainbox-provider-resource-generic
    plainbox-provider-snappy
    plainbox-provider-sru
    plainbox-provider-tpm2

Create ``checkbox-providers`` directory in ``/var/tmp/``::

    mkdir /var/tmp/checkbox-providers

.. note::
    You may not have write permissions for ``/var/tmp/``. You may want to
    run mkdir with sudo and later ``chown`` that directory

Clone plainbox-provider-checkbox to the side-loaded directory::

    cd /var/tmp/checkbox-providers
    git clone --depth=1 http://git.launchpad.net/plainbox-provider-checkbox

.. tip::
    --depth=1 tells git not to download all the history of the repo

When started, Checkbox should display following warning::

    $ checkbox-snappy.checkbox-cli
    WARNING:plainbox.session.assistant:Using side-loaded provider:
    com.canonical.certification:plainbox-provider-checkbox

Let's edit the job definition::

    $ vim /var/tmp/checkbox-providers/plainbox-provider-checkbox/units/stress/jobs.pxu

Now let's run Checkbox::

    $ checkbox-snappy.checkbox-cli

The recently edited definition should be used.
