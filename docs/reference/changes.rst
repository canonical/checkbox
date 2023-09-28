Change history
================

For a full list of the Checkbox releases, see `Checkbox Releases on GitHub <https://github.com/canonical/checkbox/releases>`_.

.. _v2.8:

V2.8 | 2023-08-09
------------------------

* Remove hard-coded version strings in python code  `#509 <https://github.com/canonical/checkbox/pull/509>`_
* Warn on unused develop ``PROVIDERPATH``  `#518 <https://github.com/canonical/checkbox/pull/518>`_
* Refactor docking test  `#462 <https://github.com/canonical/checkbox/pull/462>`_
* Make sure all the expected snaps are built during the release process  `#521 <https://github.com/canonical/checkbox/pull/521>`_
* Fix broken tests mkdir put  `#528 <https://github.com/canonical/checkbox/pull/528>`_
* Fix ``XDG_SESSION_TYPE`` is not set.  `#523 <https://github.com/canonical/checkbox/pull/523>`_
* Modify cold/warm boot stress jobs  `#517 <https://github.com/canonical/checkbox/pull/517>`_
* Add support to ``cpuid.py`` for AMD Bergamo  `#513 <https://github.com/canonical/checkbox/pull/513>`_
* Modify reboot cold boot rewrite reboot check  `#477 <https://github.com/canonical/checkbox/pull/477>`_
* Fix version packages stdlib  `#526 <https://github.com/canonical/checkbox/pull/526>`_
* Integrate ``ppa-dev-tools`` in ``deb-daily-builds``  `#512 <https://github.com/canonical/checkbox/pull/512>`_
* Checkbox 417/wireless detect  `#507 <https://github.com/canonical/checkbox/pull/507>`_
* add "Mini PC" as a valid desktop platform  `#533 <https://github.com/canonical/checkbox/pull/533>`_
* Fix: ``XDG_SESSION_TYPE`` couldn't be got by root  `#536 <https://github.com/canonical/checkbox/pull/536>`_
* Build checkbox.readthedocs.io  `#535 <https://github.com/canonical/checkbox/pull/535>`_
* Clone ``ppa-dev-tools`` in beta builds  `#538 <https://github.com/canonical/checkbox/pull/538>`_
* Avoid flooding stdout with reconnecting  `#541 <https://github.com/canonical/checkbox/pull/541>`_
* Warning for skipped file at provider loading  `#545 <https://github.com/canonical/checkbox/pull/545>`_
* Add link anchors to documentation and fix broken link to removed Plainbox docs  `#543 <https://github.com/canonical/checkbox/pull/543>`_
* Enable CPU tests for ARM64  `#522 <https://github.com/canonical/checkbox/pull/522>`_
* Allow reusing containers in metabox provisioning  `#544 <https://github.com/canonical/checkbox/pull/544>`_
* Fix: Bug #539 - ``network.py`` crashes with ``ZeroDivisionError`` on some systems  `#546 <https://github.com/canonical/checkbox/pull/546>`_
* Change the menu text to something more clear  `#540 <https://github.com/canonical/checkbox/pull/540>`_
* Add Intel dGPU prime offload support  `#537 <https://github.com/canonical/checkbox/pull/537>`_

.. _v2.7:

V2.7 | 2023-06-14
------------------------


