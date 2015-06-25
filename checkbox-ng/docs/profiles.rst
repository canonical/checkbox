Profiles configuration
^^^^^^^^^^^^^^^^^^^^^^

Execution profiles, or launchers, allow specifying a predefined set of
configuration options that allow customization of the welcome screen, displayed
whitelists as well as saving results locally or sending the submission file to
Launchpad or to the Certification database/HEXR, as well as some other
parameters.

The profile settings are part of a launcher script and use either checkbox-gui
or checkbox-launcher (in text-mode/CLI) as a shebang to interpret the
key/values.

This document provides a reference on launcher functionality and syntax. To
understand the design and concepts and see several examples, you may want to
read the :doc:`tutorial</launcher-tutorial>` on how to create launchers and
their relationship with legacy :term:`Checkbox`.

Syntax
======

As checkbox-gui is a Qt application, settings must follow the INI-style rules
of the `QSettings <http://qt-project.org/doc/qt-5/QSettings.html>`_ class.

Multiple-line values are supported but must be enclosed in doubles quotes and
extra lines must start with one space, e.g:

.. code-block:: bash

    [category]
    key = "Hello
     World"


- From QML:

.. code-block:: bash

    settings.value("category/key", i18n.tr("default_value"))

- From C++:

.. code-block:: bash

    settings->value("category/key", app.tr("default_value"))

Conversely, checkbox-launcher-specific launchers must follow `Python
ConfigParser
<https://docs.python.org/3/library/configparser.html#supported-ini-file-structure>`_
syntax.

Also, some settings only make sense for either GUI or CLI, and are thus not
understood by the other. These are noted below.

Supported Settings
==================

welcome/title
    QML application title and welcome screen header. Defaults to ``System
    Testing``.

welcome/text
    Welcome message to display on the first screen (checkbox-gui supports Rich text
    allowing HTML-style markup). Defaults to ``<p>Welcome to System Testing.</p>
    [...]``

suite/whitelist_filter
    Regular expression to match a subset of whitelist filenames. On
    checkbox-gui it defaults to ``.*``. For checkbox-launcher it has no default
    and *must* be defined.


suite/whitelist_selection
    Pattern that whitelists need to match to be preselected. Python regular
    expression. It has no default and *must* be defined.  (CLI only)

suite/skip_whitelist_selection
    If set to true, user will not receive a choice of whitelist. Only
    the preselected ones (see whitelist_selection) will be selected.
    (CLI only).

suite/skip_test_selection
    If set to true, user will not be allowed to deselect tests prior to run:
    all tests in the selected whitelist will be run. (CLI only)

submission/message
    Header text of the submission pop-up , shown to the
    user after submission has completed. (GUI only)

submission/input_type
    Show a Text input field to enter the secure ID or the LP address
    (default).  To just save the results to disk, must use the
    ``none`` value. To validate using a regex, must be ``regex``.
    (GUI only)

submission/regex
    Regular expression to validate input in submission field (e.g.
    email, secure_id) if input_type is regex. (GUI only).
    RegExpValidator, default ``.*``

submission/input_placeholder
    Temporary text to put in input field, used to guide the user.
    ``Launchpad E-Mail Address`` (default) or ``Secure ID (15 or 18
    characters)``. (GUI only)

submission/secure_id
    Preconfigured secure_id to fill in the text field.

submission/ok_btn_text
    The label for the "Send" button. ``Submit Results`` (default) or
    ``Save Results``. (GUI only)

submission/cancel_warning
    Show to the user if he wants to exit without having saved the
    report. You are about to exit this test run without saving your
    results report. Do you want to save the report? (GUI only)

submission/submit_to_hexr
    Boolean, add an extra header to also send the results to HEXR
    (works with the certification transport)

exporter/xml_export_path
    Location to save the XML submission file, if set to an empty
    string will open a file save dialog. Default:
    ``/tmp/submission.xml``
    (GUI only)

transport/submit_to
    Transport endpoint. Defaults to ``<none>``.  Supports submission
    to LP (the default, value ``launchpad``), ``certification``, or
    ``local`` (save to disk)

transport/submit_url
    URL to submit results to. This allows to upload to different
    websites, for example it can upload directly to hexr, or to the
    staging sites. Used only with the ``certification`` submit_to
    value.

transport/config_filename
    Name of a custom config file to load. Config files are mainly
    used to define environment variables. (CLI only)

transport/dont_suppress_output
    If set, resources, local jobs and attachments will be output to
    screen, this generates a lot of text and is mainly for debugging.
    (CLI only)


