Using Checkbox
========================

.. contents::

Getting Started
---------------

You've got Checkbox installed, right? :ref:`installation`

To run command line version of Checkbox, in your terminal run ``checkbox-cli``.
You should be greeted with test plan selection screen:

.. image:: _images/cc2.png
 :height: 343
 :width: 300
 :scale: 100
 :alt: checkbox-cli enables you to select which test suite to run.

With a test plan selected, you can choose the individual tests to run:

.. image:: _images/cc3.png
 :height: 600
 :width: 800
 :scale: 100
 :alt: checkbox-cli enables you to select or de-select specific tests.

When the tests are run, the results are saved to files and the program
prompts to submit them to Launchpad.

Checkbox Command Line
---------------------

When checkbox is run without any arguments, i.e.::

    $ checkbox-cli

Interactive session is started with the default options.

checkbox-cli startprovider
``````````````````````````

``startprovider`` subcommand creates a new provider, e.g.::

    $ checkbox-cli startprovider com.acme:example

The command will also add example units to that provider, to create an empty
provider, use ``--empty`` option, e.g.::

    $ checkbox-cli startprovider --empty com.acme:another-example


checkbox-cli list
`````````````````

``list`` command prints out all units of the following type.

Currently there are following types you can list:

    - job
    - test plan
    - category
    - file
    - template
    - file
    - manifest entry
    - packaging meta-data
    - exporter
    - all-jobs (this special type list both, jobs and templates generating
      jobs and has a different output formatting)

Example::

    $ checkbox-cli list job

    $ checkbox-cli list "test plan"

    $ checkbox-cli list all-jobs

.. note::
    For multi-word types like 'test plan' remember to escape the spaces in
    between, or enquote the type name.

.. _output-formatting:

Output Formatting
.................

For the 'all-jobs' group, the output may be formatted to suit your needs. Use
``--format`` option when listing ``all-jobs``. The string will be interpolated
using properties of the listed jobs. Invoke
``checkbox-cli list all-jobs --format ?``
to see available properties. If the job definition doesn't have the specified
property, ``<missing $property_name>`` will be printed in its place instead.
Additional property - ``unit_type`` is provided to the formatter when listing
all jobs. It is set to 'job' for normal jobs and 'template job' for jobs
generated with a template unit.

Example::

    $ checkbox-cli list all-jobs -f "{id}\n\t{tr_summary}\n"

    $ checkbox-cli list all-jobs -f "{id}\n"

    $ checkbox-cli list all-jobs -f "{unit_type:12} | {id:50} | {summary}\n"

.. note::
    ``\n`` and ``\t`` in the formatting string are interpreted and replaced
    with new line and tab respectively.

    When using own formatting, the jobs are not suffixed with a new line - you
    have to explicitly use it.


checkbox-cli list-bootstrapped
``````````````````````````````

This special command lists all the jobs that would be run on the device after
the bootstrapping phase, i.e. after all the resource jobs are run, and all
of the templates were instantiated.

It requires an argument being the test plan for which the bootstrapping should
execute.

Example::

    $ checkbox-cli list-bootstrapped com.canonical.certification::default

Similarly to the ``checkbox-cli list all-jobs`` command, the output of
``checkbox-cli list-bootstrapped`` can be formatted using the ``-f`` parameter.
See ``checkbox-cli list`` :ref:`output-formatting` section for more information.


checkbox-cli tp-export
``````````````````````

``tp-export`` exports a test plan as a spreadsheet document. Tests are grouped
by categories and ordered alphabetically with the full description (or the job
summary if there's no description). In addition to the description, the
certification status (blocker/non-blocker) is exported.

The session is similar to ``list-bootstrapped`` but all resource jobs are
returning fake objects and template-filters are disabled to ensure
instantiation of template units. By default only one resource object is
returned. The only exception is the graphics_card resource where two objects are
used to simulate hybrid graphics.

The command prints the full path to the document on exit/success.

Example::

    $ checkbox-cli tp-export com.canonical.certification::client-cert-18-04

It can be used to automatically generate a test case guide using a pdf converter:

Example::

    $ checkbox-cli tp-export com.canonical.certification::client-cert-18-04 | xargs -d '\n' libreoffice --headless --invisible --convert-to pdf


checkbox-cli launcher
`````````````````````

