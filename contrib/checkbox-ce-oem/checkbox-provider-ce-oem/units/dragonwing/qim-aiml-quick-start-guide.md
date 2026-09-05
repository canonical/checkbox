# QIM AI/ML Quick Start Guide

## Current Status

QIM AI/ML jobs are now fully driven by the Python runner:

- Runner: `bin/dragonwing_qim_ai_ml_test.py`
- Job files: `units/dragonwing/qim-ai-ml_jobs.pxu` (jobs) and `units/dragonwing/qim-ai-ml_test-plan.pxu` (test plans)
- Total AIML jobs: 14
	- 7 interactive (`plugin: user-interact-verify`)
	- 7 automated (`plugin: shell`)

All AIML jobs invoke `qim_ai_ml_test.py run ...` with explicit:

- `--test-data-dir "$QIM_TEST_DATA_DIR"`
- `--video-path "$TEST_VIDEO_FILE"`

## Required Environment Variables

Set these before running AIML jobs:

- `QIM_TEST_DATA_DIR`: folder containing model/label/settings artifacts
- `TEST_VIDEO_FILE`: full path to the test video file

Optional plugin-path variables (commonly required on DUT/snap env):

- `USER_DEFINED_GST_PLUGIN_PATH`
- `USER_DEFINED_GST_LD_LIBRARY_PATH`

Example:

```bash
export QIM_TEST_DATA_DIR=/home/ubuntu/CodecCrafter/qim
export TEST_VIDEO_FILE=/home/ubuntu/CodecCrafter/qim/test_video.mp4
export USER_DEFINED_GST_PLUGIN_PATH=/usr/lib/aarch64-linux-gnu/gstreamer-1.0/
export USER_DEFINED_GST_LD_LIBRARY_PATH=/usr/lib/aarch64-linux-gnu/
```

## Run Manually (Outside Checkbox)

LiteRT image classification:

```bash
python3 bin/dragonwing_qim_ai_ml_test.py run \
	--runtime litert \
	--scenario image-classification \
	--test-data-dir "$QIM_TEST_DATA_DIR" \
	--video-path "$TEST_VIDEO_FILE"
```

SNPE object detection:

```bash
python3 bin/dragonwing_qim_ai_ml_test.py run \
	--runtime snpe \
	--scenario object-detection \
	--test-data-dir "$QIM_TEST_DATA_DIR" \
	--video-path "$TEST_VIDEO_FILE"
```

What to expect:

- The script prints the resolved `gst-launch-1.0` command.
- The pipeline runs and writes an output mp4.
- For manual verification flows, check the generated output video for abnormalities.

## Artifact Resolution Rules

Preferred (current jobs):

- Models/labels/settings: from `--test-data-dir` (or `QIM_TEST_DATA_DIR` fallback)
- Video: from `--video-path` (or `TEST_VIDEO_FILE` fallback)

Also supported for flexibility:

- Explicit artifact files: `--model-path`, `--labels-path`, `--settings-path`
- Legacy compatibility env fallback: `TEST_DATA_DIR`, `TEST_MODELS_DIR`, `TEST_LABELS_DIR`, `TEST_SETTINGS_DIR`

Note:

- `--model-dir`, `--labels-dir`, and `--settings-dir` are no longer used.

## Output Location

Output file path resolution:

- `--output-path` (highest priority)
- or `--output-dir`
- or `$PLAINBOX_SESSION_SHARE/qim/<case-output-name>.mp4`

## Useful Runtime Options

- `--timeout` (default: `20` seconds)
- `--processing-width` (default: `1920`)
- `--processing-height` (default: `1080`)
- `--dry-run` to print command without executing

## Checkbox Job Behavior

In `units/dragonwing/qim-ai-ml.pxu`, each test case command now explicitly passes:

```bash
--test-data-dir "$QIM_TEST_DATA_DIR" --video-path "$TEST_VIDEO_FILE"
```

This ensures `QIM_TEST_DATA_DIR` is specific and explicit for every AIML test case.
