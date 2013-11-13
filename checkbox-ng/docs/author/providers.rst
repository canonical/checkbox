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

The format for the provider name is an RFC3720 IQN. This is specified in :rfc:`3720#section-3.2.6.3.1`. 

Then the directory specified in location should contain at least one of the following directories:

jobs
  Should contain one or more files in the Checkbox job format.

bin
  Should contain one or more executable programs.

data
  Can contain any files that may be neccesary for implementing the jobs contained in the provider, e.g. image files.

whitelists
  Should contain one or more files in the Checkbox whitelist format.
