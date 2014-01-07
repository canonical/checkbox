=========
Providers
=========

Providers are entities which provide Plainbox with jobs, scripts and whitelists, as well as miscellaneous data that may be used by tests. They work
by providing a configuration file which tells Plainbox the name and location of the provider. The provider needs to install this file to 
`/usr/share/plainbox-providers-1` (alternatively they can be placed in `~/.local/share/plainbox-providers-1`).

An example of such a file is::

    [PlainBox Provider]
    name = 2013.com.canonical:myprovider
    location = /usr/lib/plainbox-providers-1/myprovider
    description = My Plainbox test provider

It has these fields:

* name
    The format for the provider name is an RFC3720 IQN. This is specified in 
    :rfc:`3720#section-3.2.6.3.1`. It is used by PlainBox to uniquely identify 
    the provider.

* location
    The filesystem path where the providers directories are installed. This 
    location should contain at least one of the following directories:

    * jobs
        Should contain one or more files in the Checkbox job file format.
    * bin
        Should contain one or more executable programs.
    * data
        Can contain any files that may be neccesary for implementing the jobs 
        contained in the provider, e.g. image files.
    * whitelists
        Should contain one or more files in the Checkbox whitelist format.

* description
    A short description of the provider.

Tutorial
========

To best illustrate how providers work, we will walk through creating one 
step-by-step. At the end of this tutorial you will have a provider which 
adds a new whitelist, several new jobs and the scripts and test data 
supporting those jobs.

#. Create a directory with name of your provider - something like 
   plainbox-provider-mytestsuite. This will contain your provider file and 
   the directories containing your whitelist, jobs, scripts and data.

#. Next we need to create the provider file, name it with the .provider 
   extension, e.g. mytestsuite.provider. Its contents should be::

    [PlainBox Provider]
    name = 2013.com.canonical:mytestsuite
    location = /usr/lib/plainbox-providers-1/mytestsuite/
    description = Tutorial provider

#. We start off by creating a directory for the job files - this needs to be 
   called ``jobs``. We can then add a job file here, something like 
   ``myjobs.txt``. It can contain a few simple jobs like this::

    plugin: shell
    name: myjobs/builtin_command
    command: true
    _description:
     An example job that uses built in commands.

    plugin: shell
    name: myjobs/this_provider_command
    command: mycommand
    _description:
      An example job that uses a test command provided by this provider.

    plugin: shell
    name: myjobs/other_provider_command
    command: removable_storage_test usb -l
    _description:
     An example job that uses a test command provided by another provider.

#. Next we need to create a directory called ``bin`` to contain the command 
   used by the job ``myjobs/this_provider_command``. We then create a file 
   there called ``mycommand`` which contains the following text::

    !#/usr/bin/bash
    test `cat $CHECKBOX_SHARE/data/testfile` == 'expected'

   You'll notice the command uses a file in ``$CHECKBOX_SHARE/data`` - we'll
   add this file to our provider next.

#. Because the command we're using uses a file that we expect to be located in
   ``$CHECKBOX_SHARE/data``, we need to add this file to our provider so that
   after the provider is installed this file is available in that location. 
   First we need to create a directory called ``data``, then as indicated by 
   the  contents of the script we wrote in the previous step, we need to create
   a file there called ``testfile`` with the contents::

    expected

   As simple as that!

#. Lastly we need to add a whitelist that utilizes the jobs we created
   earlier. This whitelist can include jobs from other providers as well
   (and needs to include at least one from the default provider in fact).
   We need to create a directory called ``whitelists`` and add a file called
   ``mywhitelist.whitelist``. The contents should be::

    miscellanea/submission_resources
    myjobs/builtin_command
    myjobs/other_provider_command
    myjobs/this_provider_command
    graphics/glxgears

   The ``miscellanea/submission_resources`` and ``graphics/glxgears`` jobs
   are from the default provider that is part of PlainBox.

#. Now we have a provider that will work we just need to package it so
   that it puts everything in the right place to be found by PlainBox.
