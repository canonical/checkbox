.. _advanced_configs:

.. todo::

   Replace smoke -> tutorial

===============
Advanced Config
===============

This section of the tutorial documents some useful configuration that are commonly
found in the wild. This is by no means a complete list of all possible items that
one can find in a configuration. Refer to the :ref:`launcher` section for more.

Transport and Report
====================

Checkbox allows a configuration to specify how the test report should be represented and where each representation should be output.
One use case for this is outputting the final report to ``stdout`` in text form.
Create a launcher like the following:

.. code-block:: none

  [test plan]
  unit = com.canonical.certification::smoke
  forced = yes

  [test selection]
  forced = yes

  # note what comes after ":" is the name of the exporter
  [exporter:text]
  # this specific one exports text,
  # you can also try com.canonical.plainbox::html
  unit = com.canonical.plainbox::text

  # similarly, what comes after ":" is the name of the transport
  [transport:out_to_stdout]
  # standard out, you can also try "stderr" for standard error
  stream = stdout
  type = stream

  # also here, : delimits the name of the section
  # this section tells Checkbox that we want a custom report
  [report:screen]
  # we used the exporter we defined before (by using its name)
  exporter = text
  # and we use the transport we defined as well
  transport = out_to_stdout

When you now launch Checkbox it prints a human readable output to the stream you chose!

.. note::

  Checkbox will ask you if you want to submit the ``screen`` report. This is
  the Checkbox way of asking if you want it to produce that report. Respond yes.
  See the example below to know how to avoid having to give confirmation
  (using `forced`)


It may be tempting to redirect this output to file manually, but it is possible to
save it in a file using the same mechanism. Try the following launcher for
instance to create a beautiful HTML report to a file:

.. code-block:: none

  [test plan]
  unit = com.canonical.certification::smoke
  forced = yes

  [test selection]
  forced = yes

  [exporter:html]
  unit = com.canonical.plainbox::html

  [transport:out_to_file]
  type = file
  path = /tmp/output.html

  [report:file_report]
  exporter = html
  transport = out_to_file
  # This tells Checkbox to always produce this report
  # without asking any confirmation
  forced = yes

Launch Checkbox, and you should now have an HTML report to check out at
``/tmp/output.html``.

You can configure multiple exporters. Try the following launcher to produce a HTML report and two (identical) textual reports.

.. code-block:: none

  [test plan]
  unit = com.canonical.certification::smoke
  forced = yes

  [test selection]
  forced = yes

  [exporter:text]
  unit = com.canonical.plainbox::text

  [transport:out_to_file1]
  type = file
  path = /tmp/upload.txt

  [transport:out_to_file2]
  type = file
  path = ~/.last_result.txt

  [transport:out_to_file]
  type = file
  path = /tmp/upload.html

  [exporter:html]
  unit = com.canonical.plainbox::html

  [report:file_1]
  exporter = text
  transport = out_to_file1
  forced = yes

  [report:file_2]
  exporter = text
  transport = out_to_file2
  forced = yes

  [report:html_report]
  exporter = html
  transport = out_to_file
  forced = yes

.. note::

  If you start Checkbox with this launcher, remember that it will
  create a file in ``~/.last_result.txt``. You may want
  to remove it after this experiment.

UI Verbosity
==============

Sometimes we may want to know more on the tests that are executing, sometimes
we may only care about the results. To customise how much
output is produced while running via two mechanisms: ``ui.output``
and ``ui.verbosity``.

For example, consider the following launcher. When resource jobs are plenty the
standard output may fill up with their output and we may not want to read it.

.. code:: none

  [test plan]
  unit = com.canonical.certification::smoke
  forced = yes

  [test selection]
  forced = yes

  [ui]
  output = hide-resource-and-attachment

Similarly, we may not want to see the standard output of automatic jobs. We can
achieve that with the following launcher:

.. code:: none

  [test plan]
  unit = com.canonical.certification::smoke
  forced = yes

  [test selection]
  forced = yes

  [ui]
  # This also hides resource and attachments, they are automated as well!
  output = hide-automated