* Fix stream scraping in ``AssertPrint`` and ``AssertNotPrint``  `#456 <https://github.com/canonical/checkbox/pull/456>`_
* Doc starter pack  `#459 <https://github.com/canonical/checkbox/pull/459>`_
* Fix: Import checkbox-ng version from the repo not from pypi  `#461 <https://github.com/canonical/checkbox/pull/461>`_
* add: metabox scenarios for the daemon section  `#458 <https://github.com/canonical/checkbox/pull/458>`_
* Metabox testing for Test Plan Selection  `#452 <https://github.com/canonical/checkbox/pull/452>`_
* Fix the Metabox workflow to allow manual runs via workflow_dispatch  `#464 <https://github.com/canonical/checkbox/pull/464>`_
* Switch to the ZFS storage driver for LXD  `#465 <https://github.com/canonical/checkbox/pull/465>`_
* Add missing ``__init__.py`` in the config_files environment scenario  `#467 <https://github.com/canonical/checkbox/pull/467>`_
* Fix: make a warning about bad secure_id more informative  `#469 <https://github.com/canonical/checkbox/pull/469>`_
* fix: metabox exiting on successful rollback  `#470 <https://github.com/canonical/checkbox/pull/470>`_
* Metabox transport scenarios  `#471 <https://github.com/canonical/checkbox/pull/471>`_
* Removed wrong `-a` switch from bluetooth manual jobs  `#478 <https://github.com/canonical/checkbox/pull/478>`_
* Stop creating a base snapshot (before the provisioning phase)  `#483 <https://github.com/canonical/checkbox/pull/483>`_
* Add MIT license for ``screenoff.sh``  `#474 <https://github.com/canonical/checkbox/pull/474>`_
* Add missing python package dependencies (pyparsing and packaging)  `#484 <https://github.com/canonical/checkbox/pull/484>`_
* Metabox provisioning does not carry file permissions  `#486 <https://github.com/canonical/checkbox/pull/486>`_
* Documentation migration  `#468 <https://github.com/canonical/checkbox/pull/468>`_
* Minor fix for wrong usage of unit type in a test  `#495 <https://github.com/canonical/checkbox/pull/495>`_
* Metabox Install instead of sideloading providers  `#500 <https://github.com/canonical/checkbox/pull/500>`_
* Use ``glmark2`` package from repositories rather than compiling it  `#499 <https://github.com/canonical/checkbox/pull/499>`_
* Bump ``fwts`` version from V23.01.00 to V23.05.00 in checkbox runtime snaps  `#503 <https://github.com/canonical/checkbox/pull/503>`_
* Add manifest scenarios to metabox  `#466 <https://github.com/canonical/checkbox/pull/466>`_
* Update stress-ng part to v0.15.08 in checkbox-core-snap  `#505 <https://github.com/canonical/checkbox/pull/505>`_
* Improve graphic testing with Nvidia card  `#400 <https://github.com/canonical/checkbox/pull/400>`_
* Fix put crash metabox  `#473 <https://github.com/canonical/checkbox/pull/473>`_
* Fix: Bug #443 -- better optimize ``network.py`` high-speed network  `#479 <https://github.com/canonical/checkbox/pull/479>`_
* Show values of GROUP argument for list command help  `#496 <https://github.com/canonical/checkbox/pull/496>`_
* Fixed TP selection empty to be interactive  `#511 <https://github.com/canonical/checkbox/pull/511>`_
* Bump version: 2.6 → 2.7  `#514 <https://github.com/canonical/checkbox/pull/514>`_


.. _v2.6:

V2.6 | 2023-05-18
------------------------

