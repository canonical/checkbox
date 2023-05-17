=============
Exporter Unit
=============

The purpose of exporter units is to provide an easy way to customize the
plainbox reports by delegating the customization bits to providers.

Each exporter unit expresses a binding between code (the entry point) and data.
Data can be new options, different Jinja2 templates and/or new paths to load
them.

File format and location
------------------------

Exporter entry units are regular plainbox units and are contained and shipped
with plainbox providers. In other words, they are just the same as job and test
plan units, for example.

Fields
------

Following fields may be used by an exporter unit.

``id``:
    (mandatory) - Unique identifier of the exporter. This field is used to look
    up and store data so please keep it stable across the lifetime of your
    provider.

``summary``:
    (optional) - A human readable name for the exporter. This value is
    available for translation into other languages. It is used when listing
    exporters. It must be one line long, ideally it should be short (50-70
    characters max).

``entry_point``:
    (mandatory) - This is a key for a pkg_resources entry point from the
    plainbox.exporters namespace.
    Allowed values are: jinja2, text, xlsx, json and rfc822.

``file_extension``:
    (mandatory) - Filename extension to use when the exporter stream is saved
    to a file.

``options``:
    (optional) - comma/space/semicolon separated list of options for this
    exporter entry point. Only the following options are currently supported.

    text and rfc822:
        - with-io-log
        - squash-io-log
        - flatten-io-log
        - with-run-list
        - with-job-list
        - with-resource-map
        - with-job-defs
        - with-attachments
        - with-comments
        - with-job-via
        - with-job-hash
        - with-category-map
        - with-certification-status

    json:
        Same as for *text* and additionally:

        - machine-json

    xlsx:
        - with-sys-info
        - with-summary
        - with-job-description
        - with-text-attachments
        - with-unit-categories

    jinja2:
        - without-session-desc

``data``:
    (optional) - Extra data sent to the exporter code, to allow all kind of
    data types, the data field only accept valid JSON. For exporters using the
    jinja2 entry point, the template name and any additional paths to load
    files from must be defined in this field. See examples below.

Example
-------

This is an example exporter definition::

    unit: exporter
    id: my_html
    _summary: Generate my own version of the HTML report
    entry_point: jinja2
    file_extension: html
    options:
     with-foo
     with-bar
    data: {
     "template": "my_template.html",
     "extra_paths": [
         "/usr/share/javascript/lib1/",
         "/usr/share/javascript/lib2/",
         "/usr/share/javascript/lib3/"]
     }

The provider shipping such unit can be as follow::

    ├── data
    │   ├── my_template.css
    │   └── my_template.html
    ├── units
        ├── my_test_plans.pxu
        └── exporters.pxu

Note that exporters.pxu is not strictly needed to store the exporter units, but
keeping them in a dedicated file is a good practice.

How to use exporter units?
--------------------------

In order to call an exporter unit from provider foo, you just need to use in in
the launcher.

Example of a launcher using custom exporter unit::

    #!/usr/bin/env checkbox-cli

    [launcher]
    launcher_version = 1

    [transport:local_file]
    type = file
    path = /tmp/submission.html

    [exporter:my_html]
    unit = com.foo.bar::my_html

    [report:local_html]
    transport = local_file
    exporter = my_html

For more information about generating reports see :ref:`generating-reports`
