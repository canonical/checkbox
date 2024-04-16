# This file is part of Checkbox.
#
# Copyright 2013 Canonical Ltd.
# Written by:
#   Sylvain Pineau <sylvain.pineau@canonical.com>
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

"""
:mod:`plainbox.impl.exporter.xlsx`
==================================

XLSX exporter

.. warning::
    THIS MODULE DOES NOT HAVE A STABLE PUBLIC API
"""

from base64 import standard_b64decode
from collections import defaultdict, OrderedDict
import re

# Lazy load these modules
# from xlsxwriter.workbook import Workbook
# from xlsxwriter.utility import xl_rowcol_to_cell

from plainbox import get_version_string
from plainbox.abc import IJobResult
from plainbox.i18n import gettext as _, ngettext
from plainbox.impl.exporter import SessionStateExporterBase
from plainbox.impl.result import OUTCOME_METADATA_MAP as OMM


class XLSXSessionStateExporter(SessionStateExporterBase):
    """
    Session state exporter creating XLSX documents

    The hardware devices are extracted from the content of the following
    attachment:

    * com.canonical.certification::lspci_attachment

    The following resource jobs are needed to populate the system info section
    of this report:

    * com.canonical.certification::dmi
    * com.canonical.certification::device
    * com.canonical.certification::cpuinfo
    * com.canonical.certification::meminfo
    * com.canonical.certification::package
    """

    OPTION_WITH_SYSTEM_INFO = "with-sys-info"
    OPTION_WITH_SUMMARY = "with-summary"
    OPTION_WITH_DESCRIPTION = "with-job-description"
    OPTION_WITH_TEXT_ATTACHMENTS = "with-text-attachments"
    OPTION_TEST_PLAN_EXPORT = "tp-export"

    SUPPORTED_OPTION_LIST = (
        OPTION_WITH_SYSTEM_INFO,
        OPTION_WITH_SUMMARY,
        OPTION_WITH_DESCRIPTION,
        OPTION_WITH_TEXT_ATTACHMENTS,
        OPTION_TEST_PLAN_EXPORT,
    )

    def __init__(self, option_list=None, exporter_unit=None):
        """
        Initialize a new XLSXSessionStateExporter.
        """
        # Super-call with empty option list
        super().__init__((), exporter_unit=exporter_unit)
        # All the "options" are simply a required configuration element and are
        # not optional in any way. There is no way to opt-out.
        if option_list is None:
            option_list = ()
        for option in option_list:
            if option not in self.supported_option_list:
                raise ValueError(_("Unsupported option: {}").format(option))
        if exporter_unit:
            for option in exporter_unit.option_list:
                if option not in self.supported_option_list:
                    raise ValueError(
                        _("Unsupported option: {}").format(option)
                    )
        self._option_list = (
            SessionStateExporterBase.OPTION_WITH_IO_LOG,
            SessionStateExporterBase.OPTION_FLATTEN_IO_LOG,
            SessionStateExporterBase.OPTION_WITH_COMMENTS,
            SessionStateExporterBase.OPTION_WITH_JOB_DEFS,
            SessionStateExporterBase.OPTION_WITH_RESOURCE_MAP,
            SessionStateExporterBase.OPTION_WITH_ATTACHMENTS,
            SessionStateExporterBase.OPTION_WITH_CATEGORY_MAP,
            SessionStateExporterBase.OPTION_WITH_CERTIFICATION_STATUS,
        )
        self._option_list += tuple(option_list)
        if exporter_unit:
            self._option_list += tuple(exporter_unit.option_list)
        self.total_pass = 0
        self.total_fail = 0
        self.total_skip = 0
        self.total = 0

    def _set_formats(self):
        # Main Title format (Orange)
        self.format01 = self.workbook.add_format(
            {
                "align": "left",
                "size": 24,
                "font_color": "#DC4C00",
            }
        )
        # Default font
        self.format02 = self.workbook.add_format(
            {
                "align": "left",
                "valign": "vcenter",
                "size": 10,
            }
        )
        # Titles
        self.format03 = self.workbook.add_format(
            {
                "align": "left",
                "size": 12,
                "bold": 1,
            }
        )
        # Titles + borders
        self.format04 = self.workbook.add_format(
            {"align": "left", "size": 12, "bold": 1, "border": 1}
        )
        # System info with borders
        self.format05 = self.workbook.add_format(
            {
                "align": "left",
                "valign": "vcenter",
                "text_wrap": 1,
                "size": 8,
                "border": 1,
            }
        )
        # System info with borders, grayed out background
        self.format06 = self.workbook.add_format(
            {
                "align": "left",
                "valign": "vcenter",
                "text_wrap": 1,
                "size": 8,
                "border": 1,
                "bg_color": "#E6E6E6",
            }
        )
        self.format06_2 = self.workbook.add_format(
            {
                "align": "left",
                "valign": "vcenter",
                "text_wrap": 1,
                "size": 8,
                "border": 1,
                "bg_color": "#E6E6E6",
                "bold": 1,
            }
        )
        # Headlines (center)
        self.format07 = self.workbook.add_format(
            {
                "align": "center",
                "size": 10,
                "bold": 1,
            }
        )
        # Table rows without borders
        self.format08 = self.workbook.add_format(
            {
                "align": "left",
                "valign": "vcenter",
                "text_wrap": 1,
                "size": 8,
            }
        )
        # Table rows without borders, grayed out background
        self.format09 = self.workbook.add_format(
            {
                "align": "left",
                "valign": "vcenter",
                "text_wrap": 1,
                "size": 8,
                "bg_color": "#E6E6E6",
            }
        )
        # Green background / Size 8
        self.format10 = self.workbook.add_format(
            {
                "align": "center",
                "valign": "vcenter",
                "text_wrap": 1,
                "size": 8,
                "bg_color": "lime",
                "border": 1,
                "border_color": "white",
            }
        )
        # Red background / Size 8
        self.format11 = self.workbook.add_format(
            {
                "align": "center",
                "valign": "vcenter",
                "text_wrap": 1,
                "size": 8,
                "bg_color": "red",
                "border": 1,
                "border_color": "white",
            }
        )
        # Gray background / Size 8
        self.format12 = self.workbook.add_format(
            {
                "align": "center",
                "valign": "vcenter",
                "text_wrap": 1,
                "size": 8,
                "bg_color": "gray",
                "border": 1,
                "border_color": "white",
            }
        )
        # Dictionary with formats for each possible outcome
        self.outcome_format_map = {
            outcome_info.value: self.workbook.add_format(
                {
                    "align": "center",
                    "valign": "vcenter",
                    "text_wrap": "1",
                    "size": 8,
                    "bg_color": outcome_info.color_hex,
                    "border": 1,
                    "border_color": "white",
                }
            )
            for outcome_info in OMM.values()
        }
        # Attachments
        self.format13 = self.workbook.add_format(
            {
                "align": "left",
                "valign": "vcenter",
                "text_wrap": 1,
                "size": 8,
                "font": "Courier New",
            }
        )
        # Invisible man
        self.format14 = self.workbook.add_format({"font_color": "white"})
        # Headlines (left-aligned)
        self.format15 = self.workbook.add_format(
            {
                "align": "left",
                "size": 10,
                "bold": 1,
            }
        )
        # Table rows without borders, indent level 1
        self.format16 = self.workbook.add_format(
            {
                "align": "left",
                "valign": "vcenter",
                "size": 8,
                "indent": 1,
            }
        )
        # Table rows without borders, grayed out background, indent level 1
        self.format17 = self.workbook.add_format(
            {
                "align": "left",
                "valign": "vcenter",
                "size": 8,
                "bg_color": "#E6E6E6",
                "indent": 1,
            }
        )
        # Table rows without borders (center)
        self.format18 = self.workbook.add_format(
            {
                "align": "center",
                "valign": "vcenter",
                "size": 8,
            }
        )
        # Table rows without borders, grayed out background (center)
        self.format19 = self.workbook.add_format(
            {
                "align": "center",
                "valign": "vcenter",
                "size": 8,
                "bg_color": "#E6E6E6",
            }
        )

    def _hw_collection(self, data):
        hw_info = defaultdict(lambda: "NA")
        resource = "com.canonical.certification::dmi"
        if resource in data["resource_map"]:
            result = [
                "{} {} ({})".format(
                    i.get("vendor"), i.get("product"), i.get("version")
                )
                for i in data["resource_map"][resource]
                if i.get("category") == "SYSTEM"
            ]
            if result:
                hw_info["platform"] = result.pop()
            result = [
                "{}".format(i.get("version"))
                for i in data["resource_map"][resource]
                if i.get("category") == "BIOS"
            ]
            if result:
                hw_info["bios"] = result.pop()
        resource = "com.canonical.certification::cpuinfo"
        if resource in data["resource_map"]:
            result = [
                "{} x {}".format(i.get("model"), i.get("count"))
                for i in data["resource_map"][resource]
            ]
            if result:
                hw_info["processors"] = result.pop()
        resource = "com.canonical.certification::lspci_attachment"
        if resource in data["attachment_map"]:
            lspci = data["attachment_map"][resource]
            content = standard_b64decode(lspci.encode()).decode("UTF-8")
            match = re.search(
                r"ISA bridge.*?:\s(?P<chipset>.*?)\sLPC", content
            )
            if match:
                hw_info["chipset"] = match.group("chipset")
            match = re.search(
                r"Audio device.*?:\s(?P<audio>.*?)\s\[\w+:\w+]", content
            )
            if match:
                hw_info["audio"] = match.group("audio")
            match = re.search(
                r"Ethernet controller.*?:\s(?P<nic>.*?)\s\[\w+:\w+]", content
            )
            if match:
                hw_info["nic"] = match.group("nic")
            match = re.search(
                r"Network controller.*?:\s(?P<wireless>.*?)\s\[\w+:\w+]",
                content,
            )
            if match:
                hw_info["wireless"] = match.group("wireless")
            for i, match in enumerate(
                re.finditer(
                    r"VGA compatible controller.*?:\s(?P<video>.*?)\s\[\w+:\w+]",
                    content,
                ),
                start=1,
            ):
                hw_info["video{}".format(i)] = match.group("video")
            vram = 0
            for match in re.finditer(
                r"Memory.+ prefetchable\) \[size=(?P<vram>\d+)M\]", content
            ):
                vram += int(match.group("vram"))
            if vram:
                hw_info["vram"] = "{} MiB".format(vram)
        resource = "com.canonical.certification::meminfo"
        if resource in data["resource_map"]:
            result = [
                "{} GiB".format(
                    format(int(i.get("total", 0)) / 1073741824, ".1f")
                )
                for i in data["resource_map"][resource]
            ]
            if result:
                hw_info["memory"] = result.pop()
        bluetooth = self._get_bluetooth_product_or_path(data)
        if bluetooth:
            hw_info["bluetooth"] = bluetooth
        return hw_info

    def _get_resource_list(self, data, resource_id):
        """
        Get a list of resource objects associated with the specified job
        (resource) identifier

        :param data:
            Exporter data
        :param resource_id:
            Identifier of the job / resource
        :returns:
            A list of matching resource objects. If there are no resources of
            that kind then an empty list list returned.
        """
        resource_map = data.get("resource_map")
        if not resource_map:
            return []
        return resource_map.get(resource_id, [])

    def _get_bluetooth_product_or_path(
        self, data, resource_id="com.canonical.certification::device"
    ):
        """
        Get the 'product' or 'path' of the first bluetooth device.

        :param data:
            Exporter data
        :param resource_id:
            (optional) Identifier of the device resource.
        :returns:
            The 'product' attribute, or the 'path' attribute or None if no such
            device can be found.

        This method finds the name of the 'product' or 'path' attributes (first
        available one wins) associated with a resource that has a 'category'
        attribute equal to BLUETOOTH. The resource is looked using the supplied
        (default) resource identifier.
        """
        for resource in self._get_resource_list(data, resource_id):
            if resource.get("category") != "BLUETOOTH":
                continue
            if "product" in resource:
                return resource["product"]
            if "path" in resource:
                return resource["path"]

    def write_systeminfo(self, data):
        self.worksheet1.set_column(0, 0, 4)
        self.worksheet1.set_column(1, 1, 34)
        self.worksheet1.set_column(2, 3, 58)
        row = 3
        self.worksheet1.write(row, 1, _("Report created using"), self.format03)
        self.worksheet1.write(row, 2, get_version_string(), self.format03)
        hw_info = self._hw_collection(data)
        row += 2
        self.worksheet1.write(row, 1, _("Platform Name"), self.format03)
        self.worksheet1.write(row, 2, hw_info["platform"], self.format03)
        row += 2
        self.worksheet1.write(row, 1, _("BIOS"), self.format04)
        self.worksheet1.write(row, 2, hw_info["bios"], self.format06)
        row += 1
        self.worksheet1.write(row, 1, _("Processors"), self.format04)
        self.worksheet1.write(row, 2, hw_info["processors"], self.format05)
        row += 1
        self.worksheet1.write(row, 1, _("Chipset"), self.format04)
        self.worksheet1.write(row, 2, hw_info["chipset"], self.format06)
        row += 1
        self.worksheet1.write(row, 1, _("Memory"), self.format04)
        self.worksheet1.write(row, 2, hw_info["memory"], self.format05)
        row += 1
        # TRANSLATORS: on board as in 'built in card'
        self.worksheet1.write(row, 1, _("Video (on board)"), self.format04)
        self.worksheet1.write(row, 2, hw_info["video1"], self.format06)
        row += 1
        # TRANSLATORS: add-on as in dedicated graphics card
        self.worksheet1.write(row, 1, _("Video (add-on)"), self.format04)
        self.worksheet1.write(row, 2, hw_info["video2"], self.format05)
        row += 1
        self.worksheet1.write(row, 1, _("Video memory"), self.format04)
        self.worksheet1.write(row, 2, hw_info["vram"], self.format06)
        row += 1
        self.worksheet1.write(row, 1, _("Audio"), self.format04)
        self.worksheet1.write(row, 2, hw_info["audio"], self.format05)
        row += 1
        # TRANSLATORS: NIC is network interface card
        self.worksheet1.write(row, 1, _("NIC"), self.format04)
        self.worksheet1.write(row, 2, hw_info["nic"], self.format06)
        row += 1
        # TRANSLATORS: Wireless as in wireless network cards
        self.worksheet1.write(row, 1, _("Wireless"), self.format04)
        self.worksheet1.write(row, 2, hw_info["wireless"], self.format05)
        row += 1
        self.worksheet1.write(row, 1, _("Bluetooth"), self.format04)
        self.worksheet1.write(row, 2, hw_info["bluetooth"], self.format06)
        row += 2
        resource = "com.canonical.certification::package"
        if resource in data["resource_map"]:
            self.worksheet1.write(
                row, 1, _("Packages Installed"), self.format03
            )
            row += 2
            self.worksheet1.write_row(
                row, 1, [_("Name"), _("Version")], self.format07
            )
            row += 1
            for i in range(row - 2, row):
                self.worksheet1.set_row(
                    i, None, None, {"level": 1, "hidden": True}
                )
            packages_starting_row = row
            for i, pkg in enumerate(data["resource_map"][resource]):
                self.worksheet1.write_row(
                    packages_starting_row + i,
                    1,
                    [pkg.get("name", ""), pkg.get("version", "")],
                    self.format08 if i % 2 else self.format09,
                )
                self.worksheet1.set_row(
                    packages_starting_row + i,
                    None,
                    None,
                    {"level": 1, "hidden": True},
                )
            self.worksheet1.set_row(
                packages_starting_row + len(data["resource_map"][resource]),
                None,
                None,
                {"collapsed": True},
            )

    def write_summary(self, data):
        if self.total != 0:
            pass_rate = "{:.2f}%".format(self.total_pass / self.total * 100)
            fail_rate = "{:.2f}%".format(self.total_fail / self.total * 100)
            skip_rate = "{:.2f}%".format(self.total_skip / self.total * 100)
        else:
            pass_rate = _("N/A")
            fail_rate = _("N/A")
            skip_rate = _("N/A")
        self.worksheet2.set_column(0, 0, 5)
        self.worksheet2.set_column(1, 1, 2)
        self.worksheet2.set_column(3, 3, 27)
        self.worksheet2.write(3, 1, _("Failures summary"), self.format03)
        self.worksheet2.write(
            4, 1, OMM["pass"].unicode_sigil, self.outcome_format_map["pass"]
        )
        self.worksheet2.write(
            4,
            2,
            (
                ngettext(
                    "{} Test passed", "{} Tests passed", self.total_pass
                ).format(self.total_pass)
                + " - "
                + _("Success Rate: {} ({}/{})").format(
                    pass_rate, self.total_pass, self.total
                )
            ),
            self.format02,
        )
        self.worksheet2.write(
            5, 1, OMM["fail"].unicode_sigil, self.outcome_format_map["fail"]
        )
        self.worksheet2.write(
            5,
            2,
            (
                ngettext(
                    "{} Test failed", "{} Tests failed", self.total_fail
                ).format(self.total_fail)
                + " - "
                + _("Failure Rate: {} ({}/{})").format(
                    fail_rate, self.total_fail, self.total
                )
            ),
            self.format02,
        )
        self.worksheet2.write(
            6, 1, OMM["skip"].unicode_sigil, self.outcome_format_map["skip"]
        )
        self.worksheet2.write(
            6,
            2,
            (
                ngettext(
                    "{} Test skipped", "{} Tests skipped", self.total_skip
                ).format(self.total_skip)
                + " - "
                + _("Skip Rate: {} ({}/{})").format(
                    skip_rate, self.total_skip, self.total
                )
            ),
            self.format02,
        )
        self.worksheet2.write_column(
            "L3",
            [OMM["fail"].tr_label, OMM["skip"].tr_label, OMM["pass"].tr_label],
            self.format14,
        )
        self.worksheet2.write_column(
            "M3",
            [self.total_fail, self.total_skip, self.total_pass],
            self.format14,
        )
        # Configure the series.
        chart = self.workbook.add_chart({"type": "pie"})
        chart.set_legend({"position": "none"})
        chart.add_series(
            {
                "points": [
                    {"fill": {"color": OMM["fail"].color_hex}},
                    {"fill": {"color": OMM["skip"].color_hex}},
                    {"fill": {"color": OMM["pass"].color_hex}},
                ],
                "categories": "=" + _("Summary") + "!$L$3:$L$5",
                "values": "=" + _("Summary") + "!$M$3:$M$5",
            }
        )
        # Insert the chart into the worksheet.
        self.worksheet2.insert_chart(
            "F4",
            chart,
            {"x_offset": 0, "y_offset": 10, "x_scale": 0.50, "y_scale": 0.50},
        )

    def _tree(self, result_map, category_map):
        res = {}
        tmp_result_map = {}
        for job_name in result_map:
            category = category_map[result_map[job_name]["category_id"]]
            if category not in res:
                tmp_result_map[category] = {}
                tmp_result_map[category]["category_status"] = None
                tmp_result_map[category]["plugin"] = "local"
                tmp_result_map[category]["summary"] = category
                res[category] = {}
            res[category][job_name] = {}
            # Generate categories status
            child_status = result_map[job_name]["outcome"]
            if child_status == IJobResult.OUTCOME_FAIL:
                tmp_result_map[category][
                    "category_status"
                ] = IJobResult.OUTCOME_FAIL
            elif (
                child_status == IJobResult.OUTCOME_PASS
                and tmp_result_map[category]["category_status"]
                != IJobResult.OUTCOME_FAIL
            ):
                tmp_result_map[category][
                    "category_status"
                ] = IJobResult.OUTCOME_PASS
            elif tmp_result_map[category]["category_status"] not in (
                IJobResult.OUTCOME_PASS,
                IJobResult.OUTCOME_FAIL,
            ):
                tmp_result_map[category][
                    "category_status"
                ] = IJobResult.OUTCOME_SKIP
        result_map.update(tmp_result_map)
        return res, 2

    def _write_job(self, tree, result_map, max_level, level=0):
        for job, children in OrderedDict(
            sorted(
                tree.items(), key=lambda t: "z" + t[0] if t[1] else "a" + t[0]
            )
        ).items():
            if result_map[job]["plugin"] == "local" and not result_map[
                job
            ].get("category_status"):
                continue
            self._lineno += 1
            if children:
                self.worksheet3.write(
                    self._lineno,
                    level + 1,
                    result_map[job]["summary"],
                    self.format15,
                )
                outcome = result_map[job]["category_status"]
                self.worksheet3.write(
                    self._lineno,
                    max_level + 2,
                    OMM[outcome].tr_label,
                    self.outcome_format_map[outcome],
                )
                if self.OPTION_WITH_DESCRIPTION in self._option_list:
                    self.worksheet4.write(
                        self._lineno,
                        level + 1,
                        result_map[job].get(
                            "description", result_map[job].get("summary", "")
                        ),
                        self.format15,
                    )
                if level:
                    self.worksheet3.set_row(
                        self._lineno, 13, None, {"level": level}
                    )
                    if self.OPTION_WITH_DESCRIPTION in self._option_list:
                        self.worksheet4.set_row(
                            self._lineno, 13, None, {"level": level}
                        )
                else:
                    self.worksheet3.set_row(
                        self._lineno, 13, None, {"collapsed": True}
                    )
                    if self.OPTION_WITH_DESCRIPTION in self._option_list:
                        self.worksheet4.set_row(
                            self._lineno, 13, None, {"collapsed": True}
                        )
                self._write_job(children, result_map, max_level, level + 1)
            else:
                self.worksheet3.write(
                    self._lineno,
                    max_level + 1,
                    result_map[job]["summary"],
                    self.format08 if self._lineno % 2 else self.format09,
                )
                if self.OPTION_WITH_DESCRIPTION in self._option_list:
                    from xlsxwriter.utility import xl_rowcol_to_cell

                    link_cell = xl_rowcol_to_cell(self._lineno, max_level + 1)
                    self.worksheet3.write_url(
                        self._lineno,
                        max_level + 1,
                        "internal:" + _("Test Descriptions") + "!" + link_cell,
                        self.format08 if self._lineno % 2 else self.format09,
                        result_map[job]["summary"],
                    )
                    self.worksheet4.write(
                        self._lineno,
                        max_level + 1,
                        result_map[job]["summary"],
                        self.format08 if self._lineno % 2 else self.format09,
                    )
                self.total += 1
                outcome = result_map[job]["outcome"]
                self.worksheet3.write(
                    self._lineno,
                    max_level,
                    OMM[outcome].unicode_sigil,
                    self.outcome_format_map[outcome],
                )
                self.worksheet3.write(
                    self._lineno,
                    max_level + 2,
                    OMM[outcome].tr_label,
                    self.outcome_format_map[outcome],
                )
                if outcome == IJobResult.OUTCOME_PASS:
                    self.total_pass += 1
                elif outcome == IJobResult.OUTCOME_FAIL:
                    self.total_fail += 1
                else:
                    # NOTE: this is inaccurate but that's how the original code
                    # behaved. This will be fixed with detailed per-outcome
                    # counters later.
                    self.total_skip += 1
                cert_status = ""
                if "certification_status" in result_map[job]:
                    cert_status = result_map[job]["certification_status"]
                    if cert_status == "unspecified":
                        cert_status = ""
                self.worksheet3.write(
                    self._lineno,
                    max_level + 3,
                    cert_status,
                    self.format18 if self._lineno % 2 else self.format19,
                )
                io_log = " "
                if result_map[job]["plugin"] not in ("resource", "attachment"):
                    if result_map[job]["io_log"]:
                        io_log = (
                            standard_b64decode(
                                result_map[job]["io_log"].encode()
                            )
                            .decode("UTF-8")
                            .rstrip()
                        )
                io_lines = len(io_log.splitlines()) - 1
                if io_lines > 2:
                    io_log = "\n".join(io_log.splitlines()[:3]) + "\n[...]"
                    io_lines = len(io_log.splitlines()) - 1
                desc_lines = len(
                    result_map[job].get("description", "").splitlines()
                )
                desc_lines -= 1
                self.worksheet3.write(
                    self._lineno,
                    max_level + 4,
                    io_log,
                    self.format16 if self._lineno % 2 else self.format17,
                )
                comments = " "
                if result_map[job]["comments"]:
                    comments = result_map[job]["comments"].rstrip()
                self.worksheet3.write(
                    self._lineno,
                    max_level + 5,
                    comments,
                    self.format16 if self._lineno % 2 else self.format17,
                )
                if self.OPTION_WITH_DESCRIPTION in self._option_list:
                    self.worksheet4.write(
                        self._lineno,
                        max_level + 2,
                        result_map[job].get("description", ""),
                        self.format16 if self._lineno % 2 else self.format17,
                    )
                if level:
                    self.worksheet3.set_row(
                        self._lineno,
                        12 + 10.5 * io_lines,
                        None,
                        {"level": level, "hidden": True},
                    )
                    if self.OPTION_WITH_DESCRIPTION in self._option_list:
                        self.worksheet4.set_row(
                            self._lineno,
                            12 + 10.5 * desc_lines,
                            None,
                            {"level": level, "hidden": True},
                        )
                else:
                    self.worksheet3.set_row(
                        self._lineno,
                        12 + 10.5 * io_lines,
                        None,
                        {"hidden": True},
                    )
                    if self.OPTION_WITH_DESCRIPTION in self._option_list:
                        self.worksheet4.set_row(
                            self._lineno,
                            12 + 10.5 * desc_lines,
                            None,
                            {"hidden": True},
                        )

    def write_results(self, data):
        tree, max_level = self._tree(data["result_map"], data["category_map"])
        self.worksheet3.write(3, 1, _("Tests Performed"), self.format03)
        self.worksheet3.freeze_panes(6, 0)
        self.worksheet3.set_tab_color("#DC4C00")  # Orange
        self.worksheet3.set_column(0, 0, 5)
        [self.worksheet3.set_column(i, i, 2) for i in range(1, max_level + 1)]
        self.worksheet3.set_column(max_level + 1, max_level + 1, 48)
        self.worksheet3.set_column(max_level + 2, max_level + 2, 12)
        self.worksheet3.set_column(max_level + 3, max_level + 3, 18)
        self.worksheet3.set_column(max_level + 4, max_level + 4, 65)
        self.worksheet3.set_column(max_level + 5, max_level + 5, 65)
        self.worksheet3.write_row(
            5,
            max_level + 1,
            [
                _("Name"),
                _("Result"),
                _("Certification Status"),
                _("I/O Log"),
                _("Comments"),
            ],
            self.format07,
        )
        if self.OPTION_WITH_DESCRIPTION in self._option_list:
            self.worksheet4.write(3, 1, _("Test Descriptions"), self.format03)
            self.worksheet4.freeze_panes(6, 0)
            self.worksheet4.set_column(0, 0, 5)
            [
                self.worksheet4.set_column(i, i, 2)
                for i in range(1, max_level + 1)
            ]
            self.worksheet4.set_column(max_level + 1, max_level + 1, 48)
            self.worksheet4.set_column(max_level + 2, max_level + 2, 65)
            self.worksheet4.write_row(
                5, max_level + 1, [_("Name"), _("Description")], self.format07
            )
        self._lineno = 5
        self._write_job(tree, data["result_map"], max_level)
        self.worksheet3.set_row(
            self._lineno + 1, None, None, {"collapsed": True}
        )
        if self.OPTION_WITH_DESCRIPTION in self._option_list:
            self.worksheet4.set_row(
                self._lineno + 1, None, None, {"collapsed": True}
            )
        self.worksheet3.autofilter(5, max_level, self._lineno, max_level + 3)

    def write_tp_export(self, data):
        def _category_map(state):
            """Map from category id to their corresponding translated names."""
            wanted_category_ids = frozenset(
                {
                    job_state.effective_category_id
                    for job_state in state.job_state_map.values()
                    if job_state.job in state.run_list
                    and job_state.job.plugin not in ("resource", "attachment")
                }
            )
            return {
                unit.id: unit.tr_name()
                for unit in state.unit_list
                if unit.Meta.name == "category"
                and unit.id in wanted_category_ids
            }

        self.worksheet4.set_header(
            "&C{}".format(data["manager"].test_plans[0])
        )
        self.worksheet4.set_footer("&CPage &P of &N")
        self.worksheet4.set_margins(left=0.3, right=0.3, top=0.5, bottom=0.5)
        self.worksheet4.set_column(0, 0, 40)
        self.worksheet4.set_column(1, 1, 13)
        self.worksheet4.set_column(2, 2, 55)
        self.worksheet4.write_row(
            0,
            0,
            ["Name", "Certification status", "Description"],
            self.format06_2,
        )
        self.worksheet4.repeat_rows(0)
        self._lineno = 0
        state = data["manager"].default_device_context.state
        cat_map = _category_map(state)
        run_list_ids = [job.id for job in state.run_list]
        for cat_id in sorted(cat_map, key=lambda x: cat_map[x].casefold()):
            self._lineno += 1
            self.worksheet4.write_row(
                self._lineno, 0, [cat_map[cat_id], "", ""], self.format15
            )
            for job_id in sorted(state._job_state_map):
                job_state = state._job_state_map[job_id]
                if job_id not in run_list_ids:
                    continue
                if (
                    job_state.effective_category_id == cat_id
                    and job_state.job.plugin not in ("resource", "attachment")
                ):
                    self._lineno += 1
                    certification_status = (
                        job_state.effective_certification_status
                    )
                    if certification_status == "unspecified":
                        certification_status = ""
                    description = job_state.job.description
                    if not description:
                        description = job_state.job.summary
                    self.worksheet4.write_row(
                        self._lineno,
                        0,
                        [
                            job_state.job.partial_id,
                            certification_status,
                            description,
                        ],
                        self.format05,
                    )
                    desc_lines = len(description.splitlines()) + 1
                    self.worksheet4.set_row(self._lineno, 12 * desc_lines)
            self._lineno += 1

    def write_attachments(self, data):
        self.worksheet5.set_column(0, 0, 5)
        self.worksheet5.set_column(1, 1, 120)
        i = 4
        for name in data["attachment_map"]:
            try:
                content = standard_b64decode(
                    data["attachment_map"][name].encode()
                ).decode("UTF-8")
            except UnicodeDecodeError:
                # Skip binary attachments
                continue
            self.worksheet5.write(i, 1, name, self.format03)
            i += 1
            self.worksheet5.set_row(
                i, None, None, {"level": 1, "hidden": True}
            )
            j = 1
            for line in content.splitlines():
                self.worksheet5.write(j + i, 1, line, self.format13)
                self.worksheet5.set_row(
                    j + i, None, None, {"level": 1, "hidden": True}
                )
                j += 1
            self.worksheet5.set_row(i + j, None, None, {"collapsed": True})
            i += j + 1  # Insert a newline between attachments

    def write_resources(self, data):
        self.worksheet6.set_column(0, 0, 5)
        self.worksheet6.set_column(1, 1, 120)
        i = 4
        for name in [
            job_id
            for job_id in data["result_map"]
            if data["result_map"][job_id]["plugin"] == "resource"
        ]:
            io_log = " "
            try:
                if data["result_map"][name]["io_log"]:
                    io_log = standard_b64decode(
                        data["result_map"][name]["io_log"].encode()
                    ).decode("UTF-8")
            except UnicodeDecodeError:
                # Skip binary output
                continue
            self.worksheet6.write(i, 1, name, self.format03)
            i += 1
            self.worksheet6.set_row(
                i, None, None, {"level": 1, "hidden": True}
            )
            j = 1
            for line in io_log.splitlines():
                self.worksheet6.write(j + i, 1, line, self.format13)
                self.worksheet6.set_row(
                    j + i, None, None, {"level": 1, "hidden": True}
                )
                j += 1
            self.worksheet6.set_row(i + j, None, None, {"collapsed": True})
            i += j + 1  # Insert a newline between resources logs

    def dump_from_session_manager(self, session_manager, stream):
        """
        Extract data from session_manager and dump it into the stream.

        :param session_manager:
            SessionManager instance that manages session to be exported by
            this exporter
        :param stream:
            Byte stream to write to.

        """
        data = self.get_session_data_subset(session_manager)
        data["manager"] = session_manager
        self.dump(data, stream)

    def dump(self, data, stream):
        """
        Public method to dump the XLSX report to a stream
        """
        from xlsxwriter.workbook import Workbook

        self.workbook = Workbook(stream, {"constant_memory": True})
        self._set_formats()
        if self.OPTION_WITH_SYSTEM_INFO in self._option_list:
            self.worksheet1 = self.workbook.add_worksheet(_("System Info"))
            self.write_systeminfo(data)
        if not self.OPTION_TEST_PLAN_EXPORT in self._option_list:
            self.worksheet3 = self.workbook.add_worksheet(_("Test Results"))
        if (
            self.OPTION_WITH_DESCRIPTION in self._option_list
            or self.OPTION_TEST_PLAN_EXPORT in self._option_list
        ):
            self.worksheet4 = self.workbook.add_worksheet(
                _("Test Descriptions")
            )
        if self.OPTION_TEST_PLAN_EXPORT in self._option_list:
            self.write_tp_export(data)
        else:
            self.write_results(data)
        if self.OPTION_WITH_SUMMARY in self._option_list:
            self.worksheet2 = self.workbook.add_worksheet(_("Summary"))
            self.write_summary(data)
        if self.OPTION_WITH_TEXT_ATTACHMENTS in self._option_list:
            self.worksheet5 = self.workbook.add_worksheet(_("Log Files"))
            self.write_attachments(data)
        if not self.OPTION_TEST_PLAN_EXPORT in self._option_list:
            self.worksheet6 = self.workbook.add_worksheet(_("Resources Logs"))
            self.write_resources(data)
        for worksheet in self.workbook.worksheets():
            worksheet.outline_settings(True, False, False, True)
            worksheet.hide_gridlines(2)
            worksheet.fit_to_pages(1, 0)
            worksheet.write(1, 1, _("System Testing Report"), self.format01)
            worksheet.set_row(1, 30)
        self.workbook.close()