* Update stress-ng part to v0.15.07 in checkbox-core-snap  `#432 <https://github.com/canonical/checkbox/pull/432>`_
* Fix link and spaces in release README  `#430 <https://github.com/canonical/checkbox/pull/430>`_
* FIX ``providers/base/bin/cpuid.py``: add another Sapphire Rapids ``CPUID``  `#421 <https://github.com/canonical/checkbox/pull/421>`_
* Add: set multiple MAC in one ``BTDEVADDR`` feature  `#424 <https://github.com/canonical/checkbox/pull/424>`_
* Fix docs (launchers tutorial, sphinx warning)  `#433 <https://github.com/canonical/checkbox/pull/433>`_
* Fix the release to stable workflow by cloning with full git history  `#434 <https://github.com/canonical/checkbox/pull/434>`_
* Require user to provide comment for manually skipped or failed cert-blockers  `#426 <https://github.com/canonical/checkbox/pull/426>`_
* Explain remote checkbox testing in CONTRIBUTING guide  `#438 <https://github.com/canonical/checkbox/pull/438>`_
* Add debugging info to the Metabox GitHub Action  `#441 <https://github.com/canonical/checkbox/pull/441>`_
* Add example in metabox README to check remote/service  `#442 <https://github.com/canonical/checkbox/pull/442>`_
* fix: print proper estimated runtime even when some jobs don't provide it  `#435 <https://github.com/canonical/checkbox/pull/435>`_
* Fix broken links in Checkbox contribution guide  `#447 <https://github.com/canonical/checkbox/pull/447>`_
* Update vendor ``RPyC`` 5.3.1  `#436 <https://github.com/canonical/checkbox/pull/436>`_
* Fix Checkbox configuration value resolution and add Metabox scenarios to test it  `#439 <https://github.com/canonical/checkbox/pull/439>`_
* Rework GitHub templates  `#449 <https://github.com/canonical/checkbox/pull/449>`_
* Add: USB-C OTG test  `#358 <https://github.com/canonical/checkbox/pull/358>`_
* Fix: checkbox crash for non-existent usernames and refactor user handling  `#451 <https://github.com/canonical/checkbox/pull/451>`_
* Bump version: 2.5 → 2.6  `#454 <https://github.com/canonical/checkbox/pull/454>`_


.. _v2.5:

V2.5 | 2023-04-21
------------------------

* Fix: Add new python3-packaging dependency to checkbox core snaps  `#405 <https://github.com/canonical/checkbox/pull/405>`_
* Fix docker test whitespace, services and version are top level keys  `#407 <https://github.com/canonical/checkbox/pull/407>`_
* Stable release workflow (promotion from beta to stable )  `#408 <https://github.com/canonical/checkbox/pull/408>`_
* Stable release workflow  `#409 <https://github.com/canonical/checkbox/pull/409>`_
* Fix checkbox-stable-release.yml, checkout the repo before calling GitHub release  `#410 <https://github.com/canonical/checkbox/pull/410>`_
* add zapper-enabled bt test  `#419 <https://github.com/canonical/checkbox/pull/419>`_
* Update the release README  `#417 <https://github.com/canonical/checkbox/pull/417>`_
* Add support for fish shell  `#425 <https://github.com/canonical/checkbox/pull/425>`_
* add ACPI OEM _OSI test  `#398 <https://github.com/canonical/checkbox/pull/398>`_
* Update stress-ng part to v0.15.07 in checkbox-core-snap  `#432 <https://github.com/canonical/checkbox/pull/432>`_


.. _v2.4:

V2.4 | 2023-04-02
------------------------

* Change: update the ``tbt3`` storage-test job command  `#389 <https://github.com/canonical/checkbox/pull/389>`_
* Open a new release for development  `#391 <https://github.com/canonical/checkbox/pull/391>`_
* Add git short SHA suffix to daily builds uploaded to the edge channel  `#392 <https://github.com/canonical/checkbox/pull/392>`_
* Add git short SHA suffix to daily builds uploaded to the edge channel  `#393 <https://github.com/canonical/checkbox/pull/393>`_
* Fix: Jinja2 3.1 compatibility (Lunar packaged version)  `#395 <https://github.com/canonical/checkbox/pull/395>`_
* Fix: Add new python3-packaging dependency  `#396 <https://github.com/canonical/checkbox/pull/396>`_
* Fix: Docker Compose compatibility with v1 removal  `#399 <https://github.com/canonical/checkbox/pull/399>`_
* Added OPEN_AX_SSID variable  `#394 <https://github.com/canonical/checkbox/pull/394>`_
* Unify versioning within Debian packages and with snaps  `#402 <https://github.com/canonical/checkbox/pull/402>`_
* Bump version: 2.3 → 2.4  `#403 <https://github.com/canonical/checkbox/pull/403>`_
