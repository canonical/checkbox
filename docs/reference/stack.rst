The "Checkbox Stack"
====================

The Checkbox Stack is a collection of projects that together constitute a
complete testing and certification solution. It is composed of the following
parts (see table below for extra details). All of the projects are linked to
from the `Launchpad project group <https://launchpad.net/checkbox-project>`_.

Component Descriptions
----------------------

+------------------------+---------------------------------------+-------------+
| Project                | Responsible for                       |    Type     |
+========================+=======================================+=============+
| Checkbox (CLI)         | - The python command-line interface   | Application |
|                        |                                       |             |
|                        |   - the text user interface           |             |
|                        |                                       |             |
|                        | - Additional certification APIs       |             |
|                        |                                       |             |
|                        |   - sending data to Certification     |             |
|                        |     website (C3)                      |             |
+------------------------+---------------------------------------+-------------+
| Client Certification   | - canonical-certification-client      | Provider    |
| Provider               |   executable                          |             |
|                        | - client certification test plans     |             |
+------------------------+---------------------------------------+-------------+
| Server Certification   | - server certification test plans     | Provider    |
| Provider               | - additional server test plans        |             |
+------------------------+---------------------------------------+-------------+
| Checkbox Provider      | - Generic (all platform) job          | Provider    |
|                        |   definitions                         |             |
|                        | - Most of custom "scripts"            |             |
|                        | - Default and SRU test plans          |             |
+------------------------+---------------------------------------+-------------+
| Resource Provider      | - Generic resource jobs               | Provider    |
|                        | - Generic binaries for those jobs     |             |
+------------------------+---------------------------------------+-------------+
| Snappy Provider        | - Job definitions aimed mostly at     |             |
|                        |   Ubuntu Core systems                 |             |
|                        | - "Snap aware" jobs                   |             |
+------------------------+---------------------------------------+-------------+
| Checkbox Support       | - Support code for various providers  | Library     |
|                        | - Parsers for many text formats       |             |
+------------------------+---------------------------------------+-------------+
| PlainBox               | - Almost all core logic               | Library     |
| (part of Checkbox)     |                                       | and         |
|                        |   - RFC822 (job definition) parser    | Development |
|                        |   - Configuration handling            | Toolkit     |
|                        |   - Testing session (suspend/resume)  |             |
|                        |   - Job runner                        |             |
|                        |   - Trusted launcher                  |             |
|                        |   - Dependency resolver               |             |
|                        |   - Command line handling             |             |
|                        |   - The HTML and XSLX exporters       |             |
|                        |   - and more...                       |             |
+------------------------+---------------------------------------+-------------+
