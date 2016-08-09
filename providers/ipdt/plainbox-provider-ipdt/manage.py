#!/usr/bin/env python3
# Copyright 2015 Canonical Ltd.
# All rights reserved.
#
# Written by:
#   Zygmunt Krynicki <zygmunt.krynicki@canonical.com>

"""Management script for the snappy provider."""

from plainbox.impl.secure.qualifiers import select_jobs
from plainbox.impl.session import SessionState
from plainbox.provider_manager import ManageCommand
from plainbox.provider_manager import manage_py_extension
from plainbox.provider_manager import setup, N_, _


def nr_rows_of(text):
    """Get the number of rows / lines in some text."""
    return text.count("\n") + 1

assert nr_rows_of("foo") == 1
assert nr_rows_of("foo\nbar") == 2


def nr_cols_of(text):
    """Get the number of columns in some text."""
    return max((len(line) for line in text.splitlines()), default=0)

assert nr_cols_of("foo") == 3
assert nr_cols_of("foo\nfroz") == 4

# XXX: All width/height sizing below is flawed but that is the best we can do.
# It seems that width is in "characters" (but this breaks because of
# proportional font) but height is in pixels. In either case we don't know the
# font used.

# XXX: this is picked manually by trial and error
HEIGHT_FACTOR = 14
HEIGHT_PADDING = 6

# XXX: This tries to approximate average width of characters
WIDTH_FACTOR = 1.1
WIDTH_PADDING = 0.5


