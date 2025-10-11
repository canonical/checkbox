# WebGL Conformance Test

## Test Information

The WebGL conformance test in Checkbox uses the official [**WebGL Conformance Test Suite**](https://www.khronos.org/webgl/wiki/Testing/Conformance) from Khronos, without any third-party packages. The test runs on Firefox, Chromium, and Google Chrome, provided they're installed. Each browser is launched with specific options to ensure a proper test environment:

* **Firefox**: Started with `--private-window` to ensure a clean testing environment.
* **Chromium**: Started with `--new-window` and `--use-gl=desktop` to force the use of native OpenGL instead of [ANGLE](https://chromium.googlesource.com/angle/angle/+/main/README.md). 
* **Google Chrome**: Runs with the same settings as Chromium, plus `--no-first-run`, `--disable-fre`, and `--password-store=basic` to prevent the test from being blocked by initial setup prompts or password manager features.

---

## Prerequisites

To run the test, you must have a **self-hosted WebGL conformance test server**. You need to configure the `WEBGL_CONFORMANCE_TEST_URL` environment variable to point to your server's URL.

The default test server setup can be found in the [oem-qa-tools repository](https://github.com/canonical/oem-qa-tools/tree/main/Tools/env-setup/WebGL_conformance_test_server) for this purpose.
