.. Checkbox documentation master file, created by
   sphinx-quickstart on Wed Feb 13 11:18:39 2013.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Checkbox
==========

Checkbox is a flexible test automation software.
It's the main tool used in Ubuntu Certification program.

You can use checkbox without any modification to check if your system is
behaving correctly or you can develop your own set of tests to check your
needs. See :ref:`tutorials` for details.

.. warning::

    Documentation is under development. Some things are wrong, inaccurate or
    describe development goals rather than current state.

.. _installation:

Installation
^^^^^^^^^^^^

Checkbox can be installed from a :abbr:`PPA (Personal Package Archive)`
(recommended) or :abbr:`pypi (python package index)` on Ubuntu Precise (12.04)
or newer.

.. code-block:: bash

    $ sudo add-apt-repository ppa:hardware-certification/public && sudo apt-get update && sudo apt-get install checkbox-ng

Running stable release update tests
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Checkbox has special support for running stable release updates tests in an
automated manner. This runs all the jobs from the *sru.test plan* and sends the
results to the certification website.

To run SRU tests you will need to know the so-called :term:`Secure ID` of the
device you are testing. Once you know that all you need to do is run:

.. code-block:: bash

    $ checkbox sru $secure_id submission.xml

The second argument, submission.xml, is a name of the fallback file that is
only created when sending the data to the certification website fails to work
for any reason.

Table of contents
=================

.. toctree::
   :maxdepth: 3

   intro.rst
   tutorials.rst
   units/index.rst
   bugs.rst
   stack.rst
   launcher-tutorial.rst
   qml-job-tutorial.rst
   configs.rst
   nested-test-plan.rst
   snappy.rst
   testing-snappy.rst

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
