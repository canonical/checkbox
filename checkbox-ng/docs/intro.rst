Introduction to Checkbox
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
 * ``qml`` -- A test with GUI defined in a QML file. 
   See :ref:`qml-job-tutorial`



