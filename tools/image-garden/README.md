# Image Garden Spread tests

This directory contains Spread tests that run Checkbox snaps in Ubuntu Core
virtual machines provided by Image Garden.

## Requirements

First, Install Image Garden:

```bash
sudo snap install image-garden
```

The patching tool also requires `python3`, `snap`, and `unsquashfs` on the host.

## Run a patched snap locally

Run `run_local.py` from this directory. Pass the launcher that Checkbox should
use and, optionally, the Ubuntu Core series:

```bash
cd tools/image-garden
python3 run_local.py tests/run-patched-snap/launcher.conf --series 24
```

`tests/run-patched-snap/launcher.conf` runs the metabox
`smoke-automated-passing` test plan, but you can use a different launcher to run other test plans.

The series defaults to `24`; supported values are `18`, `20`, `22`, `24`, and
`26`. The series selects both the snap name, such as `checkbox24`, and the
matching Image Garden system, such as `ubuntu-core-24`. The script performs the
following steps:

1. Downloads the matching Checkbox snap from the `edge` channel.
2. Creates a `local_run_<series>/` directory, such as `local_run_24/`.
3. Unsquashes the snap under that directory.
4. Copies the launcher there so Spread can send it to the guest.
5. Overlays the local Checkbox Python packages and providers.
6. Runs the launcher against the patched snap with `snap try`.

You can also pass a specific snap as an argument to the script:

```bash
python3 run_local.py \
    path/to/launcher.conf \
    --series 24 \
    --snap-file path/to/checkbox24.snap
```


## Run the store smoke tests locally

The store smoke task does not patch a snap or require a custom launcher:

```bash
cd tools/image-garden
image-garden.spread -vv -artifacts=artifacts \
    "garden:ubuntu-core-24:tests/run-smoke"
```

Supported systems are listed in `spread.yaml`.

## Clean local files

Remove local test state when it is no longer needed:

```bash
rm -rf tools/image-garden/artifacts \
    tools/image-garden/local_run_*
```
