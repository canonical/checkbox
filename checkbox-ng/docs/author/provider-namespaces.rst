====================
Provider Name-Spaces
====================

Name-spaces are a new feature in the 0.5 release. They alter typically short
job identifiers (names) and prefix them with a long and centrally-managed name
space identifier to ensure that jobs created by different non-cooperating but
well-behaving authors are uniquely distinguishable.

Theoretical Considerations
==========================

About name-spaces
-----------------

Starting with the 0.5 release, PlainBox supports name-spaces for job
identifiers. Each job has a partial identifier which is encoded by the ``id:``
or the legacy ``name:`` field in job definition files. That partial identifier
is prefixed with the name-space of the provider that job belongs to. This
creates unique names for all jobs.

Rationale
---------

Historically the :term:`Checkbox` project used to ship with a collection of job
definitions for various testing tasks. Since there was only one organization
controlling all jobs there was no problem of undesired clashes as all the
involved developers could easily coordinate and resolve issues. 

With the rewrite that brought :term:`PlainBox` the core code and the pluggable
data concept was becoming easier to work with and during the 0.4 development
cycle we had decided to offer first-class support for external developers to
work on their own test definitions separately of the Canonical Hardware
Certification team that maintained the Checkbox project.

The first concern that became obvious as we introduced test providers was that
the name-space for all identifiers (job names at the time) was flat. As
additional test authors started using providers and, devoid of the baggage of
experience with legacy Checkbox, used natural, generic names for job
definitions it became clear that in order to work each test author needs to
have a private space where no clashes are possible.

Name-Space Organization Guide
-----------------------------

This section documents some guidelines for using name-spaces in practice.

Provider Name Spaces and IQN
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

PlainBox name-spaces are based on the iSCSI IQN concept. It is a simple
extension of the usage of DNS names to create name-spaces. As DNS is externally
managed anyone owning a domain name can use that domain name and have a high
chance of avoiding clashes (as long as no party is maliciously trying to create
clashing names). IQN extends that with a year code. Since DNS name ownership
can and does change (people don't extend domains, companies change ownership,
etc.) it was important to prevent people from having to own a domain forever to
ensure name-space collisions are avoided. By prepending the four-digit year
number when a domain was owned by a particular entity, anyone that ever owned a
domain can create unique identifiers.

Sole Developers
^^^^^^^^^^^^^^^

If you are a sole developer you need to own at least one domain name at least
once. Assuming you owned example.com in 2014 you can create arbitrary many
name-spaces starting with ``2014.example.com``. It is advisable to use at least
one sub-domain if you know up front that the tests you are working on are for a
particular, well-defined task. For example, you could use
``2014.example.com.project1``.

Within that name-space you can create arbitrary many test providers (typically
to organize your dependencies so that not everything needs to be installed at
once). An example provider could be called
``2014.example.com.project1:acceptance-tests``. If you have two jobs inside
that provider, say ``test-1`` and ``test-2`` they would be called (**surprise**)
``2014.example.com.project1::test-1`` and
``2014.example.com.project1::test-2``.

Organizations and Companies
^^^^^^^^^^^^^^^^^^^^^^^^^^^

If you are working as a part of an organization you should coordinate within
that organization and use the same rules as the sole developer above. The
primary difference is that you should really always use a sub-domain (so for
example, ``2014.example.com.department``) to differentiate your tests from
tests that may be independently developed by other people within the same
company. It is recommended that managers of particular organizational units
decide on the particular name-space to use.

Important Notes
^^^^^^^^^^^^^^^

There are two important notes that apply to everyone:

.. note::

    Remember that provider namespace is **derived** from the provider name, the
    part after the colon, including the colon, is discarded. Providers are a
    way to organize tests together for dependencies. Namespaces are a way to
    organize tests regardless of dependencies.

.. warning::

    If you are reading this in 2015 and beyond, don't bump the year component.
    Unless you are the new owner of ``example.com`` and you want to
    differentiate your tests from whoever used to own *example.com* in 2014 you
    should **keep using the same year forever**. If you bump the year all the
    time you will create lots of small namespaces and you will most likely
    break other people that may run your tests with a fixed identifier
    hardcoded in a package name or script. 

Technical Details
=================

Implicit Provider Name-Space
----------------------------

As mentioned above, the provider name-space is derived from the provider name::

    2014.com.example.project:acceptance
    ^----------------------^
               |
       provider namespace

    ^---------------------------------^
                     |
               provider name

The part of the provide name before the colon is used as the name-space. The
colon is *not* a part of the name-space.

The implicit name-space is used to construct non-partial job definition names
as well as to implicitly prefix each pattern inside :term:`whitelists <whitelist>`. 

Using Explicit Name-Spaces
--------------------------

Explicit name-spaces need to be used in two situations:

1. When running a single job by name, e.g.: ``plainbox run -i
   2013.com.canonical.plainbox::stub/true``.
   
   This is required as any partial ID may silently change the job it resolves
   to and we didn't want to introduce that ambiguity.

2. When including a job from another name-space inside a whitelist, e.g.::

        ~/2014.com.example.some:provider$ cat whitelists/cross.whitelist
        job-a
        job-b
        2014\.com\.example\.other::job-a
        ~/2014.com.example.some:provider$

   Here the whitelist names three jobs:

   * 2014.com.example.some::job-a
   * 2014.com.example.some::job-b
   * 2014.com.example.other::job-a

   Note that the dots are escaped with ``\`` to prevent them from matching
   arbitrary character.

Custom Executables & Execution Environment
------------------------------------------

When PlainBox needs to execute a job with a shell command it constructs a
special execution environment that includes additional executables specific to
some providers. The execution environment is comprised of a directory with
symbolic links to all the private executables of all of the provides that have
the same name-space as the provider that owns the job that is to be executed.

Names of custom executables should be treated identically as job identifiers,
they share a private name-space (though separate from job names) and need to be
managed in the same way.

Limitations and Known Issues
============================

List of issues as of version 0.5
--------------------------------

* It is impossible to use a resource from one name-space in a job definition
  from another name-space. This restriction should be lifted with the
  introduction of additional syntax in subsequent versions.

* It is impossible for a local job to generate a new job definition in a
  different name-space than the one of the local job itself. This limitation is
  likely not to be lifted.
