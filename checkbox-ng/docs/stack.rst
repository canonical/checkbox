The "Checkbox Stack"
====================

The Checkbox Stack is a collection of projects that together constitute a
complete testing and certification solution. It is composed of the following
parts (see table below). All of the projects are linked to from the 
`Launchpad project group <https://launchpad.net/checkbox-project>`_.

+------------------------+---------------------------------------+-------------+
| Project                | Responsible for                       |    Type     |
+========================+=======================================+=============+
| Next Generation        | - The C++/QML user interface          | Application |
| Checkbox (GUI)         | - The graphical launcher for          |             |
|                        |   providers, e.g.                     |             |
|                        |   checkbox-certification-client       |             |
+------------------------+---------------------------------------+-------------+
| Next Generation        | - The python command-line interface   | Application |
| Checkbox (CLI)         |                                       |             |
|                        |   - the text user interface           |             |
|                        |   - the SRU testing command           |             |
|                        |                                       |             |
|                        | - Additional certification APIs       |             |
|                        |                                       |             |
|                        |   - sending data to Launchpad         |             |
|                        |   - sending data to HEXR              |             |
|                        |                                       |             |
|                        | - the DBus service needed by GUI      |             |
+------------------------+---------------------------------------+-------------+
| Client Certification   | - canonical-certification-client      | Provider    |
| Provider               |   executable                          |             |
|                        | - client certification whitelists     |             |
+------------------------+---------------------------------------+-------------+
| Server Certification   | - server certification whitelists     | Provider    |
| Provider               | - additional server whitelists        |             |
+------------------------+---------------------------------------+-------------+
| System-on-Chip Server  | - SoC server certification whitelists | Provider    |
| Certification Provider |                                       |             |
+------------------------+---------------------------------------+-------------+
| Checkbox Provider      | - Almost all job definitions          | Provider    |
|                        | - Most of custom "scripts"            |             |
|                        | - Default and SRU whitelist           |             |
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
|                        |   - The XML, HTML and XSLX exporters  |             |
|                        |   - and more...                       |             |
|                        |                                       |             |
|                        | - Provider development toolkit        |             |
|                        |                                       |             |
|                        |   - 'plainbox startprovider'          |             |
|                        |   - 'manage.py' implementation        |             |
+------------------------+---------------------------------------+-------------+
| Legacy Checkbox        | - Applications                        | Monolithic  |
| (no longer maintained) |                                       | Application |
|                        |   - Qt4 GUI                           | Library     |
|                        |   - Gtk2 GUI                          | and Data    |
|                        |   - Urwid (text) GUI                  |             |
|                        |                                       |             |
|                        | - Core                                |             |
|                        |                                       |             |
|                        |   - Plugin and Event / Message Engine |             |
|                        |   - Almost Every feature implemented  |             |
|                        |     a core plugin                     |             |
|                        |                                       |             |
|                        | - Data                                |             |
|                        |                                       |             |
|                        |   - Jobs and whitelists               |             |
+------------------------+---------------------------------------+-------------+
