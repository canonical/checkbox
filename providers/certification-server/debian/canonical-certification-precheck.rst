=================================
 canonical-certification-precheck
=================================

----------------------------------------------------------------------
Performs a series of pre-checks to ensure the SUT is ready for testing
----------------------------------------------------------------------

:Manual section: 1
:Author: Jeff Lane, 2016

SYNOPSIS
========
  canonical-certification-precheck

OPTIONS
=======

This program doesn't support any command line options.

DESCRIPTION
===========

This program is meant for use with systems participating in the Canonical
hardware certification process. To use this tool, simply execute the script.
You will be prompted with a series of questions as well as automated checks to
ensure that the SUT is properly configured and ready to perform the automated
testing that Ubuntu Server Certification involves.

This program will give you a summary at the end of any issues discovered so
that you can correct them before running the Server Test Suite. In some cases,
it will offer to fix issues for you. 

Using this program is not required for Certification, but it is provided as a
convenience to testers to catch commonly misconfigured items.
