ChangeLog
=========

.. note::
    This changelog contains only a summary of changes. For a more accurate
    accounting of development history please inspect the source history
    directly.

PlainBox 0.5a1
^^^^^^^^^^^^^^

.. note::

    The 0.5 release is not finalized and the list below is incomplete.

New Features
------------

* PlainBox is now a better development tool for test authors. With the new
  'plainbox startprovider' command it is easy to bootstrapp  development of
  third party test collections. This is further explained in the new
  :ref:`tutorial`.

Workflow Changes
----------------

* PlainBox dropped support for Ubuntu 13.04 (Raring Rigtail), following
  scheduled end-of-life of that release.
* PlainBox dropped support for Ubuntu 13.10 (Saucy Salamander) given the
  imminent release of the next release.
* PlainBox now supports Ubuntu 14.04 (Trusty Thar), scheduled for release on
  the 17th of April 2014.

This implies that any patch merged into trunk is only tested on Ubuntu 12.04
(with python3.2) and Ubuntu 14.04 (with python3.3, which will switch to python
3.4 later, before the final release.)

Internal Changes
----------------

General Changes
...............

* PlainBox now supports Python 3.4.

New Modules
...........

* PlainBox now has a dedicated module for implementing versatile command line
  utilities :mod:`plainbox.impl.clitools`. This module is used to implement the
  new :mod:`plainbox.provider_manager` which is what backs the per-provider
  management script.

API changes (WhiteLists)
........................

* PlainBox has new and improved APIs for loading whitelists
  :meth:`plainbox.impl.secure.qualifiers.WhiteList.from_string()` and
  :meth:`plainbox.impl.secure.qualifiers.WhiteList.from_file()`.
* PlainBox now tracks the origin of whitelist, knowing where they were defined
  in. Origin is available as
  :meth:`plainbox.impl.secure.qualifiers.WhiteList.origin`

API changes (Providers)
.......................

* PlainBox can validate providers, jobs and whitelists better than before. In
  particular, broken providers are now verbosely ignored. This is implemented
  as a number of additional validators on
  :class:`plainbox.impl.secure.providers.v1.Provider1Definition`
* PlainBox can now enumerate all the executables of a provider
  :meth:`plainbox.abc.IProvider1.get_all_executables()`
* PlainBox has new APIs for applications to load as much of provider content as
  possible, without stopping on the first encountered problem.
  :meth:`plainbox.impl.secure.providers.v1.Provider1.load_all_jobs()`
* The ``Provider1.load_jobs()`` method has been removed. It was only used
  internally by the class itself. Identical functionality is now offered by
  :class:`plainbox.impl.secure.plugins.FsPlugInCollection` and
  :class:`plainbox.impl.secure.providers.v1.JobDefinitionPlugIn`.

API changes (Qualifiers)
........................

* PlainBox now has additional APIs that correctly preserve order of jobs
  selected by a :term:`WhiteList`, see:
  :func:`plainbox.impl.secure.qualifiers.select_jobs`.
* PlainBox has new APIs for converting any qualifier into a list of primitive
  (non-divisible) qualifiers that express the same selection,
  :meth:`plainbox.abc.IJobQualifier.get_primitive_qualifiers()` and
  :meth:`plainbox.abc.IJobQualifier.is_primitive()`.
* PlainBox has new APIs for qualifiers to uniformly include and exclude jobs
  from the selection list. This is implemented as a voting system described in
  the :meth:`plainbox.abc.IJobQualifier.get_vote()` method.

API changes (Other)
...................

* :class:`plainbox.impl.secure.plugins.FsPlugInCollection` can now load plug-ins
  from files of various extensions. The ``ext`` argument can now be a list of
  extensions to load.
* :class:`plainbox.impl.secure.plugins.FsPlugInCollection` now takes a list of
  directories instead of a PATH-like argument that had to be split with the
  platform-specific path separator.
* :class:`plainbox.impl.secure.rfc822.Origin` gained the
  :meth:`plainbox.impl.secure.rfc822.Origin.relative_to()` method which is
  useful for presenting origin objects in a human-friendly form.
* Implementations of :class:`plainbox.impl.secure.plugins.IPlugIn` can now
  raise :class:`plainbox.impl.secure.plugins.PlugInError` to prevent being
  added to a plug-in collection.
* :class:`plainbox.impl.secure.config.Config` gained
  :meth:`plainbox.impl.secure.config.Config.get_parser_obj()` and
  :meth:`plainbox.impl.secure.config.Config.write()` which allow configuration
  changes to be written back to the filesystem.
* :class:`plainbox.impl.secure.config.Config` now has special support for the
  new :class:`plainbox.impl.secure.config.NotUnsetValidator`. Unlike all other
  validators, it is allowed to inspect the special
  :data:`plainbox.impl.secure.config.Unset` value.

Bug fixes
---------

* Bugfixes: https://launchpad.net/checkbox/+milestone/plainbox-0.5a1

PlainBox 0.4
^^^^^^^^^^^^

* Bugfixes: https://launchpad.net/checkbox/+milestone/plainbox-0.4

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
