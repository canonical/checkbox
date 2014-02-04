.. _usage:

Basic Usage
===========

Currently :term:`PlainBox` has no graphical user interface. To use it you need
to use the command line.

PlainBox has built-in help system so running :command:`plainbox run --help`
will give you instant information about all the various arguments and options
that are available. This document is not intended to replace that.

Running a specific job
^^^^^^^^^^^^^^^^^^^^^^

Basically there is just one command that does everything we can do so far, that
is :command:`plainbox run`. It has a number of options that tell it which
:term:`job` to run and what to do with results.

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

To run a :term:`whitelist` pass the ``--whitelist`` or ``-w`` option.

For example, to run the default white list run:

.. code-block:: bash

    $ plainbox run -w /path/to/some/file.whitelist

Saving test results
^^^^^^^^^^^^^^^^^^^

Anything that PlainBox captures and stores during test execution can be
exported to a file using the exporter system. The two most commonly used
exporters are JSON (versatile and general) and XML (for internal Canonical use).

JSON Exporter
-------------

To generate a JSON file with all of the internally available data (for storage,
processing or other automation) you will need to pass three additional
arguments to ``plainbox run``:

#. ``--output-format=json``
#. ``--output-options=OPTION1,OPTION2`` where *OPTIONx* are option names.
#. ``--output-file=NAME`` where *NAME* is a file name.

Pass ``?`` to ``--output-options`` for a list of available options. Multiple
exporter options can be specified, separated with commas.

.. code-block:: bash

    $ plainbox run --whitelist=/path/to/some/file.whitelist --output-format=json --output-file=results.json

XML Exporter
------------

To generate an XML file that can be sent to the :term:`certification website`
you need to pass two additional arguments to ``plainbox run``:

#. ``--output-format=xml``
#. ``--output-file=NAME`` where *NAME* is a file name

For example, to get the default certification tests ready to be submitted
run this command:

.. code-block:: bash

    $ plainbox run --whitelist=/path/to/some/file.whitelist --output-format=xml --output-file=submission.xml

Other Exporters
---------------

You can discover the full list of known exporters at runtime, by passing ``?``
to ``--output-format``.

Custom Exporters
----------------

Exporters can be provided by third party packages. Exporters are very simple to
write. If you don't want to transform JSON to your preferred format, you can
copy the json exporter and use it as template for writing your own.
