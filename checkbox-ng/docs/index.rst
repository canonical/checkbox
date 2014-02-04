.. PlainBox documentation master file, created by
   sphinx-quickstart on Wed Feb 13 11:18:39 2013.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

PlainBox
========

:term:`PlainBox` is a toolkit consisting of python3 library, development tools,
documentation and examples. It is targeted at developers working on testing or
certification applications and authors creating tests for such applications.

PlainBox can be used to both create simple and comprehensive test tools as well
as to develop and execute test jobs and test scenarios. It was created as a
refined and rewritten core of the :term:`CheckBox` project. It has a well
tested and documented core, small but active development community and a
collection of associated projects that use it as a lower-level engine/back-end
library.

PlainBox has a novel approach to discovering (and probing) hardware and
software that is extensible and not hardwired into the system. It allows test
developers to express association between a particular test and the hardware,
software and configuration constraints that must be met for the test to execute
meaningfully. This feature, along with pluggable test definitions, makes
PlainBox flexible and applicable to many diverse testing situations, ranging
from mobile phones, traditional desktop computers, servers and up to testing
"cloud" installations.

What are you interested in?
^^^^^^^^^^^^^^^^^^^^^^^^^^^

Are you a :doc:`test author <author/index>`, :doc:`application developer
<appdev/index>` or :doc:`core developer <dev/index>`?

Table of contents
=================

.. toctree::
   :maxdepth: 2

   usage.rst
   author/index.rst
   appdev/index.rst
   dev/index.rst
   ref/index.rst
   glossary.rst
   changelog.rst

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
