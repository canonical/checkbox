=============================
 canonical-certification-cli
=============================

--------------------------------------------------------------------------------------------------------
performs interactive system testing in console mode and sends results to Canonical Certification Website
--------------------------------------------------------------------------------------------------------

:Manual section: 1
:Author: Zygmunt Krynicki, 2015

SYNOPSIS
========
  canonical-certification-cli

OPTIONS
=======

This program doesn't support any command line options.

DESCRIPTION
===========

This program is meant for use with systems participating in the Canonical
hardware certification process. To use this tool the device under test must
have a valid *Secure-ID* number.  To learn how to create or locate the Secure
ID, please see here: https://certification.canonical.com/

This program will gather information from your system. Then you will be asked
manual tests to confirm that the system is working properly. Finally, you will
be asked for the Secure ID of the computer to submit the information to the
certification.canonical.com database.

TEST PLAN SELECTION
===================

This program will allow you to select test any test plan.
