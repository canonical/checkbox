# This file is part of Checkbox.
#
# Copyright 2023 Canonical Ltd.
# Written by:
#   Maciej Kisielewski <maciej.kisielewski@canonical.com>
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
Generic utility functions.
"""
import json
import textwrap
from datetime import datetime

from plainbox.impl.color import Colorizer


def newline_join(head: str, *tail: str) -> str:
    """
    Join strings with newlines.
    If the first argument is an empty string, it will be ignored.

    See unittests for examples.
    """
    if not head:
        return "\n".join(tail)
    return "\n".join((head, *tail))


def generate_resume_candidate_description(candidate):
    template = textwrap.dedent(
        """
        Session Title:
            {session_title}

        Test plan used:
            {tp_id}

        Last job that was run:
            {last_job_id}

        Last job was started at:
            {last_job_start_time}
        """
    )
    app_blob = json.loads(candidate.metadata.app_blob)
    session_title = candidate.metadata.title or "Unknown"
    tp_id = app_blob.get("testplan_id", "Unknown")
    last_job_id = candidate.metadata.running_job_name or "Unknown"
    last_job_timestamp = candidate.metadata.last_job_start_time or None
    if last_job_timestamp:
        dt = datetime.utcfromtimestamp(last_job_timestamp)
        last_job_start_time = dt.strftime("%Y-%m-%d %H:%M:%S")
    else:
        last_job_start_time = "Unknown"
    return template.format(
        session_title=session_title,
        tp_id=tp_id,
        last_job_id=last_job_id,
        last_job_start_time=last_job_start_time,
    )


def request_comment(prompt: str) -> str:
    """
    Request a comment from the user.
    :param prompt: the thing that user has to explain with their comment
    :return: the comment provided by the user
    """
    colorizer = Colorizer()
    red = colorizer.RED
    blue = colorizer.BLUE
    comment = ""
    while not comment:
        print(red("This job is required in order to issue a certificate."))
        print(red("Please add a comment to explain {}.".format(prompt)))
        comment = input(blue("Please enter your comments:\n"))
    return comment
