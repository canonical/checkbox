Introduction to Plainbox
========================

.. contents::

What is Plainbox?
-----------------

Many years ago, a dark sorcerer known only as CR3 created a testing tool
called ``hw-test`` with the vision of running tests against hardware to
bless the hardware and deem it as Ubuntu Certified.  There was great
rejoicing.  From the crowd that gathered around this tool came requests and
requirements for new features, new tests and new methods of doing things.
Over the subsequent years, a tool called Checkbox was created. It was the
product of the design by committee philosophy and soon grew ponderous and
difficult to understand except by a few known only as "The Developers."
Checkbox's goal was to function as a universal testing engine that could
drive several types of testing: end-users running tests on their systems,
certification testing with a larger set of tests, and even OEM-specific
testing with custom tests.

A couple of years ago Checkbox started showing its age. The architecture
was difficult to understand and to extend and the core didn't really scale
to some things we wanted to do; however, the test suite itself was still
quite valuable.

Thus Plainbox was created, as a "plain Checkbox" and again, there was much
rejoicing. It was originally meant to be a simpler library for creating
testing applications and as a requirement, it was designed to be compatible
with the Checkbox test/job definition format.

Since then, Plainbox has become a large set of libraries and tools, but the
central aim is still to write testing applications. Note that the term
*Checkbox* is still used to refer to the test suite generically; *Plainbox*
is used to refer to the new tool set "under the hood."

Goal
----

The goal of these tools is of course to run tests. They use a test
description language that was inherited from Checkbox, so it has many
interesting quirks. Since Checkbox itself is now deprecated, we have been
adding new features and improving the test description language so this is
in some flux.

Terminology
-----------

In developing or using Plainbox, you'll run into several unfamiliar terms.
Check the :doc:`../glossary` to learn what they mean. In fact, you should
probably check it now. Pay particular attention to the terms *Checkbox*,
*Plainbox*, *job* and *provider*.

Getting Started
---------------

To get started, we'll install Plainbox and ``checkbox-ng`` along with some
tests and look at how they are organized and packaged.

The newest versions are in our PPAs. We'll use the development PPA at
``ppa:checkbox-dev/ppa``. From there we'll install ``plainbox``,
``checkbox-ng``, and ``plainbox-provider-checkbox``.

As an end user this is all I need to run some tests. We can quickly run
``checkbox-cli``, which will show a series of screens to facilitate running
tests. First up is a welcome screen:

.. image:: cc1.png
 :height: 178
 :width: 800
 :scale: 100
 :alt: checkbox-cli presents an introductory message before enabling you to
       select tests.

When you press the Enter key, ``checkbox-cli`` lets you select which
test plan to use:

.. image:: cc2.png
 :height: 343
 :width: 300
 :scale: 100
 :alt: checkbox-cli enables you to select which test suite to run.

With a test plan selected, you can choose the individual tests to run:

.. image:: cc3.png
 :height: 600
 :width: 800
 :scale: 100
 :alt: checkbox-cli enables you to select or de-select specific tests.

When the tests are run, the results are saved to files and the program
prompts to submit them to Launchpad.

As mentioned, ``checkbox-cli`` is just a convenient front-end for some
Plainbox features but it lets us see some aspects of Plainbox.

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
(more on this later). A provider can ship jobs, binaries, data and
test plans.

A **job** or **test** is the smallest unit or description that Plainbox
knows about. It describes a single test (historically they're called
jobs). The simplest possible job is::

 id: a-job
 plugin: manual
 description: Ensure your computer is turned on. Is the computer turned on?

Jobs are shipped in a provider's jobs directory. This ultra-simple example
has three fields: ``id``, ``plugin``, and ``description``. (A real job
should include a ``_summary`` field, too.) The ``id`` identifies the job
(of course) and the ``description`` provides a plain-text description of
the job. In the case of this example, the description is shown to the user,
who must respond because the ``plugin`` type is ``manual``. ``plugin``
types include (but are not limited to):

 * ``manual`` -- A test that requires the user to perform some action and
   report the results.
 * ``shell`` -- An automated test that requires no user interaction; the
   test is passed or failed on the basis of the return value of the script
   or command.
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

