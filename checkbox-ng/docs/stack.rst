The "Checkbox Stack"
====================

The Checkbox Stack is a collection of projects that together constitute a
complete testing and certification solution. It is composed of the following
parts (see table below for extra details). All of the projects are linked to
from the `Launchpad project group <https://launchpad.net/checkbox-project>`_.

Architecture Diagram
--------------------

.. image:: _images/Checkbox-Stack-Architecture.svg
    :alt: Architecture Diagram

This diagram contains a high-level approximation of the current Checkbox
architecture. There are three main "pillars". On the left we have *end
products*. Those are actual tools that certification and engineers are using.
On the right we have the *test market*. This is a open market of tests vendors
and suppliers. The tests are wrapped in containers known as providers. In the
center we have three shared components. Those implement the bulk of the
framework and user interfaces for test execution. Finally in the bottom-left
corner there is a part of checkbox (a library) that is shared with HEXR for
certain tasks. HEXR is a out-of-scope web application used by part of the
certification process. Arrows imply communication with the shape of the arrow
shows who calls who.

As mentioned before, in the center column there are three main components of
shared code (shared by everyone using the end products that are discussed
below). The shared code is composed of plainbox, checkbox and
checkbox-converged.  Component responsibilities are discussed in more detail in
the table below.  Here we can see that checkbox and checkbox-converged use
plainbox API.  checkbox-converged does so using pyotherside, and checkbox uses
this api directly through python 3.

In the right hand side column there are various test providers. The checkbox
project is producing and maintaining a number of providers (see the table
below) but it is expected that our downstream users will also produce their own
providers (specific to a customer or project). Eventually some providers may
come from third parties that will adopt the format.

Lastly in the bottom-left corner, the shared library, this library contains
many parsers of various file formats and output formats. Technically this
library is a dependency of HEXR, checkbox *and* of providers. As an added
complexity the library needs to be called from python3 code and python2 code.

.. note::
    The communication between checkbox and plainbox is bi-directional.
    Plainbox offers some base interfaces and extension points. Those are all
    exposed through plainbox (using common APIs) but some of those are actually
    implemented in checkbox-ng.

.. warning::
    All internal APIs is considered unstable. 
    Stable APIs include:

    * unit definitions
    * SessionAssistant API
    * launcher syntax

Component Descriptions
----------------------

+------------------------+---------------------------------------+-------------+
| Project                | Responsible for                       |    Type     |
+========================+=======================================+=============+
| Checkbox-Converged     | - The QML user interface              | Application |
|                        | - The graphical launcher for          |             |
|                        |   providers, e.g.                     |             |
|                        |   checkbox-certification-client       |             |
+------------------------+---------------------------------------+-------------+
| Checkbox (CLI)         | - The python command-line interface   | Application |
|                        |                                       |             |
|                        |   - the text user interface           |             |
|                        |                                       |             |
|                        | - Additional certification APIs       |             |
|                        |                                       |             |
|                        |   - sending data to HEXR              |             |
+------------------------+---------------------------------------+-------------+
| Client Certification   | - canonical-certification-client      | Provider    |
| Provider               |   executable                          |             |
|                        | - client certification test plans     |             |
+------------------------+---------------------------------------+-------------+
| Server Certification   | - server certification test plans     | Provider    |
| Provider               | - additional server test plans        |             |
+------------------------+---------------------------------------+-------------+
| System-on-Chip Server  | - SoC server certification test plans | Provider    |
| Certification Provider |                                       |             |
+------------------------+---------------------------------------+-------------+
| Checkbox Provider      | - Almost all job definitions          | Provider    |
|                        | - Most of custom "scripts"            |             |
|                        | - Default and SRU test plans          |             |
+------------------------+---------------------------------------+-------------+
| Resource Provider      | - Almost all resource jobs            | Provider    |
|                        | - Almost all resource "scripts"       |             |
+------------------------+---------------------------------------+-------------+
| Checkbox Support       | - Support code for various providers  | Library     |
|                        | - Parsers for many text formats       |             |
+------------------------+---------------------------------------+-------------+
| PlainBox               | - Almost all core logic               | Library     |
|                        |                                       | and         |
|                        |   - RFC822 (job definition) parser    | Development |
|                        |   - Configuration handling            | Toolkit     |
|                        |   - Testing session (suspend/resume)  |             |
|                        |   - Job runner                        |             |
|                        |   - Trusted launcher                  |             |
|                        |   - Dependency resolver               |             |
|                        |   - Command line handling             |             |
|                        |   - The HTML and XSLX exporters       |             |
|                        |   - and more...                       |             |
|                        |                                       |             |
|                        | - Provider development toolkit        |             |
|                        |                                       |             |
|                        |   - 'plainbox startprovider'          |             |
|                        |   - 'manage.py' implementation        |             |
+------------------------+---------------------------------------+-------------+
