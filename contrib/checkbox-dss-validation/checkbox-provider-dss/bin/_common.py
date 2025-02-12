#!/usr/bin/env python3
# Copyright 2018-2022 Canonical Ltd.
# All rights reserved.
#
"""Common utilities for the checkbox-provider-dss

Authors:
    - Abdullah (@motjuste) <abdullah.abdullah@canonical.com>
"""

import subprocess


def run_command(*command: str, **kwargs) -> str:
    """Run a shell command and return its output"""
    try:
        result = subprocess.check_output(
            command,
            stderr=subprocess.STDOUT,  # We capture stdout and stderr in stdout
            universal_newlines=True,
            **kwargs,
        )
        result = result.strip()
        return result
    except subprocess.CalledProcessError as e:
        raise SystemExit(e.returncode) from e
