.. _advanced_configs:

.. todo::

   Replace smoke -> tutorial

===============
Advanced Config
===============

This section of the tutorial documents some useful configuration that are commonly
found in the wild. This is by no means a complete list of all possible items that
one can find in a configuration. Refer to the `launcher`_ section for more.

Transport and Report
====================

Checkbox allows a configuration to specify how the test report should be represented.
One usage of this feature is to output the final report to ``stdout`` in text form.
Create a launcher like the following:

.. code-block:: none

  [test plan]
  unit = com.canonical.certification::smoke
  forced = yes

  [test selection]
  forced = yes

  # note what comes after : is the name of the exporter
  [exporter:text]
  # this specific one exports text,
  # you can also try com.canonical.plainbox::html
  unit = com.canonical.plainbox::text

  # similarly, what comes out : is the name of the transport
  [transport:out_to_stdout]
  # standard out, you can also try stderr for standard error
  stream = stdout
  type = stream

  # also here, : delimits the name of the section
  # this section tells Checkbox that we want a custom report
  [report:screen]
  # we used the exporter we defined before (by using its name)
  exporter = text
  # and we use the transport we defined as well
  transport = out_to_stdout

Launch checkbox, it should print a human readable output to the stream you chosed!

.. note::

  Checkbox will ask you if you want to submit the ``screen`` report. This is
  Checkbox's way of asking if you want it to produce that report. Respond yes.
  See the example below to know how to avoid having to give confirmation
  (using forced)


It may be tempting to redirect this output to file manually, but it is possible to
save it in a file using the same mechanism. Try the following launcher for
instance to create a beautiful html report to a file:

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

Launch Checkbox, you should now have an html report to check out in
``/tmp/output.html``.

Of course you can have multiple exporters, as mentioned before, try the following
launcher, it will produce one html report and two (equal) textual reports.

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

  If you start Checkbox with this launcher, remember to remove ``~/.last_result.txt``
  you may not want it to be there


UI Verbosity
==============

Sometimes we may want more informations on the tests that are executing, sometimes
we may only care about the results. Checkbox allows you to customize how much
output is produced while running via two mechanisms ``ui.output``
and ``ui.verbosity``.

For example, consider the following launcher, when resource jobs are plenty the
standard output may fill up with their output and we may not want to read it.

.. code:: none

  [test plan]
  unit = com.canonical.certification::smoke
  forced = yes

  [test selection]
  forced = yes

  [ui]
  output = hide-resource-and-attachment

Similarly, we may not want to see the standard output of automatic jobs, we can
obtain that with the following launcher:

.. code:: none

  [test plan]
  unit = com.canonical.certification::smoke
  forced = yes

  [test selection]
  forced = yes

  [ui]
  # This also hides resource and attachments, they are automated as well!
  output = hide-automated

We can also obtain the opposite result, sometimes we may want to have more
informations about a Checkbox execution, for example, we may want to read
when a job is started. Check out the following launcher to get that.

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

Checkbox is able to automatically retry failing jobs, try to use the following
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

As you may have noticed, once every test was executed, all failing tests were
retried up to two times, waiting a few seconds between one attempt and the next.
This may be very useful if, for example, a test relies on an external factor
like, for example, WiFi access.

Config Renaming
===============

Checkbox, by default, always calls its configs as ``checkbox.conf`` and always
looks for them in the same three places. This may be an issue when one wants to
store and use multiple configurations on the same machine.

Lets try to make Checkbox load a new configuration from a different location and
with a different name.

First, create the following config in ``/tmp/my_config_name.conf``

.. code:: none

   [test plan]
   unit = com.canonical.certification::smoke
   forced = yes

   [test selection]
   forced = yes

Also, just to be sure that this works, lets create a standard
``~/.config/checkbox.conf`` config that does not do what we want

.. code:: none

   [test plan]
   unit = wrong_name

Then create the following launcher and call Checkbox with it.

.. code:: none

   [config]
   config_filename = /tmp/my_config_name.conf

As you can see the correct file was loaded, as the other one would have
risen an error. The ``config_filename`` can also be just a name. To try this
modify the previous launcher by removing ``/tmp/`` and move the
``my_config_name.conf`` to ``~/.config``. Launch Checkbox and see, you should
obtain the same result.

Config Inheritance
==================

Config renaming is useful, but sometimes it is not enough to maintain a clean
setup. One thing that it common is wanting a basic configuration of Checkbox
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

Now create a launcher file that uses this global configs:

.. code:: none

   [config]
   config_filename = ~/.config/checkbox_global.conf

   [test plan]
   unit = com.canonical.certification::smoke
   force = True

Launch checkbox and check that both configs are taken into account. Lets say
that this is the default behaviour that you use when running tests and
checking that everything is all right. Now create another launcher that we can use
for submissions

.. code:: none

   [config]
   config_filename = ~/.config/checkbox_global.conf

   [test plan]
   unit = com.canonical.certification::smoke
   forced = True

   [launcher]
   stock_reports = [text, certification, submission_files]
   local_submission = True

As you can see, this launcher overwrites the ``stock_reports`` value from the imported
config. This is intended, this is why we call this feature inheritance, when a config
or a launcher imports another config/launcher, every value is inherited and can be
overwritten.

.. warning::

   Checkbox will happily resolve names and paths in your configs with the only
   boundary that you can not have a circular import. We strongly advise you to
   use this feature in moderation, it can simplify the maintaining of multiple
   configurations by avoiding copy-pasting values around but it can make debugging
   a configuration very complicated as well. Also, remember ``check-config``, it
   tracks the origin of config values and can help you remember where you set any
   configuration.
