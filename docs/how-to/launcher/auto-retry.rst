Configuring auto-retry for failing tests
==========================================

You can use launchers to configure Checkbox to automatically retry failing jobs.

Enable auto-retry
------------------

To apply the auto-retry function to all failing test jobs, add a ``ui`` section
in your launcher and set the ``ui.auto-retry`` option to ``yes``. You can also
specify the maximum number of attempts and the delay between each retry.

For example:

.. code-block:: ini
  :caption: my_launcher
  :emphasize-lines: 9-10, 12

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

After every test was executed, all failing tests were retried up to two times,
waiting 2 seconds between one attempt and the next. This may be useful if, for
example, a test relies on an external factor like WiFi access.

For more details about the ``ui`` section in Checkbox launchers, see
:doc:`../../reference/launcher`.

Skip auto-retry
---------------- 

When ``auto_retry`` is set to ``yes``, **every** failing job will be retried.
This can be a problem: for instance, for jobs that take a really long time
to run. To avoid this, you can use the ``auto-retry=no`` inline override
in the test plan to explicitly mark each job you do not wish to see
retried.

For example:

.. code-block:: yaml
  :caption: my_test_plan.pxu
  :emphasize-lines: 5

  id: foo-bar-and-froz
  _name: Tests Foo, Bar and Froz
  include:
    foo
    bar     auto-retry=no
    froz

In this case, even if the job ``bar`` fails and auto-retry is activated, it
will not be retried.
