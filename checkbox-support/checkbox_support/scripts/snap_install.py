#!/usr/bin/env python3
# Copyright (C) 2026 Canonical Ltd.
"""Install a snap or refresh it if already installed.

Example:
    $ sudo ./snap_install.py rocm-validation-suite
"""

import argparse
import logging

from checkbox_support.helpers.retry import retry
from checkbox_support.snap_utils.snapd import Snapd, SnapdRequestError

logger = logging.getLogger(__name__)


@retry(3, 10)
def install(snap, snapd=None, *, channel="stable", revision=None):
    """Install a snap or refresh if already installed.

    :param snap: Name of the snap to install or refresh
    :param snapd: Snapd instance to use, defaults to a new Snapd instance
    :param channel: Snap channel to install
    :param revision: Snap revision to install
    """
    if snapd is None:
        snapd = Snapd()
    if snapd.list(snap) is None:
        logger.info("Installing snap %s", snap)
        snapd.install(snap, channel=channel, revision=revision)
    else:
        logger.info("Refreshing snap %s", snap)
        try:
            snapd.refresh(snap, channel=channel, revision=revision)
        except SnapdRequestError as exc:
            if exc.kind != "snap-no-update-available":
                raise
            logger.info("Snap %s is already up to date", snap)


def _parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("snap", help="name of the snap to install")
    parser.add_argument(
        "--channel", help="Snap channel", default="stable", type=str
    )
    parser.add_argument(
        "--revision", help="Snap revision", default=None, type=int
    )
    return parser.parse_args(argv)


def main(argv=None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    args = _parse_args(argv)

    snapd = Snapd()
    install(
        args.snap,
        snapd,
        channel=args.channel,
        revision=args.revision,
    )


if __name__ == "__main__":
    main()