``launcher`` command lets you customize checkbox experience.

See :ref:`launcher-tutorial` for more details.

.. note::
    ``launcher`` is implied when invoking checkbox-cli with a file as the only
    argument. e.g.::

        $ checkbox-cli my-launcher

    is equivalent to::

        $ checkbox-cli launcher my-launcher

.. _run_subcmd:

checkbox-cli run
````````````````

``run`` lets you run particular test plan or a set of jobs.

To just run one test plan, use the test plan's id as an argument, e.g.::

    $ checkbox-cli run com.canonical.certification::smoke

To run a hand-picked set of jobs, use regex pattern(s) as arguments. Jobs
with id matching the expression will be run, e.g.::

    $ checkbox-cli run com.acme:.*

.. note::
    The command above runs all jobs which id begins with ``com.acme:``

You can use multiple patterns to match against, e.g.::

    $ checkbox-cli run .*true .*false

.. note::
    The command above runs all jobs which id ends with 'true' or 'false'

Looking Deeper
--------------

Providers
`````````

First, we installed some "provider" packages. Providers were designed to
encapsulate test descriptions and their related tools and data. Providers
are shipped in Debian packages, which allows us to express dependencies to
ensure required external packages are installed, and we can also separate
those dependencies; for instance, the provider used for server testing
doesn't actually contain the server-specific test definitions (we try to
keep all the test definitions in the Checkbox provider), but it does depend
on all the packages needed for server testing. Most users will want the
resource and Checkbox providers which contain many premade tests, but this
organization allows shipping the tiny core and a fully customized provider
without extraneous dependencies.

A provider is described in a configuration file (stored in
``/usr/share/plainbox-providers-1``). This file describes where to find all
the files from the provider. This file is usually managed automatically
(more on this later). A provider can ship jobs, binaries, data and test plans.


A **job** or **test** is the smallest unit or description that Checkbox
knows about. It describes a single test (historically they're called
jobs). The simplest possible job is::

 id: a-job
 plugin: manual
 _description: Ensure your computer is turned on. Is the computer turned on?

Jobs are shipped in a provider's jobs directory. This ultra-simple example
has three fields: ``id``, ``plugin``, and ``description``. (A real job
should include a ``_summary`` field, too.) The ``id`` identifies the job
(of course) and the ``_description`` provides a plain-text description of
the job. In the case of this example, the description is shown to the user,
who must respond because the ``plugin`` type is ``manual``. ``plugin``
types include (but are not limited to):

 * ``manual`` -- A test that requires the user to perform some action and
   report the results.
 * ``shell`` -- An automated test that requires no user interaction; the
   test is passed or failed on the basis of the return value of the script
   or command.
 * ``resource`` -- Job that identifies the resources that the system has.
   (e.g. discrete GPU, Wi-Fi module). This information can later be used by
   other jobs to control other jobs' execution. (E.g. skip Wi-Fi tests if
   there's no Wi-Fi chip).
 * ``user-interact`` -- A test that asks the user to perform some action
   *before* the test is performed. The test then passes or fails
   automatically based on the output of the test. An example is
   ``keys/media-control``, which runs a tool to detect keypresses, asks the
   user to press volume keys, and then exits automatically once the last
   key has been pressed or the user clicks the skip button in the tool.
 * ``user-interact-verify`` -- This type of test is similar to the
   ``user-interact`` test, except that the test's output is displayed for
   the user, who must then decide whether it has passed or failed. An
   example of this would be the ``usb/disk_detect`` test, which asks the
   user to insert a USB key, click the ``test`` button, and then verify
   manually that the USB key was detected correctly.
 * ``user-verify`` -- A test that the user manually performs or runs
   automatically and requires the user to verify the result as passed or
   failed.  An example of this is the graphics maximum resolution test
   which probes the system to determine the maximum supported resolution
   and then asks the user to confirm that the resolution is correct.
