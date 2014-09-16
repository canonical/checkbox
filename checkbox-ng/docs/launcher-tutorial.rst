Checkbox/plainbox launchers tutorial
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

This document provides an explanation of why launchers are necessary, what
you can achieve with them, and goes over several examples to better describe
their capabilities. For a detailed reference on which settings are supported
by launchers, and specific syntax for launcher files, look at
:doc:`/profiles`.


Legacy checkbox behavior control
================================

In the past, :term:`Checkbox`'s behavior was controlled by three mechanisms.

First, the functions of checkbox could be augmented by adding plugins.
For example, the ability to submit to certification website was added by
the checkbox-certification package using a plugin. The plugins included
by checkbox-certification and which add new behavior to base checkbox
were:

::

    /usr/share/checkbox-certification/plugins/certify_message.py
    /usr/share/checkbox-certification/plugins/submission_info.py
    /usr/share/checkbox-certification/plugins/backup.py
    /usr/share/checkbox-certification/plugins/certify_prompt.py
    /usr/share/checkbox-certification/plugins/certify_report.py
    /usr/share/checkbox-certification/plugins/certify_schemas.py

These added the way to prompt the user for submission-specific data, generate
the xml report, and other functions.

Next, the behaviors of the plugins could be configured or controlled
using configuration files, which are "cascaded". A config file can
include others and those can in turn include others.

This is an example of a project-specific project-qt.ini main config file. It's
the first file read when the project-specific client is launched. Some settings
are abbreviated:

::
    
    [DEFAULT]
    includes = %(checkbox_oem_share)s/configs/checkbox-project-base-qt.ini %(checkbox_project_share)s/configs/checkbox-project-base.ini
    
    [checkbox/plugins/environment_info]
    repositories = deb http://.*\(archive\|security\).ubuntu.com/ubuntu precise-security
    routers = multiple
    server_iperf = 10.20.30.40
    sources_list = /etc/apt/sources.list
    wpa_n_psk = password
    wpa_n_ssid = access-point
    
    [checkbox/plugins/user_interface]
    title = My project System Testing

Notice the includes line, this instructs it to load the config file for
checkbox-project-base-qt and checkbox-project-base. Checkbox-project-base-qt
loads the configs for checkbox-certification and checkbox-project. Settings are
cascaded so the config options near the top override the ones near the
bottom.

Finally, the "binary" used to invoke checkbox is a shell script that
defines where to find the things checkbox needs to run: you can define a
share directory, a specific data directory, point to a configuration
file and define some environment variables that you may need during
testing. Here's an example for checkbox-project-qt:

::

    #!/bin/bash
    export CHECKBOX_DATA=${CHECKBOX_DATA:-~/.checkbox}
    export CHECKBOX_SHARE=${CHECKBOX_SHARE:-/usr/share/checkbox}
    export CHECKBOX_OPTIONS=${CHECKBOX_OPTIONS:---log-level=debug --log=$CHECKBOX_DATA/checkbox-project.log}
    export CHECKBOX_CERTIFICATION_SHARE=${CHECKBOX_CERTIFICATION_SHARE:-/usr/share/checkbox-certification}
    export CHECKBOX_OEM_SHARE=${CHECKBOX_PROJECT_BASE_SHARE:-/usr/share/checkbox-project-base}
    export CHECKBOX_PROJECT_SHARE=${CHECKBOX_PROJECT_SHARE:-/usr/share/checkbox-project}
    
    # Convenience for defining the PYTHONPATH directory.
    if [ "$CHECKBOX_SHARE" != "/usr/share/checkbox" ]; then
        export PYTHONPATH="$CHECKBOX_SHARE:$PYTHONPATH"
    fi
    
    python3 $CHECKBOX_SHARE/run "$@" $CHECKBOX_PROJECT_SHARE/configs/$(basename $0).ini

Here you can see that it defines some locations and an important part is
the final python3 line, where it will locate and use the required .ini
config file we saw earlier.

This hierarchical organization was very powerful but was also difficult
to handle, and also had some limitations. Part of the work we did with
checkbox was to integrate all the project-specific plugins into checkbox
trunk, this way all the core code is in one place, and the project-specific
variants only supply jobs, whitelists, data and configuration, without adding
new behavior.

New plainbox behavior control
=============================

Unlike checkbox, plainbox's core is monolythic, and it has no concept of
plugins. This makes it easier to understand and work with. The plainbox
core has implementations for all the functions in the old checkbox
packages, so no additions are necessary to use features such as
submission to certification or report generation.


What we call plainbox is the library that implements all the
functionality, as can be seen :doc:`here</stack>`.

Plainbox provides tools to help test developers write and package tests.
These are delivered in "providers", which are entities designed to
encapsulate test descriptions, custom scripts for testing, whitelists
and assorted data. They were designed to allow teams to
write and deliver their custom tests without worrying too much about the
underlying plainbox code.

To get information on how to write tests and providers, see the :ref:`Provider
Tutorial<tutorial>`

However, when actually using these tests to verify a real system, we
wanted to provide something easier and closer to the user experience of
checkbox. We created two clients, checkbox-gui and checkbox-cli, which
had some hardcoded behaviors, and we also started creating other clients
which were based on these but were purpose specific. For instance, we
had a version of checkbox for SRU testing, another for server
certification, and so on.

