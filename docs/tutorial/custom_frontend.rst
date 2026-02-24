.. _custom-apps:

Creating a custom Checkbox frontend
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

This guide describes how to create a custom Checkbox frontend for testing a
new project. This is usually done to package in-development tests and test
plans before shifting them to the main Checkbox providers. This tutorial will
guide you to package as a snap the
:ref:`2024.com.tutorial:tutorial provider <adv_test_case>` we have previously
created.

Prerequisites
=============

To complete this tutorial you will need Snapcraft. Refer to the following to
install it: `Set up Snapcraft <https://documentation.ubuntu.com/snapcraft/stable/how-to/set-up-snapcraft/>`_

Additionally, you will need the provider we created during the previous
tutorial. If you don't have it, you can still follow this tutorial by borrowing
the `one in the main Checkbox repository <https://github.com/canonical/checkbox/tree/main/providers/tutorial>`_
but remember: you must change the `namespace (here) <https://github.com/canonical/checkbox/blob/main/providers/tutorial/manage.py#L6>`_! If you don't do that Checkbox
will complain about duplicated units.

Starting a new Checkbox Frontend snap
=====================================

To begin our new snap we start from creating a new project directory. Usually
custom frontends are named `checkbox_name_of_the_project`, so start by creating
a `checkbox_tutorial` directory. Prepare the following tree structure,
creating a new ``providers`` directory and a ``snap`` directory inside of it,
then copy the ``2024.com.tutorial:tutorial`` directory we created via
``startprovider`` inside ``providers``::

  checkbox_tutorial:
  ├─ providers
  │  ├── 2024.com.tutorial:tutorial
  │  │   ├─── manage.py
  │  [...]
  └── snap
     └── snapcraft.yaml

In this tutorial we will package only one provider, the tutorial provider, but
this structure is future-proof, allowing you to expand your custom frontend
snap as needed. This is exactly the structure we use for the main Checkbox
repository.

.. warning::

   This tutorial will focus on creating a core24 snap. If you need a snap for
   another base, ensure that both the snap's base and the runtime version you
   pull match your system (e.g., the snap base core24 requires runtime version
   checkbox24). A version mismatch can cause errors that are very difficult to
   debug.

Edit the ``snapcraft.yaml`` and set it to the following:

.. code:: yaml

  name: checkbox-tutorial
  summary: Checkbox tutorial custom frontend
  description: |
    This is a custom frontend for Checkbox containing the tutorial provider.
    Use it along the checkbox24 snap.
  grade: stable
  confinement: strict
  base: core24

  adopt-info: version-calculator

  slots:
    custom-frontend:
      interface: content
      content: custom-frontend
      read:
        - /

  package-repositories:
    - type: apt
      ppa: checkbox-dev/edge # used to pull the installation machinery

  parts:
    version-calculator:
      plugin: dump
      source: snap
      override-pull: |
        craftctl default
        # consider calculating the version here!
        export version="v1.2.3"
        [ $version ] || exit 1
        craftctl set version=$version
    checkbox-provider-tutorial:
      # install each provider in its own independent part
      plugin: dump
      source: providers/2024.com.tutorial:tutorial
      source-type: local
      build-environment:
        - PYTHONPYCACHEPREFIX: "/tmp"
      build-packages: # add here any other build dependency you may have
        - checkbox-ng # this is necessary to run manage.py
      stage-packages: # add here any runtime dependency of your provider
        - jq          # Note: we added a packaging metadata unit but those are
                      #       not used in snap builds! Repeat all dependencies
                      #       here if you want them included in the snap
      override-build: |
        # Do NOT validate your provider, if you depend on tests/nested parts
        # that aren't in this provider (or in this repository) it will fail to
        # validate. We will handle validation in a separate workflow.
        python3 manage.py build
        # Note: providers MUST be in /providers to use the new custom-frontend
        #       connection, do not change the location
        # Note2: if you are building with snapcraft<7.x, change CRAFT_PART_INSTALL to SNAPCRAFT_PART_INSTALL
        python3 manage.py install --layout=relocatable --prefix=/providers/tutorial --root="$CRAFT_PART_INSTALL"

