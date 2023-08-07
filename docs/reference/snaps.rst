.. _snap_reference:

===============
Snap Versions
===============

There are several Checkbox snaps and channels to choose from. You can
get a full list via ``snap info checkbox``. You can refer to the following
to decide what you should install.

.. _ref_which_snap:

Picking your version
====================

As you may recall from the :ref:`installing_checkbox` tutorial, when installing Checkbox
you need to pick a frontend and a backend. There are several parameters that
may influence your choice of the best snap for your situation but in general
there are three distinguishing factors in Checkbox snaps: base, confinement and
stability.

Base
----

The base of a snap is the underlying version of the operating system
that it uses to run. For example ``checkbox 22.04`` and ``checkbox22``
are built on top of Ubuntu22.04. This is not an 100% accurate
explanation of what a base is but you can use this rule of thumb in your decision.
If you want a more complete explanation of what bases are and how they are built,
refer to this
`blog post from the Snapcraft team <https://snapcraft.io/blog/all-about-that-base>`_.

In general we advise to use the version of Checkbox that most closely matches the
system that is going to run it. If you are not on an LTS release of Ubuntu or
you are using a completely different operating system, try to match it to
the closest release we have. For example, if you are on Ubuntu23.04,
``checkbox22`` is probably the one you will have to choose.

Confinement
-----------

As you may know, or may learn more from
`the Snapcraft documentation <https://snapcraft.io/docs/snap-confinement>`_, a
snap can either use ``strict`` or ``classic`` confinement. Checkbox has a snap
for both models. The strict snaps are called ``ucXX``, the classic ones have a
standard LTS name.

In general we advise to use ``classic`` snap. You are going to need the ``classic``
one whenever the tests you are running need a binary that is available in your
system but not in the ``strict`` snap.

.. note::

  This section only applies to the Checkbox frontend, the backend snap is always
  ``strictly`` confined.

Stability
---------

Checkbox uses `semantic versioning <https://semver.org>`_. There are three channels
that you can install from ``edge``, ``beta`` and ``stable``.

If you want a stable version that we are pretty sure that works, use ``stable``, this
version was tested thoroughly via continuous integration and in our lab and is the
one that we use for our `Ubuntu Certified <https://ubuntu.com/certified>`_ program.

If you can trade a little bit of stability for more up-to-date features, you can use
``beta``. This version of Checkbox was tested via CI and on a subset of our lab. It
should be as good as ``stable``, but once we are sure it is we will promote it to
that channel.

If you want the most up-to-date possible build of Checkbox you can use the
``edge`` channel. These builds are updated daily and contain the latest changes to
the framework. We do not advise to use this channel in production, it is tested
via CI and it is built from the latest commit in the ``main`` branch of the
`Checkbox Repository on github <https://github.com/canonical/checkbox>`_.
