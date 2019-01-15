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

.. _installation:

Installation
^^^^^^^^^^^^

Checkbox can be installed from a :abbr:`PPA (Personal Package Archive)`
(recommended) or :abbr:`pypi (python package index)` on Ubuntu Precise (12.04)
or newer.

.. code-block:: bash

    $ sudo add-apt-repository ppa:hardware-certification/public && sudo apt-get update && sudo apt-get install checkbox-ng

Table of contents
=================

.. toctree::
   :maxdepth: 3

   using.rst
   understanding.rst
   tutorials.rst
   remote.rst
   units/index.rst
   bugs.rst
   stack.rst
   launcher-tutorial.rst
   side-loading.rst
   configs.rst
   nested-test-plan.rst
   snappy.rst
   testing-snappy.rst
   custom-app.rst
   glossary.rst

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
