.. PlainBox documentation master file, created by
   sphinx-quickstart on Wed Feb 13 11:18:39 2013.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

PlainBox
========

:term:`PlainBox` is a hardware testing tool useful for certifying laptops,
desktops and servers with Ubuntu. It is a replacement for the current
certification tool, :term:`CheckBox`.

PlainBox *complements* CheckBox. It uses all the hardware test definitions,
scripts and libraries from CheckBox. PlainBox is currently in **alpha** stages,
having mostly but not entirely complete core and a developer-centric command
line interface.

.. warning::

    Documentation is under development. Some things are wrong, inaccurate or
    describe development goals rather than current state.

Installation
^^^^^^^^^^^^

PlainBox can be installed from a :abbr:`PPA (Personal Package Archive)`
(recommended) or :abbr:`pypi (python package index)` on Ubuntu Precise (12.04)
or newer.

.. code-block:: bash

    $ sudo add-apt-repository ppa:checkbox-dev/ppa && sudo apt-get update && sudo apt-get install plainbox


Testing your hardware
^^^^^^^^^^^^^^^^^^^^^

To test your hardware with the default set of tests run this command.

.. code-block:: bash

    $ plainbox run --whitelist=/usr/share/checkbox/data/whitelists/default.whitelist --output-format=xml --output-file=submission.xml

The :file:`submission.xml` you get in the end can be submitted to the
:term:`certification website`. For more details see :ref:`usage`

Table of contents
=================

.. toctree::
   :maxdepth: 2

   usage.rst
   dev/index.rst
   glossary.rst
   changelog.rst

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
