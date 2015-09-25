ChangeLog
=========

.. note::
    This changelog contains only a summary of changes. For a more accurate
    accounting of development history please inspect the source history
    directly.

.. _version_0_24:

Plainbox 0.24 (unreleased)
^^^^^^^^^^^^^^^^^^^^^^^^^^

* Plainbox now supports an *after* job ordering constraint. This constraint is
  very similar to the existing *depends* constraint, except that the outcome of
  the referenced job is not important. In practical terms, even if one job runs
  and fails, another job that runs *after* it, will run.

  This constraint is immediately useful to all *attachment* jobs that want to
  collect a log file from some other operation, regardless of the outcome of
  that operation. In the past those would have to be carefully placed in the
  test plan, in the right order. By using the *after* constraint, the
  attachment jobs will automatically pull in their log-generating cousins and
  will run at the right time no matter what happens.

.. _version_0_23:

Plainbox 0.23 (QA Testing)
^^^^^^^^^^^^^^^^^^^^^^^^^^

* Mandatory jobs - jobs may be marked as mandatory - this way they are always
  executed - useful for jobs that get information about hardware. Use
  mandatory_include test plan field to mark the jobs you want always to be run.

* Bootstrapping jobs - applications may run jobs that generate other jobs prior
  to the execution of the 'normal' list of jobs. Use bootstrap_include field of
  the test plan to list all jobs that generate other jobs.

  Read more about mandatory and bootstrapping jobs in
  :doc:`plainbox test plan unit <manpages/plainbox-test-plan-units>`

* Plainbox now supports a new flag :ref:`has-leftovers
  <job_flag_has_leftovers>`, that governs the behavior of leftover file
  detection feature. When this flag is added to a job definition files left
  over by the execution of a command are silently ignored.

* Plainbox now supports a new flag on job definitions :ref:`simple
  <job_flag_simple>` that is meant to cut the boiler-plate from fully automated
  test cases. When this flag is added to a job definition then many otherwise
  mandatory or recommended features are disabled.

.. _version_0_18:

Plainbox 0.18
^^^^^^^^^^^^^

.. note::
    This version is under active development. The details in the milestone page
    may vary before the release is finalized.

This is a periodic release, containing both bug fixes and some minor new
features. Details are available at:

* https://launchpad.net/plainbox/+milestone/0.18

.. warning::
    API changes were not documented for this release. We are working on a new
    system that will allow us to automatically generate API changes between

.. _version_0_17:

Plainbox 0.17
^^^^^^^^^^^^^

This is an (out-of-cycle) periodic release, containing both bug fixes and some
minor new features. Details are available at:

* https://launchpad.net/plainbox/+milestone/0.17

.. warning::
    API changes were not documented for this release. We are working on a new
    system that will allow us to automatically generate API changes between
    releases without the added manual maintenance burden.

.. _version_0_16:

Plainbox 0.16
^^^^^^^^^^^^^

This is a periodic release, containing both bug fixes and some minor new
features. Details are available at:

* https://launchpad.net/plainbox/+milestone/0.16

.. warning::
    API changes were not documented for this release. We are working on a new
    system that will allow us to automatically generate API changes between
    releases without the added manual maintenance burden.

.. _version_0_15:

Plainbox 0.15
^^^^^^^^^^^^^

This is a periodic release, containing both bug fixes and some minor new
features. Details are available at:

* https://launchpad.net/plainbox/+milestone/0.15

.. warning::
    API changes were not documented for this release. We are working on a new
    system that will allow us to automatically generate API changes between
    releases without the added manual maintenance burden.

.. _version_0_14:

Plainbox 0.14
^^^^^^^^^^^^^

This is a periodic release, containing both bug fixes and some minor new
features. Details are available at:

* https://launchpad.net/plainbox/+milestone/0.14

.. warning::
    API changes were not documented for this release. We are working on a new
    system that will allow us to automatically generate API changes between
    releases without the added manual maintenance burden.

.. _version_0_13:

Plainbox 0.13
^^^^^^^^^^^^^

This is a periodic release, containing both bug fixes and some minor new
features. Details are available at:

* https://launchpad.net/plainbox/+milestone/0.13

.. warning::
    API changes were not documented for this release. We are working on a new
    system that will allow us to automatically generate API changes between
    releases without the added manual maintenance burden.

.. _version_0_12:

Plainbox 0.12
^^^^^^^^^^^^^

This is a periodic release, containing both bug fixes and some minor new
features. Details are available at:

* https://launchpad.net/plainbox/+milestone/0.12

