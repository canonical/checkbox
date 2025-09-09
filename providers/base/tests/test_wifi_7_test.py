import pathlib
import unittest as ut
import wifi_7_test as w7

TEST_DATA_DIR = pathlib.Path(__file__).parent / "test_data"


class TestWifi7Tests(ut.TestCase):

    def test_happy_path(self):

        with (TEST_DATA_DIR / "iw_dev_link_succ.txt").open() as f:
            w7.ConnectionInfo.parse(f.read())
        
        with (TEST_DATA_DIR / "iw_dev_info_succ.txt").open() as f:
            w7.ConnectionInfo.parse(f.read())


if __name__ == "__main__":
    ut.main()