Let's try to build our new frontend snap:

.. code:: shell-session

   $ cd checkbox_tutorial
   $ snapcraft pack --use-lxd
   $ ls # Note: name will depend on the architecture of the machine you are building on
   providers  snap  checkbox-tutorial_v1.2.3_amd64.snap

To try/use our new snap we now need to install the runtime, then install our
new snap and connect them.

.. code:: shell-session

   $ sudo snap install --devmode checkbox24
   $ sudo snap install --dangerous checkbox-tutorial_v1.2.3_amd64.snap
   $ sudo snap connect checkbox24:custom-frontend checkbox-tutorial
   $ checkbox24.checkbox run tutorial/passing
   ===========================[ Running Selected Jobs ]============================
   =========[ Running job 1 / 1. Estimated time left (at least): 0:00:00 ]=========
   --------------------------[ A job that always passes ]--------------------------
   ID: com.canonical.certification::tutorial/passing
   Category: com.canonical.certification::tutorial
   ... 8< -------------------------------------------------------------------------
   This job passes!
   ------------------------------------------------------------------------- >8 ---
   Outcome: job passed
   Finalizing session that hasn't been submitted anywhere: checkbox-run-2025-10-27T11.37.55
   ==================================[ Results ]===================================
    ☑ : A job that always passes

.. note::

  Here we have to use ``--dangerous`` because we built the snap locally.
  Once in the store this will no longer be necessary.

Building the snap on GitHub
===========================

We recommend creating the following workflow in your repository to build and
publish your snap. This tutorial will not go into much detail about how you
should gate the promotion between edge, beta and stable but we advise you to
take inspiration from the Checkbox process detailed in :ref:`canary-explanation`.

Create the following under
``.github/workflows/checkbox_tutorial_build_publish.yaml``:

.. code:: yaml

    name: Checkbox tutorial Snap native builds
    permissions:
      contents: read
    on:
      workflow_call:
        inputs:
          store_upload:
            description: 'Should the workflow upload to the store?'
            default: false
            required: false
            type: boolean
      workflow_dispatch:
        inputs:
          store_upload:
            description: 'Should the workflow upload to the store?'
            default: false
            required: false
            type: boolean
        secrets:
          SNAPCRAFT7_CREDS:
            required: true
    jobs:
      snap_checkbox_tutorial_native:
        strategy:
          fail-fast: false
          matrix:
            tag: [X64, ARM64]
        runs-on:
          group: "Canonical self-hosted runners"
          labels: ["self-hosted", "linux", "large", "${{ matrix.tag }}"]
        timeout-minutes: 1200 #20h, this will timeout sooner due to inner timeouts
        name: Checkbox Tutorial Snap (${{matrix.tag}})
        steps:
          - uses: actions/checkout@08c6903cd8c0fde910a37f88322edcfb5dd907a8
            with:
              fetch-depth: 0
              persist-credentials: false

          - id: snap_build
            uses: Wandalen/wretry.action@71a909ebf09f3ffdc6f42a17bd54ecb43481da49
            name: Build the snap
            timeout-minutes: 600 # 10hours
            with:
              action: snapcore/action-build@v1.3.0
              attempt_delay: 600000 # 10min
              attempt_limit: 5
              with: |
                snapcraft-channel: 8.x/stable

          - uses: actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02
            name: Upload logs on failure
            if: failure()
            with:
              name: snapcraft-log-series${{ matrix.tag }}
              path: |
                /home/runner/.cache/snapcraft/log/
                /home/runner/.local/state/snapcraft/log/
                checkbox*.txt

          - uses: actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02
            name: Upload the snap as artifact
            with:
              name: checkbox_tutorial_${{ matrix.tag }}.snap
              path: ${{ steps.snap_build.outputs.snap }}

          - name: Publish track
            if: inputs.store_upload
            uses: canonical/action-publish@214b86e5ca036ead1668c79afb81e550e6c54d40
            env:
              SNAPCRAFT_STORE_CREDENTIALS: ${{ secrets.SNAPCRAFT7_CREDS }}
            with:
              snap: ${{ steps.snap_build.outputs.snap }}
              release: latest/edge

