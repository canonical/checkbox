ChangeLog
=========

.. note::
    This changelog contains only a summary of changes. For a more accurate
    accounting of development history please inspect the source history
    directly.

PlainBox 0.5b1
^^^^^^^^^^^^^^

.. note::

    The 0.5 release is not finalized and the list below is incomplete.

New Features
------------

* PlainBox is now a better development tool for test authors. With the new
  'plainbox startprovider' command it is easy to bootstrap  development of
  third party test collections. This is further explained in the new
  :ref:`tutorial`. The template is described in :doc:`provider template
  <author/provider-template>`.
* Test providers now control namespaces for job definitions, allowing test
  authors to freely name job definitions without any central coordination
  authority. See more about :doc:`provider namespaces
  <author/provider-namespaces>`.
* PlainBox is now fully internationalized, making it possible to translate all
  of the user interface. Certain extensible features such as commands and test
  job providers are also translatable and can be shipped by third party
  developers. All the translations are seamlessly enabled, even if they come
  from different sources. See more about :doc:`provider internationalization
  <author/provider-i18n>`.

Command Line Interfaces Changes
-------------------------------

* The -c | --checkbox option was removed. It used to select which "provider" to
  load (out of packaged providers, special source provider and special stub
  provider) but with the introduction of :term:`namespaces <namespace>` this
  option became meaningless. To support a subset of reasons why it was being
  used a new option was added in its place. The new --providers option can
  decide if plainbox will load **all** providers (default), just the special
  **src** provider or just the special **stub** provider. We hope that nobody
  will need to use this option.

* The ``plainbox run -i``, ``plainbox dev analyze -i`` and similar
  --include-patterns options no longer works with simple job definition
  identifier patterns. It now requires fully qualified patterns that also
  include the name-space of the defining provider. In practical terms instead
  of ``plainbox run -i foo`` one needs to use ``plainbox run -i
  2013.example.com::foo``. If one really needs to run *any* job ``foo`` from
  any provider that can be achieved with ``plainbox run -i '.*::foo'``.

Workflow Changes
----------------

* PlainBox is now available in Debian as the ``python3-plainbox`` and
  ``plainbox`` packages. Several of the Checkbox project developers are
  maintaining packages for the core library, test providers and whole test
  applications.
* PlainBox dropped support for Ubuntu 13.04 (Raring Rigtail), following
  scheduled end-of-life of that release.
* PlainBox dropped support for Ubuntu 13.10 (Saucy Salamander) given the
  imminent release of the next version of Ubuntu.
* PlainBox now supports Ubuntu 14.04 (Trusty Thar), scheduled for release on
  the 17th of April 2014.

This implies that any patch merged into trunk is only tested on Ubuntu 12.04
(with python3.2) and Ubuntu 14.04 (with python3.3, which will switch to python
3.4 later, before the final release.)

Internal Changes
----------------

General Changes
...............

* PlainBox now supports Python 3.4. This includes existing support for Python
  3.2 and 3.3. Effective Ubuntu coverage now spans two LTS releases.
  This will be maintained until the end of Ubuntu 12.04 support.

New Modules
...........

* PlainBox now has a dedicated module for implementing versatile command line
  utilities :mod:`plainbox.impl.clitools`. This module is used to implement the
  new :mod:`plainbox.provider_manager` which is what backs the per-provider
  management script.
* The new :mod:`plainbox.provider_manager` module contains the implementation
  of the ``manage.py`` script, which is generated for each new provider. The
  script implements a set of subcommands for working with the provider from a
  developer's point of view. 
* The vendor package now contains a pre-release version of
  :mod:`~plainbox.impl.vendor.textland` - a text mode, work-in-progress,
  compositor for console applications. TextLand is used to implement certain
  screens displayed by checkbox-ng. This makes it easier to test, easier to
  develop (without having to rely on complex curses APIs) and more portable as
  the basic TextLand API (to display a buffer and provide various events) can
  be implemented on many platforms.

API changes (Job Definitions)
.............................

