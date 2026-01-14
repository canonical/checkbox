Changing output verbosity
===============================

When test are executed, by default, Checkbox prints errors and warnings of all
test jobs on the standard output. But sometimes you may want to know more on the
tests that are executing, or you may only care about the results. 

To customize the types of output information produced while running tests, you can
either apply verbosity options when you launch Checkbox, or change the UI output 
options in a launcher: ``ui.output`` and ``ui.verbosity``.

Hide output by job types
-------------------------

You can hide output from resource jobs and automatic jobs by toggling the
``ui.output`` option. 

For example, when resource jobs are plenty, the standard output may fill up with their
output. In this case, consider the ``hide-resource-and-attachment`` option in the 
following launcher: 

.. code-block:: ini
  :emphasize-lines: 9

  [test plan]
  unit = com.canonical.certification::smoke
  forced = yes

  [test selection]
  forced = yes

  [ui]
  output = hide-resource-and-attachment

Similarly, to hide the standard output of automatic jobs, use the
``hide-automated`` option as in the following launcher:

.. code-block:: ini
  :emphasize-lines: 10

  [test plan]
  unit = com.canonical.certification::smoke
  forced = yes

  [test selection]
  forced = yes

  [ui]
  # This also hides resource and attachments, they are automated as well!
  output = hide-automated

Change verbosity level
-----------------------

By default, Checkbox only prints errors and warnings to the output. If you want to have more detailed information about Checkbox execution, run Checkbox tests with one of the verbosity levels:

* verbose - report informational messages during execution, such as job starting
* debug - report all debug messages

Using command options
~~~~~~~~~~~~~~~~~~~~~

When you invoke Checkbox, add either the ``--verbose`` or ``--debug`` option respectively.

For example::

  $ checkbox.checkbox-cli --debug launcher mylauncher

Using launcher configurations
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Add the ``verbosity`` option in the ``ui`` section of your launcher file. For example:

.. code-block:: ini
  :emphasize-lines: 10

  [test plan]
  unit = com.canonical.certification::smoke
  forced = yes

  [test selection]
  forced = yes

  [ui]
  # Also, `debug` is available
  verbosity = verbose

For more information about the ``ui`` section, see :doc:`../../reference/launcher`.