.. warning::
    API changes were not documented for this release. We are working on a new
    system that will allow us to automatically generate API changes between
    releases without the added manual maintenance burden.

.. _version_0_11:

Plainbox 0.11
^^^^^^^^^^^^^

This is a periodic release, containing both bug fixes and some minor new
features. Details are available at:

* https://launchpad.net/plainbox/+milestone/0.11

.. warning::
    API changes were not documented for this release. We are working on a new
    system that will allow us to automatically generate API changes between
    releases without the added manual maintenance burden.

.. _version_0_10:

Plainbox 0.10
^^^^^^^^^^^^^

This is a periodic release, containing both bug fixes and some minor new
features. Details are available at:

* https://launchpad.net/plainbox/+milestone/0.10

.. warning::
    API changes were not documented for this release. We are working on a new
    system that will allow us to automatically generate API changes between
    releases without the added manual maintenance burden.

.. _version_0_9:

Plainbox 0.9
^^^^^^^^^^^^

This is a periodic release, containing both bug fixes and some minor new
features. Details are available at:

* https://launchpad.net/plainbox/+milestone/0.9

.. warning::
    API changes were not documented for this release. We are working on a new
    system that will allow us to automatically generate API changes between
    releases without the added manual maintenance burden.

.. _version_0_8:

Plainbox 0.8
^^^^^^^^^^^^

This is a periodic release, containing both bug fixes and some minor new
features. Details are available at:

* https://launchpad.net/plainbox/+milestone/0.8

.. warning::
    API changes were not documented for this release. We are working on a new
    system that will allow us to automatically generate API changes between
    releases without the added manual maintenance burden.

.. _version_0_7:

Plainbox 0.7
^^^^^^^^^^^^

This is a periodic release, containing both bug fixes and some minor new
features. Details are available at:

* https://launchpad.net/plainbox/+milestone/0.7

.. warning::
    API changes were not documented for this release. We are working on a new
    system that will allow us to automatically generate API changes between
    releases without the added manual maintenance burden.

.. _version_0_6:

Plainbox 0.6
^^^^^^^^^^^^

This is a periodic release, containing both bug fixes and some minor new
features. Details are available at:

* https://launchpad.net/plainbox/+milestone/0.6

.. warning::
    API changes were not documented for this release. We are working on a new
    system that will allow us to automatically generate API changes between
    releases without the added manual maintenance burden.

.. _version_0_5:

Plainbox 0.5.4
^^^^^^^^^^^^^^

This is a maintenance release of the 0.5 series.

Bugs fixed in this release are assigned to the following milestone:

* Bugfixes: https://launchpad.net/plainbox/+milestone/0.5.4

Plainbox 0.5.3
^^^^^^^^^^^^^^

This is a maintenance release of the 0.5 series.

Bug fixes
---------

Bugs fixed in this release are assigned to the following milestone:

* Bugfixes: https://launchpad.net/plainbox/+milestone/0.5.3

API changes
-----------

* Plainbox now has an interface for transport classes.
  :class:`plainbox.abc.ISessionStateTransport` that differs from the old
  implementation of the certification transport (the only one that used to
  exist). The new interface has well-defined return value, error semantics and
  takes one more argument (session state). This change was required to
  implement the launchpad transport.
* Plainbox now has support for pluggable build systems that supply automatic
  value for the build_cmd argument in manage.py's setup() call. They existing
  build systems are available in the :mod:`plainbox.impl.buildsystems` module.
* All exporters can now make use of key=value options.
* The XML exporter can now be customized to set the client name option. This is
  available using the standard exporter option list and is available both at
  API level and on command line.
* The provider class can now keep track of the src/ directory and the build/bin
  directory, which are important for providers under development. This feature
  is used to run executables from the build/bin directory.
* Plainbox will now load the src/EXECUTABLES file, if present, to enumerate
  executables built from source. This allows manage.py install to be more
  accurate and allows manage.py info do display executables even before they
  are built.

Plainbox 0.5.2
^^^^^^^^^^^^^^

This is a maintenance release of the 0.5 series.

Bug fixes
---------

Bugs fixed in this release are assigned to the following milestone:

* Bugfixes: https://launchpad.net/checkbox/+milestone/plainbox-0.5.2

API changes
-----------

* Plainbox now remembers the base directory (aka location) associated with each
  provider. This is available as and
  :attr:`plainbox.impl.secure.providers.v1.Provider1.base_dir`
* The :class:`plainbox.impl.commands.checkbox.CheckboxInvocationMixIn` gained a
  new required argument to pass the configuration object around. This is
  required to fix bug https://bugs.launchpad.net/checkbox/+bug/1298166. This
  API change is backwards incompatible and breaks checkbox-ng << 0.3.
