.. _envvar:

Environment variables set by Checkbox
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Checkbox sets a few environment variables during execution. These can be
used in the job definition itself or even in the script called by the
``command`` field of a the job.

``PLAINBOX_SESSION_SHARE``
    Path to a directory that can be used to store temporary data during the
    test run. This is useful if you have one test gathering data, and another
    one checking said data. For example, the first test would write its
    output to ``$PLAINBOX_SESSION_SHARE/my_test_output``, and the other one
    would retrieve the content of the file to analyze it.

``PLAINBOX_PROVIDER_DATA``
    Directory within the provider that contains additional data required by
    some jobs. For instance, the `Base provider data directory`_ contains
    files used to assign the GPIO pins specific to some hardware.

``CHECKBOX_RUNTIME``
    Directory where the Checkbox runtime is located. This is especially useful
    when in a snap environment where test authors may need to point to specific
    files within the runtime environment. For example, when using the
    checkbox24 snap, the runtime is ``/snap/checkbox24/current``.

``CHECKBOX_RUNNING_STRICT_SNAP``
    Defined when Checkbox is running from a strict snap with value ``1``.
    Can be used to detect if the job is running inside a snap namespace or not.

``CHECKBOX_OS_IS_UBUNTUCORE``
    Defined when Checkbox is running on a Ubuntu Core system with value ``1``.
    Can be used to change the behaviour of testing on Ubuntu Core.

.. _Base provider data directory: https://github.com/canonical/checkbox/tree/main/providers/base/data