But then we realized that a lot of the code was duplicated and the
behaviors were common except for a few changes. So we came up with the
concept of "launchers", which are somewhat similar to checkbox's
configuration files and shell script launchers.

The idea is that checkbox-gui and checkbox-cli have some very basic
behaviors, since they are the clients that are shipped by default with
ubuntu. They can show all the available whitelists, show a predefined
welcome message, and at the end will let the user see the html report
and submit it to launchpad using their e-mail address, similar to the
version of checkbox that shipped with Ubuntu.

Instead of using complicated command line switches, launchers allow you
to configure some optional behaviors to customize your testing
experience. A launcher contains settings, and is similar to a shell
script, but the interpreter will be either checkbox-gui or
checkbox-launcher.

Here are a few examples of what can be done with launchers.

As a surprise, checkbox-cli is itself a launcher:

::

    #!/usr/bin/env checkbox-launcher
    [welcome]
    text = Welcome to System Testing!
        Checkbox provides tests to confirm that your system is working properly.
        Once you are finished running the tests, you can view a summary report for
        your system.
        Warning: Some tests could cause your system to freeze or become
        unresponsive. Please save all your work and close all other running
        applications before beginning the testing process.
    
    [suite]
    whitelist_filter = ^default$
    whitelist_selection = ^default$
    skip_whitelist_selection = True
    
    [transport]
    submit_to = launchpad

You can see here we customize a few options: it shows a welcome message,
automatically selects the default whitelist, and will submit to
launchpad when it's finished.

A graphical launcher example is canonical-certification-client.

::

    #!/usr/bin/checkbox-gui
    
    [welcome]
    title = "System Certification"
    text = "<p>Welcome to System Certification!</p><p></p><p>This application will
    gather information from your system. Then you will be asked manual tests to
    confirm that the system is working properly. Finally, you will be asked for
    the Secure ID of the computer to submit the information to the certification
    database.</p><p></p><p> To learn how to create or locate the Secure ID,
    please see here: <a href=\"https://certification.canonical.com\">certification.canonical.com</a></p><p></p>"
    
    [suite]
    whitelist_filter = "^client-(cert|selftest).*"
    
    [submission]
    input_type = "regex"
    input_placeholder = "Secure ID (15 or 18 characters)"
    ok_btn_text = "Submit Results"
    submit_to_hexr = "true"
    
    [exporter]
    xml_export_path = "/tmp/submission.xml"
    
    [transport]
    submit_to = "certification"


Graphical launchers are a bit more complicated, but essentially it's
similar, what it allows is for you to define some parameters to
customize your testing experience.

A very simple text-mode launcher is canonical-hw-collection which just
runs the basic hardware information tests and uploads them to a hardware
database:

::

    [welcome]
    title = Gathering hardware information
    text = Gathering hardware information.  You may be prompted for your password.
           This process will take approximately 30 seconds and you will be provided
           with a URL through which you can confirm and register your hardware
           submission.
    
    [suite]
    whitelist_filter = ^hwsubmit$
    whitelist_selection = ^hwsubmit$
    skip_whitelist_selection = True
    skip_test_selection = True
    
    [submission]
    # A bogus secure_id ensures we don't ask it
    # It can always be overridden in the .conf file.
    secure_id = 000
    
    [transport]
    submit_to = certification
    submit_url = https://hardware-server.example.com/

FInally, canonical-driver-test-suite provides both a graphical and a
text mode launcher, which are functionally equivalent:

::

    #!/usr/bin/checkbox-gui
    
    [welcome]
    title = "Canonical Driver Test Suite"
    text = "<p>Welcome to the Canonical Driver Test Suite.</p>
     <p></p>
     <p>This program contains automated and manual tests to help you discover
     issues that will arise when running your device drivers on Ubuntu.</p>
     <p></p>
     <p>This application will step the user through these tests in a
     predetermined order and automatically collect both system information as
     well as test results. It will also prompt the user for input when manual
     testing is required.</p>
     <p></p>
     <p>The run time for the tests is determined by which tests you decide to
     execute. The user will have the opportunity to customize the test run to
     accommodate the driver and the amount of time available for testing.</p>
     <p></p>
     <p>To begin, simply click the Continue button below and follow the onscreen
     instructions.</p><p></p>"
    
    [suite]
    whitelist_filter = "^ihv-.*"
    
    [submission]
    ok_btn_text = "Save Results"
    input_type = "none"
    
    [exporter]
    xml_export_path = ""
    
    [transport]
    submit_to = "local"

Text mode:

::

    #!/usr/bin/env checkbox-launcher
    [welcome]
    text = Welcome to the Canonical Driver Test Suite
        This program contains automated and manual tests to help you discover
        issues that will arise when running your device drivers on Ubuntu.
        This application will step the user through these tests in a
        predetermined order and automatically collect both system information as
        well as test results. It will also prompt the user for input when manual
        testing is required.
        The run time for the tests is determined by which tests you decide to
        execute. The user will have the opportunity to customize the test run to
        accommodate the driver and the amount of time available for testing.
        To begin, simply click the Continue button below and follow the onscreen
        instructions.
    
    [suite]
    # Whitelist(s) displayed in the suite selection screen
    whitelist_filter = ^ihv-.*
    # Whitelist_selection is mandatory so we set it to a bogus value so
    # no whitelists are preselected.
    whitelist_selection = bogus