This is a basic workflow that will build your snap for ``amd64`` and
``arm64``. If you need a more advanced example, reference the following
workflow in the Checkbox repository: `Checkbox daily native builds <https://github.com/canonical/checkbox/blob/main/.github/workflows/checkbox-daily-native-builds.yaml>`_.

.. note::

  This assumes you have access to the self hosted runners for your
  repository. If this is not the case, or you need more architectures, see the
  chapter below.

Building the snap on Github (more architectures)
================================================

To build for architectures we don't have a self hosted runner for, or if you
don't have access to them for your project, we recommend using the following
workflow:

.. code:: yaml

  name: Checkbox Tutorial Snap cross-builds
  permissions:
    contents: read
  on:
    workflow_dispatch:
      inputs:
        store_upload:
          description: 'Should the workflow upload to the store?'
          default: false
          required: false
          type: boolean
    workflow_call:
      inputs:
        store_upload:
          description: 'Should the workflow upload to the store?'
          default: false
          required: false
          type: boolean
      secrets:
        SNAPCRAFT7_CREDS:
          required: true
  jobs:
    snap-runtime:
      strategy:
        fail-fast: false
        matrix:
          arch: [armhf, riscv64]
      # Note: uc16 needs ubuntu20 because we need cgroup v1 to build it
      runs-on: 'ubuntu-latest'
      timeout-minutes: 1200 #20h, this will timeout sooner due to inner timeouts
      name: Runtime (${{ matrix.arch }})
      steps:
        - uses: actions/checkout@08c6903cd8c0fde910a37f88322edcfb5dd907a8
          with:
            fetch-depth: 0
            persist-credentials: false

        - name: Set up QEMU
          uses: docker/setup-qemu-action@29109295f81e9208d7d86ff1c6c12d2833863392

        - id: snap_build
          name: Build (retries on fail)
          uses: Wandalen/wretry.action@71a909ebf09f3ffdc6f42a17bd54ecb43481da49
          with:
            attempt_limit: 5
            action: canonical/snapcraft-multiarch-action@v1
            with: |
              architecture: ${{ matrix.arch }}

        - uses: actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02
          name: Upload logs on failure
          if: failure()
          with:
            name: runtime-build-log-${{ matrix.arch }}
            path: |
              /home/runner/.cache/snapcraft/log/
              /home/runner/.local/state/snapcraft/log/
              checkbox*.txt

        - uses: actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02
          name: Upload the snap as artifact
          with:
            name: checkbox_tutorial_${{ matrix.arch }}.snap
            path: ${{ steps.snap_build.outputs.snap }}

        - name: Publish track
          if: inputs.store_upload
          uses: canonical/action-publish@214b86e5ca036ead1668c79afb81e550e6c54d40
          env:
            SNAPCRAFT_STORE_CREDENTIALS: ${{ secrets.SNAPCRAFT7_CREDS }}
          with:
            snap: ${{ steps.snap_build.outputs.snap }}
            release: latest/edge

This is a basic workflow that will build your snap for ``armhf`` and
``riscv64``. If you need a more advanced example, that is similar but also
handles multiple bases (including uc16) and snapcraft versions
reference the following workflow in the Checkbox repository: `Checkbox daily cross build <https://github.com/canonical/checkbox/blob/main/.github/workflows/checkbox-daily-cross-builds.yaml>`_.

.. note::

   If you don't have access to the self hosted runners, you will not be able
   to build snaps for core16. You need a system that supports cgroup v1 to do
   so. If you do, refer to the Checkbox workflow for the precise tags you
   should use.
