.. _usage:

Usage
=====

Currently :term:`PlainBox` has no graphical user interface. To use it you need
to use the command line.

Basically there is just one command that does everything we can do so far, that
is :command:`plainbox run`. It has a number of options that tell it which
:term:`job` to run and what to do with results.

PlainBox has built-in help system so running :command:`plainbox run --help`
will give you instant information about all the various arguments and options
that are available. This document is not intended to replace that.

Running a specific job
^^^^^^^^^^^^^^^^^^^^^^

To run a specific :term:`job` pass it to the ``--include-pattern`` or ``-i``
option.

For example, to run the ``cpu/scaling_test`` job:

.. code-block:: bash

    $ plainbox run -i cpu/scaling_test

.. note::

    The option ``-i`` can be provided any number of times.

Running jobs related to a specific area
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

PlainBox has no concept of job categories but you can simulate that by
running all jobs that follow a specific naming pattern. For example, to run
all of the USB tests you can run the following command:

.. code-block:: bash

    $ plainbox run -i 'usb/.*'

To list all known jobs run:

.. code-block:: bash

    plainbox special --list-jobs

Running a white list
^^^^^^^^^^^^^^^^^^^^

To run a :term:`white list` pass the ``--whitelist`` or ``-w`` option.

For example, to run the default white list run:

.. code-block:: bash

    $ plainbox run -w /usr/share/checkbox/data/whitelists/default.whitelist

Saving test results as XML
^^^^^^^^^^^^^^^^^^^^^^^^^^

To generate an XML file that can be sent to the :term:`certification website`
you need to pass two additional options:

1. ``--output-format=xml``
2. ``--output-file=NAME`` where *NAME* is a file name

For example, to get the default certification tests ready to be submitted
run this command:

.. code-block:: bash

    $ plainbox run --whitelist=/usr/share/checkbox/data/whitelists/default.whitelist --output-format=xml --output-file=submission.xml

