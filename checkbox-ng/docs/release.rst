========================
CheckBox Release Process
========================

This page describes the necessary steps for releasing versions of CheckBox and
CheckBox Certification to the stable PPA belonging to the Hardware
Certification team, on a regular basis. Throughout this document the term
'CheckBox' is used as a catch-all term to cover all versions of CheckBox owned
by the Hardware Certification team, currently CheckBox itself and the CheckBox
Certification extensions.

Overview
========

Currently the process runs on a bi-weekly cadence, with a new release of
Checkbox every two weeks. This covers ten working days, and the tasks carried
out on each day or group of days is described below:

* Days 1-4: Time allowed for new changes to be introduced into trunk.
* Day 5: Changes are merged from the trunk of ``lp:checkbox`` and
  ``lp:checkbox-certification`` to their respective release branches.
  The changelogs for both are *bumped* at this point and revisions are tagged.
  At this stage it may also be necessary to copy the package 'fwts' from the
  `FWTS Stable PPA
  <https://launchpad.net/~firmware-testing-team/+archive/ppa-fwts-stable>`_ 
  to the `Checkbox Release Testing PPA
  <https://launchpad.net/~checkbox-dev/+archive/testing>`_.
  
* Days 6-9: Testing is performed by the release manager for the Hardware
  Certification team, and a representative of the CE QA team (the main
  customer for CheckBox within Canonical)
* Day 9: A release meeting is held between the release manager for the
  Hardware Certification team and the representative of the CE QA team.
  Potential issues with the release are identified and plans made to address
  them.
* Day 10: The tested version of CheckBox is copied to the stable PPA.

Launchpad Branches
==================

The release process requires separate branches in Launchpad containing a
semi-frozen version of the code that was in trunk on day 5 of the process. This
is so that development can continue on trunk without jeopardising the stability
of the to-be released version of CheckBox. The relationship between all
branches involved in the process is as shown below:

* `lp:checkbox/release` <- `lp:checkbox`
* `lp:checkbox-certification/release` <- `lp:checkbox-certification`
* `lp:~checkbox-dev/checkbox/checkbox-packaging-release` <- `lp:~checkbox-dev/checkbox/checkbox-packaging`

Auditing milestoned bugs
========================

Prior to creating the release candidate the release manager should review the
list of bugs milestoned for the next release of CheckBox. They should visit
`checkbox milestones <https://launchpad.net/checkbox/+milestones milestones>`_
and locate the milestone dated with the release date.

* For bugs that are set to In Progress with a branch associated - liase with
  the branch owner to see if the merge can be completed before the deadline.
* For bugs that are in any other non-closed status (except *Fix Commited*) -
  re-milestone them to the following milestone.

Cutting the release
===================

In order to cut the release, we have to merge the changes from trunk into the
release branch, commit them with a suitable message and update the changelog in
trunk so that future changes go under the correct version. For each combination
of branches shown above, do the following (the example uses ``lp:checkbox`` and
``lp:checkbox/release``)::

    bzr branch lp:checkbox/release checkbox-release
    bzr branch lp:checkbox checkbox-trunk
    cd checkbox-release
    current_stable=`head -n1 $(find . -name 'changelog') | grep -oP '(?<=\().*(?=\))'`
    bzr merge lp:checkbox

at this point if no changes (other than one to ``debian/changelog``) get merged
in then we do not perform a release of the package in question. In practice
this often happens with ``checkbox-certification`` but never with
``checkbox``::

    bzr commit -m "Merged in changes from rev$(bzr revno -r tag:$current_stable lp:checkbox) to rev$(bzr revno lp:checkbox) from lp:checkbox"
    bzr push lp:checkbox/release
    cd `find . -name 'debian'`; cd ..
    bzr tag `head -n1 debian/changelog | grep -oP '(?<=\().*(?=\))'`
    dch -r (save modified changelog)
    dch -i -U 'Incremented changelog'
    debcommit
    bzr push lp:checkbox

The last step in the process is to perform a build of the packages in the
``ppa:checkbox-dev/testing PPA``. To do this we need to go to the recipe pages
for the ``checkbox`` and/or ``checkbox-certification`` release branches.

 * `checkbox-testing recipe
   <https://code.launchpad.net/~checkbox-dev/+recipe/checkbox-testing>`_
 * `checkbox-certification-testing recipe
   <https://code.launchpad.net/~checkbox-dev/+recipe/checkbox-certification-testing>`_

