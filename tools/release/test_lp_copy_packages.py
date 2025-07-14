import unittest
import lazr

from unittest.mock import patch, MagicMock

import lp_copy_packages


class TestMain(unittest.TestCase):
    @patch("lp_copy_packages.get_launchpad_client")
    def test_main(self, get_launchpad_client_mock):
        lp_client = get_launchpad_client_mock()

        checkbox_dev_user = MagicMock()
        lp_client.people = {"checkbox-dev": checkbox_dev_user}

        source_to_copy = MagicMock(
            date_superseded=None, source_package_name="up to date package"
        )
        source_no_copy_outdated_distro = MagicMock(
            date_superseded=None, source_package_name="outdated source"
        )

        ppas = checkbox_dev_user.getPPAByName()
        ppas.getPublishedSources.return_value = [source_to_copy] * 5 + [
            source_no_copy_outdated_distro,
        ]
        copied = 0

        def fail_on_outdated(**kwargs):
            nonlocal copied
            source_name = kwargs["source_name"]
            print(source_name)
            if source_name == "outdated source":
                raise lazr.restfulclient.errors.BadRequest(
                    response=MagicMock(items=lambda: [], status=400, reason="some"),
                    content=b"distro is obsolete and will not accept new uploads",
                )
            copied += 1

        ppas.copyPackage = fail_on_outdated
        lp_copy_packages.main(["checkbox-dev", "beta", "checkbox-dev", "stable"])

        self.assertEqual(copied, 5)
