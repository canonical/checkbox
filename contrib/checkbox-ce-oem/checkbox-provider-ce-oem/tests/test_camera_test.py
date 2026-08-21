import argparse
import os
import tempfile
import unittest
from unittest.mock import patch

import camera_test
from camera_utils import CameraScenarios


class FakeHandler:
    """Writes one artifact per capture call, like a real capture tool."""

    def capture_image(self, store_path, artifact_name, **kwargs):
        with open(os.path.join(store_path, artifact_name + ".yuv"), "wb") as f:
            f.write(b"data")


class TestArtifactStaging(unittest.TestCase):
    """Captures are staged in the job user's home, then moved."""

    def test_capture_artifacts_staged_then_moved(self):
        with tempfile.TemporaryDirectory() as tmp:
            session = os.path.join(tmp, "session")
            home = os.path.join(tmp, "home")
            os.makedirs(home)
            args = argparse.Namespace(
                camera="imx219",
                physical_interface="cam0",
                method="gstreamer",
                width=1920,
                height=1080,
                format="NV12",
                v4l2_device_name="0",
                mode=None,
                framerate=None,
            )

            with patch.object(
                camera_test, "PLAINBOX_SESSION_SHARE", session
            ), patch.dict(os.environ, {"HOME": home}):
                store = camera_test._execute_scenario(
                    args, FakeHandler(), CameraScenarios.CAPTURE_IMAGE, "abc"
                )

            # artifacts ended up in the session share (5 capture iterations)
            self.assertTrue(store.startswith(session))
            self.assertEqual(len(os.listdir(store)), 5)
            # the staging area is gone
            self.assertFalse(
                os.path.exists(os.path.join(home, "checkbox-camera-staging"))
            )


if __name__ == "__main__":
    unittest.main()
