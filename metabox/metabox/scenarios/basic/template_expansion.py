# This file is part of Checkbox.
#
# Copyright 2024 Canonical Ltd.
#
# Checkbox is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3,
# as published by the Free Software Foundation.
#
# Checkbox is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Checkbox.  If not, see <http://www.gnu.org/licenses/>.

import textwrap

from metabox.core.scenario import Scenario
from metabox.core.actions import AssertRetCode, Start, AssertPrinted
from metabox.core.utils import tag


@tag("template", "basic")
class InvalidUnitErrorUserVisible(Scenario):
    """
    Check that when Checkbox expands a template it correctly detects
    if some of the expanded units are invalid and reports it to the user
    """

    launcher = textwrap.dedent(
        """
        #!/usr/bin/env checkbox-cli
        [launcher]
        launcher_version = 1
        stock_reports = text, submission_files
        [test plan]
        unit = 2021.com.canonical.certification::report_missing_parameters_generated_units
        forced = yes
        [ui]
        type=silent
        [test selection]
        forced=yes
        [transport:local_file]
        type=file
        path=c3-local-submission.tar.xz
        [exporter:example_tar]
        unit = com.canonical.plainbox::tar
        [report:file]
        transport = local_file
        exporter = tar
        forced = yes
        """
    )
    steps = [
        Start(),
        AssertPrinted("template_validation_invalid_fields_somename"),
        AssertPrinted("Outcome: job passed"),
        AssertPrinted("template_validation_invalid_fields_invalid_body"),
        AssertPrinted("Outcome: job failed"),
        AssertPrinted("template_validation_missing_parameter_MISSING_PARAM_1"),
        AssertPrinted("Outcome: job failed"),
        AssertRetCode(1),
    ]


@tag("template", "resume", "basic")
class LocalResumeInvalidUnitErrorUserVisible(Scenario):
    """
    Check that when Checkbox expands a template it correctly detects
    if some of the expanded units are invalid and reports it to the user
    """

    modes = ["local"]
    launcher = textwrap.dedent(
        """
        #!/usr/bin/env checkbox-cli
        [launcher]
        launcher_version = 1
        stock_reports = text, submission_files
        [test plan]
        unit = 2021.com.canonical.certification::resume_report_missing_parameters_generated_units
        forced = yes
        [ui]
        type=silent
        [test selection]
        forced=yes
        [transport:local_file]
        type=file
        path=c3-local-submission.tar.xz
        [exporter:example_tar]
        unit = com.canonical.plainbox::tar
        [report:file]
        transport = local_file
        exporter = tar
        forced = yes
        """
    )
    steps = [
        Start(),
        AssertPrinted("reboot-emulator"),
        Start(),
        AssertPrinted("template_validation_invalid_fields_somename"),
        AssertPrinted("job passed"),
        AssertPrinted("template_validation_invalid_fields_invalid_body"),
        AssertPrinted("job failed"),
        AssertPrinted("template_validation_missing_parameter_MISSING_PARAM_1"),
        AssertPrinted("job failed"),
        AssertPrinted("job passed"),
        AssertPrinted("job passed"),
        AssertPrinted("job failed"),
        AssertPrinted("job failed"),
        AssertRetCode(1),
    ]


@tag("template", "resume", "basic")
class RemoteResumeInvalidUnitErrorUserVisible(Scenario):
    """
    Check that when Checkbox expands a template it correctly detects
    if some of the expanded units are invalid and reports it to the user
    """

    modes = ["remote"]
    launcher = textwrap.dedent(
        """
        #!/usr/bin/env checkbox-cli
        [launcher]
        launcher_version = 1
        stock_reports = text, submission_files
        [test plan]
        unit = 2021.com.canonical.certification::resume_report_missing_parameters_generated_units
        forced = yes
        [ui]
        type=silent
        [test selection]
        forced=yes
        [transport:local_file]
        type=file
        path=c3-local-submission.tar.xz
        [exporter:example_tar]
        unit = com.canonical.plainbox::tar
        [report:file]
        transport = local_file
        exporter = tar
        forced = yes
        """
    )
    steps = [
        Start(),
        AssertPrinted("reboot-emulator"),
        AssertPrinted("template_validation_invalid_fields_somename"),
        AssertPrinted("job passed"),
        AssertPrinted("template_validation_invalid_fields_invalid_body"),
        AssertPrinted("job failed"),
        AssertPrinted("template_validation_missing_parameter_MISSING_PARAM_1"),
        AssertPrinted("job failed"),
        AssertPrinted("job passed"),
        AssertPrinted("job passed"),
        AssertPrinted("job failed"),
        AssertPrinted("job failed"),
        AssertRetCode(1),
    ]