We can also obtain the opposite result: sometimes we may want to have as
much information possible about a Checkbox execution. For example, we may
want to read when a job is started. The following launcher accomplishes that:

.. code:: none

  [test plan]
  unit = com.canonical.certification::smoke
  forced = yes

  [test selection]
  forced = yes

  [ui]
  # Also, `debug` is available
  verbosity = verbose

Auto-Retrying Failing Tests
===========================

Checkbox is able to automatically retry failing jobs. Use the following
launcher to see how this is done.

.. code:: none

  [test plan]
  unit = com.canonical.certification::smoke
  forced = yes

  [test selection]
  forced = yes

  [ui]
  auto_retry = yes
  max_attempts = 2
  # the delay is in seconds
  delay_before_retry = 2

After every test was executed, all failing tests were
retried up to two times, waiting a few seconds between one attempt and the next.
This may be useful if, for example, a test relies on an external factor
like WiFi access.

Config Renaming
===============

The default configuration filename Checkbox looks for is `checkbox.conf`. The config file is always
looks for them in the same three places. This may be an issue when one wants to
store and use multiple configurations on the same machine.

Let's try to make Checkbox load a new configuration from a different location.

First, create the following config at ``/tmp/my_config_name.conf``

.. code:: none

   [test plan]
   unit = com.canonical.certification::smoke
   forced = yes

   [test selection]
   forced = yes

To verify that this works, let's create a config file with the default filename `checkbox.conf` at one of the default lookup locations
``~/.config/checkbox.conf`` config that does _not_ do what we want.

.. code:: none

   [test plan]
   unit = wrong_name

Then create the following launcher and call Checkbox with it.

.. code:: none

   [config]
   config_filename = /tmp/my_config_name.conf

Since no error was raised, you can see that the correct file was loaded,.
The ``config_filename`` can also be just a name. To try this
modify the previous launcher by removing ``/tmp/`` and move the
``my_config_name.conf`` to ``~/.config``. Now launch Checkbox and you should
see the same result.

Config Inheritance
==================

Config renaming is useful, but sometimes it is not enough to maintain a clean
setup. One thing that is common is wanting a basic configuration of Checkbox
and a few smaller configurations that are specific to each situation.

For example, create the following config file in ``~/.config/checkbox_global.conf``

.. code:: none

  [ui]
  output = hide-automated

  [launcher]
  session_title = My machine name
  stock_reports = [text]

  [exporter:text]
  unit = com.canonical.plainbox::text

  [transport:out_to_file]
  type = file
  path = /tmp/.last_checkbox_out.txt

  [report:screen]
  exporter = text
  transport = out_to_file

  [manifest]
  com.canonical.certification::my_manifest_key = True

Now create a launcher file that uses this global config:

.. code:: none

   [config]
   config_filename = ~/.config/checkbox_global.conf

   [test plan]
   unit = com.canonical.certification::smoke
   force = True

Launch Checkbox and check that both configuration sources are taken into account. Let's say
that this is the default behavior that you use when running tests.
Now create another launcher that we can use
for when we want to output a submission:

.. code:: none

   [config]
   config_filename = ~/.config/checkbox_global.conf

   [test plan]
   unit = com.canonical.certification::smoke
   forced = True

   [launcher]
   stock_reports = [text, certification, submission_files]
   local_submission = True

As you can see, this launcher overrides the ``stock_reports`` value from the imported
config. This configuration value inheritance (when a config
or a launcher imports another config/launcher) allows every value to be inherited and
overwritten.

.. warning::

   Checkbox will happily resolve names and paths in your configs with the only
   restriction that you can not have a circular import. We advise you to
   use this feature in moderation since whilst it can simplify the maintaining of multiple
   configurations by avoiding copy-pasting values around, it can also make debugging
   a configuration complicated. Also, remember ``check-config``, which
   tracks the origin of config values and can help you remember where you set any
   configuration.
