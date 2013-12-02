ChangeLog
=========

.. note::
    This changelog contains only a summary of changes. For a more accurate
    accounting of development history please inspect the source history
    directly.

PlainBox 0.4 beta 2
^^^^^^^^^^^^^^^^^^^

* Bugfixes: https://launchpad.net/checkbox/+milestone/plainbox-0.4b2

PlainBox 0.4 beta 1
^^^^^^^^^^^^^^^^^^^

* Lots of production usage, bug fixes and improvements. Too many to
  list here but we shipped one commercial product on top of plainbox
  and it basically works.
* Better internal abstractions, job runner, execution controller,
  session state controller, session manager, suspend and resume
  Helpers, on-disk format version and upgrade support. Lots of very
  important internal plumbing done better to improve maintainability
  of the code.
* Switched from a model where checkbox and plainbox are tied closely
  together to a model where plainbox is a back-end for multiple
  different products and job definitions (all kinds of "test
  payload") is orthogonal to the interaction/work-flow/user
  interface.  This opens up the path for a separate "test payload
  market" to form around plainbox where various projects can just
  focus on producing and maintaining tests rather than complete
  solutions by themselves. Such parties don't have to coordinate with
  anyone or manage their code inside our repository.
* Generalized the trusted launcher concept to run any job wrapped
  inside a job provider. This allows any job, regardless where it is
  coming from, to run as another user securely and easily.
* DBus service (present throughout the development cycle) moved to
  checkbox-ng as it was not mature enough. Makes plainbox easier to
  test by hiding the complexity in another project. Not sure if we
  keep the DBus interface though so this was a good move for the core
  itself.

PlainBox 0.3
^^^^^^^^^^^^

* Added support for all job types (manual, user-interact, user-verify, attachment, local)
* Added support for running as another user
* Added support for creating session checkpoints and resuming testing across reboots
* Added support for exporting test results to JSON, plain text and XML
* Added support for handling binary data (eg, binary attachments)
* Added support for using sub-commands to the main plainbox executable
* Added documentation to the project 
* Numerous internal re-factorings, changes and improvements.
* Improved unit and integration testing coverage

PlainBox 0.2
^^^^^^^^^^^^

* Last release made from the standalone github tree.
* Added support for discovering dependencies and automatic dependency
  resolution (for both job dependencies and resource dependencies)

PlainBox 0.1
^^^^^^^^^^^^

* Initial release
