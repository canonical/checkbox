==========================
PLAINBOX_PROVIDER_DATA (7)
==========================

Synopsis
========

``command: example-command $PLAINBOX_PROVIDER_DATA/data-file.dat``

Running an example-command on a provider-specific data file.

Description
===========

Plainbox providers can require arbitrary data files for successful testing.
The absolute path of the provider ``data/`` directory is exposed as the
environment variable ``$PLAINBOX_PROVIDER_DATA``. Job commands can use that
variable to refer to the data directory in an unambiguous way.

Typical Use Cases
-----------------

Typically the data file is used by the job command. For example, let's say that
an audio file ``test.wav`` is stored in the ``data/`` directory of the provider
and the intent is to have a job definition which plays that file::

    id: play-audio-file
    plugin: user-verify
    summary: play the test.wav file
    command: paplay $PLAINBOX_PROVIDER_DATA/test.wav
    description:
     Plays the test sound file (test.wav)

     Did the sound file play correctly?

The job ``play-audio-file`` will use the ``paplay`` (1) executable to play an
audio file shipped by the provider. Since the actual location of the audio file
may vary, depending on environment and installation method, the test definition
uses the environment variable ``$PLAINBOX_PROVIDER_DATA`` to access it in an
uniform way.

Checkbox Compatibility
----------------------

Jobs designed to work with pre-Plainbox-based Checkbox may still refer to the
old, somewhat confusing, environment variable :doc:`CHECKBOX_SHARE`. It points
to the same directory.

See Also
========

:doc:`PLAINBOX_PROVIDER_DATA`