* Plainbox now offers the generic extensibility point for build systems for
  provider executables. Entry points for classes implementing the
  :class:`plainbox.abc.IBuildSystem` interface can be registered in the
  ``plainbox.buildsystems`` pkg-resources entry point.
* Plainbox has a better job validation subsystem. Job validation parameters
  (eventually passed to
  :meth:`plainbox.impl.job.CheckboxJobValidator.validate()`) can be set on the
  provider loader class and they will propagate across the stack. Along with
  more fine-tuned controls for strict validation and deprecated fields
  validation this offers tools better ways to discover potential problems.

Plainbox 0.5.1
^^^^^^^^^^^^^^

First working release of the 0.5 series, 0.5 was missing one critical patch and
didn't work. Basically, The tag was applied on the wrong revision.

Plainbox 0.5
^^^^^^^^^^^^

New Features
------------

* Plainbox is now a better development tool for test authors. With the new
  'plainbox startprovider' command it is easy to bootstrap  development of
  third party test collections. This is further explained in the new
  :ref:`tutorial`. The template is described in :doc:`provider template
  <author/provider-template>`.
* Test providers now control namespaces for job definitions, allowing test
  authors to freely name job definitions without any central coordination
  authority. See more about :doc:`provider namespaces
  <author/provider-namespaces>`.
* Plainbox is now fully internationalized, making it possible to translate all
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

* Plainbox is now available in Debian as the ``python3-plainbox`` and
  ``plainbox`` packages. Several of the Checkbox project developers are
  maintaining packages for the core library, test providers and whole test
  applications.
* Plainbox dropped support for Ubuntu 13.04 (Raring Rigtail), following
  scheduled end-of-life of that release.
* Plainbox dropped support for Ubuntu 13.10 (Saucy Salamander) given the
  imminent release of the next version of Ubuntu.
* Plainbox now supports Ubuntu 14.04 (Trusty Thar), scheduled for release on
  the 17th of April 2014.

This implies that any patch merged into trunk is only tested on Ubuntu 12.04
(with python3.2) and Ubuntu 14.04 (with python3.3, which will switch to python
3.4 later, before the final release.)

Internal Changes
----------------

General Changes
...............

* Plainbox now supports Python 3.4. This includes existing support for Python
  3.2 and 3.3. Effective Ubuntu coverage now spans two LTS releases.
  This will be maintained until the end of Ubuntu 12.04 support.

New Modules
...........

* Plainbox now has a dedicated module for implementing versatile command line
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

