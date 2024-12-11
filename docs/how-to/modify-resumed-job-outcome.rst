Modify the outcome of a job when the session is resumed
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

By default, when a test session is resumed automatically, the outcome of the
last job run is set to:

* ``pass`` if the job has the ``noreturn`` flag set (it was expected that the
  session would be interrupted)
* ``crashed`` if the job does not have the ``noreturn`` flag (something
  happened during the execution of the test that crashed the device)

However, it is possible to modify this behavior by placing a ``__result`` file
in the ``$PLAINBOX_SESSION_SHARE`` directory before the session is interrupted.

The ``_result`` file is a JSON document that looks like this:

.. code-block:: json

  {
    "outcome": "fail",
    "comments": "This test failed because..."
  }

``outcome`` can take the following values:

* ``pass``
* ``fail``
* ``skip``

The next time Checkbox is started and the session is automatically resumed,
Checkbox will set the outcome and the comments for the last job run based on
the content of that ``__result`` file.
