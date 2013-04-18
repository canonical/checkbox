PlainBox Architecture
=====================

This document explains the architecture of PlainBox internals. It should be
always up-to-date and accurate to the extent of the scope of this overview.

.. toctree::
   :maxdepth: 3

   config.rst
   resources.rst
   old.rst

General design considerations
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

PlainBox is a reimplementation of CheckBox that replaces a reactor / event /
plugin architecture with a monolithic core and tightly integrated components.

The implementation models a few of the externally-visible concepts such as
jobs, resources and resource programs but also has some additional design that
was not present in CheckBox before.

The goal of the rewrite is to provide the right model and APIs for user
interfaces in order to build the kind of end-user solution that we could not
build with CheckBox.

This is expressed by additional functionality that is there only to provide the
higher layers with the right data (failure reason, descriptions, etc.). The
code is also intended to be highly testable. Test coverage at the time of
writing this document was exceeding 80%

The core requirement for the current phase of PlainBox development is feature
parity with CheckBox and gradual shift from one to another in the daily
responsibilities of the Hardware Certification team. Currently PlainBox
implements a large chunk of core / essential features from CheckBox. While not
all features are present the core is considered almost feature complete at this
stage.