* PlainBox now offers two new properties for identifying (naming) job
  definitions, :meth:`plainbox.impl.job.JobDefinition.id` and
  :meth:`plainbox.impl.job.JobDefinition.partial_id`. The ``id`` property is
  the full, effective identifier composed of ``partial_id`` and
  ``provider.namespace``, with the C++ scope resulution operator, ``::``
  joining both into one string. The ``partial_id`` field is loaded from the
  ``id`` key in  RFC822-like job definition syntax and is the part without the
  name-space. PlainBox now uses the ``id`` everywhere where ``name`` used to be
  used before. If the ``id`` field (which defines ``partial_id`` is not present
  in a RFC822 job definition then it defaults to ``name`` making this change
  fully backwards compatible.
* The :meth:`plainbox.impl.job.JobDefinition.name` property is now deprecated.
  It is still available but is has been entirely replaced by the new ``id`` and
  ``partial_id`` properties. It will be removed as a property in the next
  release of PlainBox.
* PlainBox now offers the new :meth:`plainbox.impl.job.JobDefinition.summary`
  which is like a short, one line description of the provider. It should be
  used whenever a job definition needs to be listed (in user interfaces,
  reports, etc). It can be translated and a localized version is available as
  :meth:`plainbox.impl.job.JobDefinition.tr_summary()`
* PlainBox now offers a localized version of a job description as
  :meth:`plainbox.impl.job.JobDefinition.tr_description()`.

API changes (White Lists)
.........................

* PlainBox now offers new and improved APIs for loading whitelists
  :meth:`plainbox.impl.secure.qualifiers.WhiteList.from_string()` and
  :meth:`plainbox.impl.secure.qualifiers.WhiteList.from_file()`.
* PlainBox now tracks the origin of whitelist, knowing where they were defined
  in. Origin is available as
  :meth:`plainbox.impl.secure.qualifiers.WhiteList.origin`
* PlainBox can now optionally store and use the implicit name-space of a
  WhiteList objects. This name space will be used to qualify all the patterns
  that don't use the scope resolution operator ``::``.
  The implicit name-space is available as
  :meth:`plainbox.impl.secure.qualifiers.WhiteList.implicit_namespace`.

API changes (Providers)
.......................

* PlainBox can validate providers, jobs and whitelists better than before. In
  particular, broken providers are now verbosely ignored. This is implemented
  as a number of additional validators on
  :class:`plainbox.impl.secure.providers.v1.Provider1Definition`
* PlainBox can now enumerate all the executables of a provider
  :meth:`plainbox.abc.IProvider1.get_all_executables()`
* PlainBox now offers new APIs for applications to load as much of provider
  content as possible, without stopping on the first encountered problem.
  :meth:`plainbox.impl.secure.providers.v1.Provider1.load_all_jobs()`
* The ``Provider1.load_jobs()`` method has been removed. It was only used
  internally by the class itself. Identical functionality is now offered by
  :class:`plainbox.impl.secure.plugins.FsPlugInCollection` and
  :class:`plainbox.impl.secure.providers.v1.JobDefinitionPlugIn`.
* PlainBox now associates a gettext domain with each provider. This
  information is available both in
  :attr:`plainbox.impl.secure.providers.v1.Provider1Definition.gettext_domain`
  and :attr:`plainbox.impl.secure.providers.v1.Provider1.gettext_domain`
* PlainBox now derives a namespace from the name of the provider. The namespace
  is defined as  the part of the provider name up to the colon. For example
  provider name ``2013.com.canonical.ceritifaction:resources`` defines provider
  namespace ``2013.com.canonical.certification``. The computed namespace is
  available as :meth:`plainbox.impl.secure.providers.v1.Provider1.namespace`
* PlainBox now offers a localized version of the provider description string as
  :meth:`plainbox.impl.secure.providers.v1.Provider1.tr_description()`
* PlainBox now passes the provider namespace to both whitelist and job
  definition loaders, thus making them fully aware of the namespace they come
  from.
* The implementation of various directory properties on the
  :class:`plainbox.impl.secure.providers.v1.Provider1` class have changed. They
  are now explicitly configurable and are not derived from the now-gone
  ``location`` property. This affects 
  :meth:`plainbox.impl.secure.providers.v1.Provider1.jobs_dir`,
  :meth:`plainbox.impl.secure.providers.v1.Provider1.whitelists_dir`,
  :meth:`plainbox.impl.secure.providers.v1.Provider1.data_dir`,
  :meth:`plainbox.impl.secure.providers.v1.Provider1.bin_dir`, and the new
  :meth:`plainbox.impl.secure.providers.v1.Provider1.locale_dir`.  This change
  makes the runtime layout of each directory flexible and more suitable for
  packaging requirements of particular distributions.
* PlainBox now associates an optional directory with per-provider locale data.
  This allows it to pass it to ``bindtextdomain()``.  The locale directory is
  available as :meth:`plainbox.impl.secure.providers.v1.Provider1.locale_dir`.
* PlainBox now offers a utility method,
  :meth:`plainbox.impl.secure.providers.v1.Provider1.from_definition()`, to
  instantiate a new provider from
  :class:`plainbox.impl.secure.providers.v1.Provider1Definition`
* The :class:`plainbox.impl.secure.providers.v1.Provider1Definition` class now
  offers a set of properties that compute the implicit values of certain
  directories. Those all depend on a non-Unset ``location`` field. Those
  include:
  :meth:`plainbox.impl.secure.providers.v1.Provider1Definition.implicit_jobs_dir`,
  :meth:`plainbox.impl.secure.providers.v1.Provider1Definition.implicit_whitelists_dir`,
  :meth:`plainbox.impl.secure.providers.v1.Provider1Definition.implicit_data_dir`,
  :meth:`plainbox.impl.secure.providers.v1.Provider1Definition.implicit_bin_dir`,
  :meth:`plainbox.impl.secure.providers.v1.Provider1Definition.implicit_locale_dir`,
  and
  :meth:`plainbox.impl.secure.providers.v1.Provider1Definition.implicit_build_locale_dir`,
* The :class:`plainbox.impl.secure.providers.v1.Provider1Definition` class now
  offers a set of properties that compute the effective values of certain
  directories:
  :meth:`plainbox.impl.secure.providers.v1.Provider1Definition.effective_jobs_dir`,
  :meth:`plainbox.impl.secure.providers.v1.Provider1Definition.effective_whitelists_dir`,
  :meth:`plainbox.impl.secure.providers.v1.Provider1Definition.effective_data_dir`,
  :meth:`plainbox.impl.secure.providers.v1.Provider1Definition.effective_bin_dir`,
  and
  :meth:`plainbox.impl.secure.providers.v1.Provider1Definition.effective_locale_dir`.
* The :class:`plainbox.impl.secure.providers.v1.Provider1Definition` class now
  offers the
  :meth:`plainbox.impl.secure.providers.v1.Provider1Definition.effective_gettext_domain`
  property.

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
* PlainBox has new APIs for creating almost arbitrary job qualifiers out of the
  :class:`plainbox.impl.secure.qualifiers.FieldQualifier` and
  :class:`plainbox.impl.secure.qualifiers.IMatcher` implementations such as
  :class:`plainbox.impl.secure.qualifiers.OperatorMatcher` or
  :class:`plainbox.impl.secure.qualifiers.PatternMatcher`. Older qualifiers
  will likely be entirely dropped and replaced by one of the subsequent
  releases. 

API changes (command line tools)
--------------------------------

* :class:`plainbox.impl.clitools.ToolBase` now offers additional methods for
  setting up translations specific to a specific tool. This allows a library
  (such as PlainBox) to offer a basic tool that other libraries or applications
  subclass and customize, part of the tool implementation (including
  translations) will come from one library while the rest will come from
  another. This allows various strings to use different gettext domains. This
  is implemented in the new set of methods:
  :meth:`plainbox.impl.clitools.ToolBase.get_gettext_domain()`
  :meth:`plainbox.impl.clitools.ToolBase.get_locale_dir()` and
  :meth:`plainbox.impl.clitools.ToolBase.setup_i18n()` last of which is now
  being called by the existing
  :meth:`plainbox.impl.clitools.ToolBase.early_init()` method.
* :class:`plainbox.impl.clitools.CommandBase` now offers additional methods for
  setting up sub-commands that rely on the docstring of the subcommand
  implementation class. Those are
  :meth:`plainbox.impl.clitools.CommandBase.get_command_name()`
  :meth:`plainbox.impl.clitools.CommandBase.get_command_help()`,
  :meth:`plainbox.impl.clitools.CommandBase.get_command_description()` and
  :meth:`plainbox.impl.clitools.CommandBase.get_command_epilog()`. Those
  methods return values suitable to argparse. They are all used from one
  high-level method :meth:`plainbox.impl.clitools.CommandBase.add_subcommand()`
  which is now used in the implementation of various new subcommand classes.
  All of those methods are aware of i18n and hide all of the associated
  complexity.

API changes (Resources)
-----------------------

* :class:`plainbox.impl.resource.ResourceExpression` now accepts, stores and
  users an optional implicit name-space that qualifies all resource
  identifiers. It is also available as
  :meth:`plainbox.impl.resource.ResourceExpression.implicit_namespace`.
* :class:`plainbox.impl.resource.ResourceProgram` now accepts and uses an
  optional implicit name-space that is being forwarded to the resource
  expressions.

API changes (Execution Controllers)
-----------------------------------

* :class:`plainbox.impl.ctrl.CheckBoxExecutionController` no longer puts all of
  the provider-specific executables onto the PATH of the execution environment
  for each job definition. Now only executables from providers that have the
  same name-space as the job that needs to be executed are added to PATH.  This
  brings the behavior of execution controllers in sync with all the other
  name-space-aware components.

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
* Bugfixes: https://launchpad.net/checkbox/+milestone/plainbox-0.5b1

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
