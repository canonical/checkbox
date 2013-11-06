.. CheckBoxNG documentation master file, created by
   sphinx-quickstart on Wed Feb 13 11:18:39 2013.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

CheckBoxNG
==========

:term:`CheckBoxNG` is a hardware testing tool useful for certifying laptops,
desktops and servers with Ubuntu. It is a new version of :term:`CheckBox` that
is built directly on top of :term:`PlainBox`

CheckBoxNG *replaces* CheckBox, where applicable. 

.. warning::

    Documentation is under development. Some things are wrong, inaccurate or
    describe development goals rather than current state.

Installation
^^^^^^^^^^^^

CheckBoxNG can be installed from a :abbr:`PPA (Personal Package Archive)`
(recommended) or :abbr:`pypi (python package index)` on Ubuntu Precise (12.04)
or newer.

.. code-block:: bash

    $ sudo add-apt-repository ppa:checkbox-dev/ppa && sudo apt-get update && sudo apt-get install checkbox-ng 

Running stable release update tests
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

CheckBoxNG has special support for running stable release updates tests in an
automated manner. This runs all the jobs from the *sru.whitelist* and sends the
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
   :maxdepth: 2

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
