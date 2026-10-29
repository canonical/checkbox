# CIX NPU Tool Tests

The CIX NPU tool tests run the NOE tools shipped in the `cix-ai-test` package
on CIX P1 devices and check that the NPU stack (KMD, UMD and `libnoe`) works.
All jobs run `cix_ai_test.py`, which runs one `noe_*` tool and decides the
result from the tool output, because the tools can exit with `0` even when they
fail.

Background, the scope of the supported tools and the `cix-ai-test`
redistribution status are tracked in Jira card
[CIXEE-186](https://warthogs.atlassian.net/browse/CIXEE-186).

## Prerequisites

The jobs do not install anything. Install the cix-ai-test package before running.

This provides `/usr/share/cix/bin/noe_*` and the test data in
`/usr/share/cix/testdata/npu/`. If the tool binary or the test data is missing,
the job fails with an `ENV ERROR` message.

## Test plan

| Test plan | Description |
| --- | --- |
| `cix-tool-desktop` | Manual and automated CIX tool tests for Ubuntu Desktop. |
| `cix-tool-desktop-manual` | Manual tests, nests `cix-tool-aiml-manual`. |
| `cix-tool-desktop-automated` | Automated tests, nests `cix-tool-aiml-automated`. |
| `cix-tool-aiml-full` | All NPU tool tests. |
| `cix-tool-aiml-manual` | There are no manual NPU tool tests. |
| `cix-tool-aiml-automated` | All NPU tool jobs listed below. |

`cix-tool-desktop-manual` and `cix-tool-desktop-automated` are nested in the
`ce-oem-iot-desktop-26-04-manual` and `-automated` test plans.

## Manifest

Set both manifest entries before running the jobs:

```text
is_Cix_tool: True
has_cix_ai_test_npu: True
```

`is_Cix_tool` marks a CIX Tool platform; `has_cix_ai_test_npu` marks that the
NPU is supported and tested with the `cix-ai-test` tools. If either value is
not `True`, the jobs are not selected.

## Jobs

All jobs use `plugin: shell` and have `flags: also-after-suspend`. Only `dfs` runs as `root`, because it writes to the devfreq sysfs; the other tools only need `/dev/aipu`, which is world-accessible.
Unless stated otherwise, a job passes when the tool exits with `0`, prints no
`[Err]` or `FAIL` line and at least one `Test Result Check PASS` line.

### `cix-tool-aiml/benchmark`

Runs `noe_benchmark` with the 3-core ONNX ResNet50 model
(`onnx_resnet50_3core`): init, load graph, create job, 1000 inference frames,
clean and unload. Every frame is compared with the golden `output.bin`.
This is the smoke test (TC-01) required in CIXEE-186. All 1000 frames must
print `Test Result Check PASS`.

### `cix-tool-aiml/benchmark_tflite`

Same as above with the 1-core TFLite ResNet50 model (`tflite_resnet50_1core`),
to cover another model format and core count.

### `cix-tool-aiml/batch`

Runs `noe_batch` to check that several inference jobs can be submitted as a
batch.

### `cix-tool-aiml/dfs`

Runs `noe_dfs` to check that the NPU frequency can be changed through devfreq.
The tool writes `/sys/class/devfreq/CIXH4000:00/userspace/set_freq`, which
exists only with the `userspace` governor. The script therefore switches the
governor to `userspace` before the run and always restores the original
governor afterwards.

### `cix-tool-aiml/flush_job`

Runs `noe_flush_job` to check that pending jobs can be flushed and cleaned up.
The tool does not print `Test Result Check PASS`, so only the exit code and the
absence of `[Err]` and `FAIL` lines are checked.

### `cix-tool-aiml/mthread`

Runs `noe_mthread` to check inference from several threads at the same time.

### `cix-tool-aiml/multi_model`

Runs `noe_multi_model` to check that two models can be loaded and run in one
process. There is no `Test Result Check PASS` line; only the exit code and the
absence of `[Err]` and `FAIL` lines are checked.

### `cix-tool-aiml/profiler`

Runs `noe_profiler` to check that the profiler (tick counter) can be enabled
and its tensor data read back. The `get profiler tensor success` line must be
present, and there is no `Test Result Check PASS` line.

### `cix-tool-aiml/time_cost`

Runs `noe_time_cost` to check that the time cost of each stage is reported.
There is no `Test Result Check PASS` line; only the exit code and the absence
of `[Err]` and `FAIL` lines are checked.

#### Scenario: Pass

```text
Test Result Check PASS!
noe_deinit_ctx success

noe_batch PASSED
```

#### Scenario: Fail

The tool exits with `0` but prints an error:

```text
[Err] <22237>  noe_ioctl (config clusters): This API call here is invalid.

noe_batch FAILED:
- error in output: ... [Err] ... noe_ioctl (config clusters): This API call here is invalid.
- 'Test Result Check PASS' not found
```

## Environment variables

Use these variables in the launcher `[environment]` section when needed:

| Variable | Description | Default |
| --- | --- | --- |
| `CIX_NOE_LIB_DIR` | Directory with `libnoe.so.3`. It is put at the front of `LD_LIBRARY_PATH`; an existing `LD_LIBRARY_PATH` is kept after it. | `/usr/share/cix/lib` |

Inside the Checkbox snap, `LD_LIBRARY_PATH` already points at the snap runtime
libraries. The script keeps those entries, so the CIX library directory only
has to be added in front of them.

## Running the jobs

After installing `cix-ai-test` and setting the manifest, run:

```bash
checkbox-ce-oem.checkbox-cli run com.canonical.contrib::cix-tool-desktop-automated
```

A job fails if the tool or the test data is missing, the tool times out
(`--timeout`, 600 seconds by default), the exit code is not `0`, the output has
an `[Err]` or `FAIL` line, or an expected line is missing. The full tool output
is always printed.