Each provider has a ``bin`` directory and all binaries there are available
in the path.

Other Questions
---------------

 **What Python modules are useful?**
  I usually Google for the description of the problem I'm trying to solve,
  and/or peruse the Python documentation in my spare time. I recommend the
  *Dive Into Python* books if you have experience with another language, as
  they are very focused on how to translate what you know into Python. This
  applies also to Pythonisms like iterators, comprehensions, and
  dictionaries which are quite versatile, and others. Again, the *Dive*
  books will show you how these work.

 **Are there other tools to use?**
  ``flake8`` or ``pyflakes``, it's always a good idea to run this  if you
  wrote a Python script, to ensure consistent syntax. ``manage.py
  validate`` and ``plainbox dev analyze`` are also good tools to know
  about.

 **Is there a preferred editor for Python programming?**
  I don't really know of a good editor/IDE that will provide a lot of help
  when developing Python, as I usually prefer a minimalistic editor. I'm
  partial to ``vim`` as it has syntax coloring, decent formatting
  assistance, can interface with ``git`` and ``pyflakes`` and is just
  really fast. We even have a plugin for Plainbox job files. Another good
  option if you're not married to an editor is sublime text, Zygmunt has
  been happy with it and it seems easy to extend, plus it's very
  nice-looking. A recent survey identified Kate as a good alterntive. The
  same survey identified ``gedit`` as *not* a good alternative so I'd avoid
  that one. Finally if you're into cloud, ``cloud9.io`` may be an option
  although we don't have a specific Plainbox development setup for it.

References
----------

 :doc:`Reference on Plainbox test authoring <index>`

 :doc:`jobs`

 :doc:`Plainbox provider template <provider-template>`

 :doc:`Provider and job writing tutorial <tutorial>`

 :doc:`../dev/intro`

 :doc:`What resources are and how they work <../dev/resources>`

 :doc:`Man pages on special variables available to jobs <../manpages/PLAINBOX_SESSION_SHARE>`

 :doc:`All the manpages <../manpages/index>`

 `The Checkbox stack diagram`_

.. _The Checkbox stack diagram:
   http://checkbox.readthedocs.org/en/latest/stack.html

 `Old Checkbox documentation for nostalgia`_

.. _Old Checkbox documentation for nostalgia:
   https://wiki.ubuntu.com/Testing/Automation/Checkbox

 `Usual Python modules`_

.. _Usual Python modules: https://docs.python.org/3.3/

 `Document on upcoming template units feature`_

.. _Document on upcoming template units feature:
   http://bazaar.launchpad.net/~checkbox-dev/checkbox/trunk/view/head:/plainbox/docs/manpages/plainbox-template-units.rst

 `A quick introduction to Bazaar and bzr`_

.. _A quick introduction to Bazaar and bzr:
   http://doc.bazaar.canonical.com/bzr.dev/en/mini-tutorial/

 `A tool to use git locally but be able to pull/push from Launchpad`_

.. _A tool to use git locally but be able to pull/push from Launchpad: http://zyga.github.io/git-lp/

 `A video on using git with Launchpad`_

.. _A video on using git with Launchpad:
   https://plus.google.com/115602646184989903283/posts/RCepekrA5gu

 `A video on how to set up Sublime Text for Plainbox development`_

.. _A video on how to set up Sublime Text for Plainbox development:
   https://www.youtube.com/watch?v=mrfyAgDg4ME&list=UURGrmUhQo5P9hTbVskIIjoQ

 `Checkbox(ng) documentation home`_

.. _Checkbox(ng) documentation home: http://checkbox.readthedocs.org