@manage_py_extension
class TestPlanReport(ManageCommand):

    """
    Generate a Test Plan Report.

    This command generates a test plan report. It creates a spreadsheet (.xlsx)
    with a tab for each test plan and a common tab with the pool of test
    definitions referenced by those plans.

    @EPILOG@

    NOTE: To use this command, you will need python3-xlsxwriter package to be
    installed.
    """

    name = "test-plan-report"

    def invoked(self, ns):
        """Method called when this command selected on command line."""
        try:
            from xlsxwriter.workbook import Workbook
        except ImportError:
            print("You need to install python3-xlsxwriter")
            return 1
        else:
            with open(ns.output, 'wb') as stream:
                workbook = Workbook(stream)
                self._populate_workbook(workbook)
                workbook.close()

    def _populate_workbook(self, workbook):
        """Populate the workbook with report data."""
        provider = self.get_provider()
        test_plan_list = sorted(
            (unit for unit in provider.unit_list
             if unit.Meta.name == 'test plan'),
            key=lambda unit: unit.name)
        self._add_all_jobs_sheet(workbook, provider.job_list)
        for plan in test_plan_list:
            self._add_test_plan_sheet(workbook, plan, provider.job_list)

    def _add_all_jobs_sheet(self, workbook, job_list):
        """Populate the sheet with test definitions."""
        # Sort jobs by category and ID
        job_list.sort(key=lambda job: (job.category_id, job.partial_id))
        # Create a sheet for test definitions
        sheet = workbook.add_worksheet(
            _('Test Definitions (Jobs)'))
        # Define cell formatting
        fmt_header = workbook.add_format({
            'bold': True,
            'font_color': '#ffffff',
            'bg_color': '#77216f',  # Light Aubergine
        })
        fmt_code = workbook.add_format({
            'font_name': 'courier',
        })
        fmt_info = workbook.add_format({
            'font_color': '#dd4814',  # Ubuntu Orange
            'font_name': 'Ubuntu',
            'font_size': 16,
        })
        # Create a section with static information
        sheet.merge_range('A1:C3', _("Test Descriptions"), fmt_info)
        sheet.set_row(1, 30)
        # We can add anything we want to all the rows in range(INFO_OFFSET)
        INFO_OFFSET = 3

        def max_of(callback):
            """Get the maximum of some function applied to each job."""
            return max((callback(job) for job in job_list), default=0)

        COL_CATEGORY, COL_ID, COL_DESC, COL_COMMAND, COL_DURATION = range(5)
        # Add columns: category, id and description
        sheet.write(INFO_OFFSET, COL_CATEGORY, _("Category"), fmt_header)
        sheet.write(INFO_OFFSET, COL_ID, _("Test Case ID"), fmt_header)
        sheet.write(INFO_OFFSET, COL_DESC, _("Description"), fmt_header)
        sheet.write(INFO_OFFSET, COL_COMMAND, _("Command"), fmt_header)
        sheet.write(INFO_OFFSET, COL_DURATION, _("Duration"), fmt_header)
        sheet.set_row(INFO_OFFSET, HEIGHT_FACTOR + HEIGHT_PADDING)
        # Size our columns according to the data we have
        sheet.set_column(
            COL_CATEGORY, COL_CATEGORY, max_of(
                # XXX: no, this is not the category name
                lambda job: nr_cols_of(job.category_id.split("::")[1])
            ) * WIDTH_FACTOR + WIDTH_PADDING)
        sheet.set_column(
            COL_ID, COL_ID, max_of(
                lambda job: nr_cols_of(job.partial_id)
            ) * WIDTH_FACTOR + WIDTH_PADDING)
        sheet.set_column(
            COL_DESC, COL_DESC, max_of(
                lambda job: nr_cols_of(job.tr_description())
            ) * WIDTH_FACTOR + WIDTH_PADDING)
        sheet.set_column(
            COL_COMMAND, COL_COMMAND, max_of(
                lambda job: nr_cols_of(job.command or "")
            ) * WIDTH_FACTOR + WIDTH_PADDING)
        sheet.set_column(COL_DURATION, COL_DURATION, 10)
        # Add the definition of each job as a separate row
        for index, job in enumerate(job_list, INFO_OFFSET + 1):
            # NOTE: assume the height of each row is dominated by description
            sheet.set_row(index, nr_rows_of(
                job.tr_description()
            ) * HEIGHT_FACTOR + HEIGHT_PADDING)
            # XXX: no, this is not the category name
            sheet.write(
                index, COL_CATEGORY, job.category_id.split("::")[1], fmt_code)
            sheet.write(index, COL_ID, job.partial_id, fmt_code)
            sheet.write(index, COL_DESC, job.tr_description())
            sheet.write(index, COL_COMMAND, job.command, fmt_code)
            sheet.write(index, COL_DURATION, '{:.0f}m {:.0f}s'.format(*divmod(
                job.estimated_duration, 60)))
        # Make sure the sheet is read only
        sheet.protect()

    def _add_test_plan_sheet(self, workbook, plan, job_list):
        """A sheet for a given test plan."""
        # Create a sheet for this test plan
        sheet = workbook.add_worksheet(
            _('{}').format(plan.tr_name()))
        # Define cell formatting
        fmt_header = workbook.add_format({
            'bold': True,
            'font_color': '#ffffff',
            'bg_color': '#77216f',  # Light Aubergine
        })
        fmt_code = workbook.add_format({
            'font_name': 'courier',
        })
        fmt_info = workbook.add_format({
            'font_color': '#dd4814',  # Ubuntu Orange
            'font_name': 'Ubuntu',
            'font_size': 16,
        })
        # Create a section with static information
        sheet.write('A2', _("Test Plan Name"), fmt_info)
        sheet.write('B2', plan.tr_name())
        sheet.write('A3', _("Test Plan ID"), fmt_info)
        sheet.write('B3', plan.id, fmt_code)
        sheet.merge_range(
            'A4:B4', 'TIP: plainbox run -T {}'.format(plan.id), fmt_code)
        # We can add anything we want to all the rows in range(INFO_OFFSET)
        INFO_OFFSET = 5
        # Find what is the effective run list of this test plan
        state = SessionState(job_list)
        state.update_desired_job_list(
            select_jobs(job_list, [plan.get_qualifier()]))

        def max_of(callback):
            """Get the maximum of some function applied to each job."""
            return max((callback(job) for job in state.run_list), default=0)
        COL_ID, COL_SUMMARY = range(2)
        # Add columns: id
        sheet.write(INFO_OFFSET, COL_ID, _("Test Case ID"), fmt_header)
        sheet.write(INFO_OFFSET, COL_SUMMARY, _("Summary"), fmt_header)
        sheet.set_column(
            COL_ID, COL_ID, max_of(
                lambda job: nr_cols_of(job.partial_id)
            ) * WIDTH_FACTOR + WIDTH_PADDING)
        sheet.set_column(
            COL_SUMMARY, COL_SUMMARY, max_of(
                lambda job: nr_cols_of(job.tr_summary())
            ) * WIDTH_FACTOR + WIDTH_PADDING)
        # Add the information about each job as a separate row
        for index, job in enumerate(state.run_list, INFO_OFFSET + 1):
            sheet.set_row(index, HEIGHT_FACTOR + HEIGHT_PADDING)
            sheet.write(index, COL_ID, job.partial_id, fmt_code)
            sheet.write(index, COL_SUMMARY, job.tr_summary())
        # Make sure the sheet is read only
        sheet.protect()

    def register_parser(self, subparsers):
        """Method called to define arguments this command understands."""
        parser = self.add_subcommand(subparsers)
        parser.add_argument(
            'output', metavar=_("FILE"),
            help=_("path of the .xlsx file to write"))


setup(
    name='plainbox-provider-ipdt',
    namespace='2016.com.intel.ipdt',
    version="0.1",
    description=N_("Plainbox Provider for IPDT"),
    gettext_domain='plainbox-provider-ipdt',
)
