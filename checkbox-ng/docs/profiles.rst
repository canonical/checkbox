Profiles configuration
^^^^^^^^^^^^^^^^^^^^^^

Checkbox-gui supports execution profiles via a predefined set of configuration
options that allow customization of the welcome screen, displayed whitelists
as well as saving results locally or sending the submission file to Launchpad
or to the Certification database/HEXR. 

The profile settings are part of a launcher script and use checkbox-gui as a
shebang to interpret the key/values.

As checkbox-gui is a Qt application, settings must follow the INI-style rules
of the `QSettings <http://qt-project.org/doc/qt-5/QSettings.html>`_ class.

Multilines values are supported but must be enclosed in doubles quotes and extra
lines must start with one space, e.g:

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

Supported Settings
==================

welcome/title
------------
 * QML app title and welcome screen header
 * default: "System Testing"

welcome/text
------------
 * Welcome message to display on the first screen (Rich text allowing HTML-style markup)
 * default: "<p>Welcome to System Testing.</p> [...]"

suite/whitelist_filter
----------------------
 * Regular expression to match a subset of whitelist filenames
 * default: .*

submission/message
------------------
 * Header text of the Submission Popup

submission/input_type
---------------------
 * Show a Text input field to enter the secure ID or the LP adress (default).
   To just save the results to disk, must use the "none" value.

submission/regex
----------
 * RegExpValidator, default ".*"

submission/input_placeholder
----------------------------
 * "Launchpad E-Mail Address" (default) or "Secure ID (15 or 18 characters)" 

submission/secure_id
--------------------
 * Preset value of the secure ID

submission/ok_btn_text
----------------------
 * "Submit Results" (default) or "Save Results"

submission/cancel_warning
-------------------------
 * "You are about to exit this test run without saving your results report.  Do you want to save the report?"

submission/submit_to_hexr
-------------------------
 * Boolean, add an extra header to also send the results to HEXR (works with
   the certification transport)

exporter/xml_export_path
------------------------
 * location to save the XML submission file, if set to an empty string will open a FileSaveDialog.
 * default: "/tmp/submission.xml"

transport/submit_to
-------------------
 *  Transport endpoint
 *  default: ""
 *  Supports submission to LP (the default), "certification", or "local" (save to disk)
