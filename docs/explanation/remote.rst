.. _remote:

Checkbox Remote
^^^^^^^^^^^^^^^

It is possible to run Checkbox tests on a device that you don't or cannot have
traditional control over (mouse/keyboard).

By using Checkbox Remote facilities you can use Checkbox on one device
(the :term:`controller<Checkbox Controller>`) to control Checkbox running on a
different device (the :term:`agent<Checkbox Agent>`).

This is especially useful on headless devices.

Comparison with SSH
===================

Although it is possible to connect to a device using SSH and run Checkbox
locally on it, if the device doesn't offer screen-like functionality then the
Checkbox session might have to be started over if the connection to the device
is lost.

When a UI is drawn a lot of data is transmitted through the network. Checkbox
Remote sends lean data only.

Nomenclature
============

Checkbox Agent
  See :term:`Checkbox Agent` in the glossary.

Checkbox Controller
  See :term:`Checkbox Controller` in the glossary.

Invocation
==========

Agent
  ``checkbox-cli run-agent``

Controller
  ``checkbox-cli control HOST [/PATH/TO/LAUNCHER]``

  ``HOST`` can be an IP or a hostname that the controller can resolve.

  ``LAUNCHER`` (optional) a launcher file to use that exists somewhere on the
  machine you are using as the controller.

  Example:
    ``checkbox-cli control dut8.local /home/ubuntu/testplans/sutton-client``

Custom port
===========

By default, the Agent listens on port 18871. To change that ``--port`` option
can be used. The same option used on the Controller specifies which port to
connect to.

Examples:
  ``checkbox-cli run-agent --port 10101``

  ``checkbox-cli control dut8.local --port 10101``

.. _remote_session_control:

Session control
===============

While Controller is connected, sending ``SIGINT`` (pressing ``Ctrl-C``) to the
application invokes the interrupt screen which provides the following choices:

Nothing, continue testing (ESC)
  As the name implies, it returns to the session. You can press the ``Esc`` key
  to get the same result.

Stop the test case in progress and move on to the next
  Skip current test case and move to the next.

Pause the test session and disconnect from the agent (CTRL+C)
  Leave the session on the Agent running but let the Controller exit.
  Pressing ``Ctrl-C`` a second time will have the same effect. It is possible
  to reconnect to the Agent later on and resume the testing session.

Exit and stop the Checkbox service on the agent at 127.0.0.1
  Stop the current test session and terminate the Checkbox Agent. In
  addition, stop the Controller.

End this test session preserving its data and launch a new one
  Stop the current session on the Agent and mark it so it is not possible to
  resume it, then immediately start a new one. The Controller will be greeted
  with the test plan selection screen unless a launcher was used to bypass the
  selection screens, in which case a similar test session is immediately
  started.

Remote session characteristics
==============================

Differences between a remote session and a local one are:

* Unless the session is explicitly abandoned, Checkbox Agent always resumes
  the last session.
* After testing is done, Checkbox Agent starts a new session
* Submission is done from the Controller by default (use
  ``local_submission = No`` in launcher or config to change this).
* When the Controller reconnects mid interactive test, the test is restarted.
* Hitting ``Ctrl+C`` on the Controller does not interrupt the running test.
