======================================
plainbox-packaging-meta-data-units (7)
======================================

Synopsis
========

This page documents the syntax of the plainbox packaging meta-data units

Description
===========

The packaging meta-data unit describes system-level dependencies of a provider
in a machine readable way. Dependencies can be specified separately for
different distributions. Dependencies can also be specified for a common base
distribution (e.g. for Debian rather than Ubuntu). The use of packaging
meta-data units can greatly simplify management of dependencies of binary
packages as it brings those decisions closer to the changes to the actual
provider and makes package management largely automatic.

File format and location
------------------------

Packaging meta-data units are regular plainbox units and are contained and
shipped with plainbox providers. In other words, they are just the same as job
and test plan units, for example.

Fields
------

Following fields may be used by a manifest entry unit.

``os-id``:
    (mandatory) - the identifier of the operating system this rule applies to.
    This is the same value as the ``ID`` field in the file ``/etc/os-release``.
    Typical values include ``debian``, ``ubuntu`` or ``fedora``.

``os-version-id``:
    (optional) - the identifier of the specific version of the operating system
    this rule applies to. This is the same as the ``VERSION_ID`` field in the
    file ``/etc/os-release``. If this field is not present then the rule
    applies to all versions of a given operating system.

The remaining fields are custom and depend on the packaging driver. The values
for **Debian** are:

``Depends``:
    (optional) - a comma separated list of dependencies for the binary package.
    The syntax is the same as in normal Debian control files (including package
    version dependencies). This field can be split into multiple lines, for
    readability, as newlines are discarded.
``Suggests``:
    (optional) - same as ``Depends``.
``Recommends``:
    (optional) - same as ``Depends``.

Matching Packaging Meta-Data Units
----------------------------------

The base Linux distribution driver parses the ``/etc/os-release`` file, looks
at the ``ID``, ``ID_VERSION`` and optionally the ``ID_LIKE`` fields.  They are
used as a standard way to determine the distribution for which packaging
meta-data is being collected for.

The *id and version match* strategy requires that both the ``os-id`` and
``os-dependencies`` fields are present and that they match the ``ID`` and
``ID_VERSION`` values. This strategy allows the test maintainer to express each
dependency accurately for each operating system they wish to support.

The *id match* strategy is only used when the ``os-version`` is not defined.
It is useful when a single definition is applicable to many subsequent
releases.  This is especially useful when job works well with sufficiently old
version of a third party dependency and there is no need to repeatedly re-state
the same dependency for each later release of the operating system.

The *id_like match* strategy is only used as a last resort and can be seen as a
weaker *id match* strategy. This  time the ``os-id`` field is compared to the
``ID_LIKE`` field (if present). It is useful for working with Debian
derivatives, like Ubuntu.

Each matching packaging meta-data unit is then passed to the driver to generate
packaging meta-data.

Example
-------

This is an example packaging meta-data unit, as taken from the resource provider::

    unit: packaging meta-data
    os-id: debian
    Depends:
     python3-checkbox-support (>= 0.2),
     python3 (>= 3.2),
    Recommends:
     dmidecode,
     dpkg (>= 1.13),
     lsb-release,
     wodim

This will cause the binary provider package to depend on the appropriate
version of ``python3-checkbox-support`` and ``python3`` in both *Debian*,
*Ubuntu* and, for example, *Elementary OS*. In addition the package will
recommend some utilities that are used by some of the jobs contained in this
provider.

Using Packaging Meta-Data in Debian
-----------------------------------

To make use of the packaging meta-data, follow those steps:

- Ensure that ``/etc/os-release`` exists in your build chroot. On Debian it is
  a part of the ``base-files`` package which is not something you have to worry
  about but other distributions may use different strategies.
- Mark the binary package that contains the provider with the
  ``X-Plainbox-Provider: yes`` header.
- Add the ``${plainbox:Depends}``, ``${plainbox:Recommends}`` and
  ``${plainbox:Suggests}`` variables to the binary package that contains the
  provider.
- Override the gen_control debhelper rule and run the ``python3 manage.py
  packaging`` command in addition to running ``dh_gencontrol``::

    override_dh_gencontrol:
        python3 manage.py packaging
        dh_gencontrol