* Plainbox now offers two new properties for identifying (naming) job
  definitions, :meth:`plainbox.impl.job.JobDefinition.id` and
  :meth:`plainbox.impl.job.JobDefinition.partial_id`. The ``id`` property is
  the full, effective identifier composed of ``partial_id`` and
  ``provider.namespace``, with the C++ scope resulution operator, ``::``
  joining both into one string. The ``partial_id`` field is loaded from the
  ``id`` key in  RFC822-like job definition syntax and is the part without the
  name-space. Plainbox now uses the ``id`` everywhere where ``name`` used to be
  used before. If the ``id`` field (which defines ``partial_id`` is not present
  in a RFC822 job definition then it defaults to ``name`` making this change
  fully backwards compatible.
* The :meth:`plainbox.impl.job.JobDefinition.name` property is now deprecated.
  It is still available but is has been entirely replaced by the new ``id`` and
  ``partial_id`` properties. It will be removed as a property in the next
  release of Plainbox.
* Plainbox now offers the new :meth:`plainbox.impl.job.JobDefinition.summary`
  which is like a short, one line description of the provider. It should be
  used whenever a job definition needs to be listed (in user interfaces,
  reports, etc). It can be translated and a localized version is available as
  :meth:`plainbox.impl.job.JobDefinition.tr_summary()`
* Plainbox now offers a localized version of a job description as
  :meth:`plainbox.impl.job.JobDefinition.tr_description()`.

API changes (White Lists)
.........................

* Plainbox now offers new and improved APIs for loading whitelists
  :meth:`plainbox.impl.secure.qualifiers.WhiteList.from_string()` and
  :meth:`plainbox.impl.secure.qualifiers.WhiteList.from_file()`.
* Plainbox now tracks the origin of whitelist, knowing where they were defined
  in. Origin is available as
  :meth:`plainbox.impl.secure.qualifiers.WhiteList.origin`
* Plainbox can now optionally store and use the implicit name-space of a
  WhiteList objects. This name space will be used to qualify all the patterns
  that don't use the scope resolution operator ``::``.
  The implicit name-space is available as
  :meth:`plainbox.impl.secure.qualifiers.WhiteList.implicit_namespace`.

API changes (Providers)
.......................

* Plainbox can validate providers, jobs and whitelists better than before. In
  particular, broken providers are now verbosely ignored. This is implemented
  as a number of additional validators on
  :class:`plainbox.impl.secure.providers.v1.Provider1Definition`
* Plainbox can now enumerate all the executables of a provider
  :meth:`plainbox.abc.IProvider1.get_all_executables()`
* Plainbox now offers new APIs for applications to load as much of provider
  content as possible, without stopping on the first encountered problem.
  :meth:`plainbox.impl.secure.providers.v1.Provider1.load_all_jobs()`
* The ``Provider1.load_jobs()`` method has been removed. It was only used
  internally by the class itself. Identical functionality is now offered by
  :class:`plainbox.impl.secure.plugins.FsPlugInCollection` and
  :class:`plainbox.impl.secure.providers.v1.JobDefinitionPlugIn`.
* Plainbox now associates a gettext domain with each provider. This
  information is available both in
  :attr:`plainbox.impl.secure.providers.v1.Provider1Definition.gettext_domain`
  and :attr:`plainbox.impl.secure.providers.v1.Provider1.gettext_domain`
* Plainbox now derives a namespace from the name of the provider. The namespace
  is defined as  the part of the provider name up to the colon. For example
  provider name ``2013.com.canonical.ceritifaction:resources`` defines provider
  namespace ``2013.com.canonical.certification``. The computed namespace is
  available as :meth:`plainbox.impl.secure.providers.v1.Provider1.namespace`
* Plainbox now offers a localized version of the provider description string as
  :meth:`plainbox.impl.secure.providers.v1.Provider1.tr_description()`
* Plainbox now passes the provider namespace to both whitelist and job
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
* Plainbox now associates an optional directory with per-provider locale data.
  This allows it to pass it to ``bindtextdomain()``.  The locale directory is
  available as :meth:`plainbox.impl.secure.providers.v1.Provider1.locale_dir`.
* Plainbox now offers a utility method,
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

* Plainbox now has additional APIs that correctly preserve order of jobs
  selected by a :term:`WhiteList`, see:
  :func:`plainbox.impl.secure.qualifiers.select_jobs`.
* Plainbox has new APIs for converting any qualifier into a list of primitive
  (non-divisible) qualifiers that express the same selection,
  :meth:`plainbox.abc.IJobQualifier.get_primitive_qualifiers()` and
  :meth:`plainbox.abc.IJobQualifier.is_primitive()`.
* Plainbox has new APIs for qualifiers to uniformly include and exclude jobs
  from the selection list. This is implemented as a voting system described in
  the :meth:`plainbox.abc.IJobQualifier.get_vote()` method.
* Plainbox has new APIs for creating almost arbitrary job qualifiers out of the
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
  (such as Plainbox) to offer a basic tool that other libraries or applications
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

* :class:`plainbox.impl.ctrl.CheckboxExecutionController` no longer puts all of
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
* Plainbox now stores application identifier
  :meth:`plainbox.impl.session.state.SessionMetaData.app_id` which complements
  the existing application-specific blob property
  :meth:`plainbox.impl.session.state.SessionMetaData.app_blob` to allow
  applications to resume only the session that they have created. This feature
  will allow multiple plainbox-based applications to co-exist their state
  without clashes.
* Plainbox now stores both the normalized and raw version of the data produced
  by the RFC822 parser. The raw form is suitable as keys to gettext. This is
  exposed through the RFC822 and Job Definition classes.

Bug fixes
---------

Bugs fixed in this release are assigned to the following milestones:

* https://launchpad.net/checkbox/+milestone/plainbox-0.5a1
* https://launchpad.net/checkbox/+milestone/plainbox-0.5b1
* https://launchpad.net/checkbox/+milestone/plainbox-0.5

Plainbox 0.4
^^^^^^^^^^^^

* Bugfixes: https://launchpad.net/checkbox/+milestone/plainbox-0.4

Plainbox 0.4 beta 2
^^^^^^^^^^^^^^^^^^^

* Bugfixes: https://launchpad.net/checkbox/+milestone/plainbox-0.4b2

Plainbox 0.4 beta 1
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

Plainbox 0.3
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

Plainbox 0.2
^^^^^^^^^^^^

* Last release made from the standalone github tree.
* Added support for discovering dependencies and automatic dependency
  resolution (for both job dependencies and resource dependencies)

Plainbox 0.1
^^^^^^^^^^^^

* Initial release