The **Build Now** option should be available on the page. Click it to start a
build.

Copying Firmware Test Suite to the Testing PPA
==============================================

The Firmware Test Suite tool is a test tool for system firmware that is 
naturally heavily utilised by Checkbox. To make sure the latest version
which contains fixes and new tests/features needed by Checkbox is available
and also doesn't break anything in Checkbox, we need to release it alongside
Checkbox. After cutting the release if the Firmware Testing team have notified
that a new version is available and that this version should be used for
certification, we need to copy it to the Testing PPA. To do this we need to go
to the `Copy packages view of the Firmware Test Suite (Stable) PPA
<https://launchpad.net/~firmware-testing-team/+archive/ppa-fwts-stable/+copy-packages>`_
and select the 'fwts' packages for all releases back to Precise. We need to
set the 'Destination PPA' as 'Checkbox Release Testing [~checkbox-dev/testing]'
and the 'Copy options' field to 'Copy existing binaries', then click 'Copy
packages'. This step then needs to be repeated but set the 'Destination PPA'
field to 'PPA for Checkbox Developers [~checkbox-dev/ppa]'.

Next Release of Checkbox e-mail
===============================

So that everyone has the opportunity to perform whatever testing is required in
a timely manner, after the PPA builds have been completed an email should be
sent to the following mailing lists:

* `hardware-certification-team@lists.canonical.com <mailto:hardware-certification-team@lists.canonical.com>`_
* `commercial-engineering@lists.canonical.com <mailto:commercial-engineering@lists.canonical.com>`_

The content is typically something like this::

    Subject: Next Release of CheckBox (18/11/2013)

    Hi,

    The next release of CheckBox is available in the
    https://code.launchpad.net/~checkbox-dev/+archive/testing PPA.
    Please test it at your convenience. CheckBox is based on revision 2484 of
    lp:checkbox and CheckBox Certification is based on revision 586 of
    lp:checkbox-certification.

    Thanks,

If one or the other of CheckBox and CheckBox Certification have not been
updated then there is no need to mention that package

Testing the release
===================

Now that the release has been cut, testing should take place prior to the
release meeting. From the point of view of the certification team, what needs
to be tested is ``checkbox-certification-client`` and
``checkbox-certification-server`` which form the basis for CE QAs OEM specific
versions of CheckBox. CheckBox certification server is tested in the CI loop
CheckBox certification client needs to be tested manually.

Release Meeting
===============

On the Thursday before the release is made, a meeting is held between a
representative of the Certification team and a representative of the
**Commercial Engineering QA** team. The meeting is held at 7:30 UTC as shown in
this `calendar invite
<https://www.google.com/calendar/hosted/canonical.com/event?action=TEMPLATE&tmeid=Y3QxcWVla3ViMTRvMXByOHZlOTFvc283Y2NfMjAxMzA4MjlUMDczMDAwWiBicmVuZGFuLmRvbmVnYW5AY2Fub25pY2FsLmNvbQ&tmsrc=brendan.donegan%40canonical.com>`_.
An agenda for the meeting is included in the invite.

Publishing the release
======================

To publish the release we simply need to copy a number of packages from the
`Checkbox Release Testing PPA 
<https://launchpad.net/~checkbox-dev/+archive/testing>`_
to the `Hardware Certification Public PPA
<https://launchpad.net/~hardware-certification/+archive/public>`_. To do this 
we go to the `Copy packages view of the Checkbox Release Testing PPA
<https://launchpad.net/~checkbox-dev/+archive/testing/+copy-packages>`_ and 
select all versions of the following list of packages: ``checkbox,
checkbox-certification, fwts``. Make sure that the 'Destination PPA'
field is set to 'Public PPA for Hardware Certification
[~hardware-certification/public]' and that the 'Copy options' field is set to
'Copy existing binaries', then click 'Copy Packages'.

After that is done an announcement email should be sent to
`commercial-engineering@lists.canonical.com <mailto:commercial-engineering@lists.canonical.com>`_. 
A template for the announcement in included below::

    Hi,

    A new release of checkbox has been uploaded to the Hardware
    Certification Public PPA
    (https://launchpad.net/~hardware-certification/+archive/public). The
    release is based on revision 2294 of lp:checkbox

    Thanks,

Please attach the most recent part of the changelog as release notes
