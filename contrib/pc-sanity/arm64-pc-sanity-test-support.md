# ARM64 PC Sanity Test Support

## Purpose

This document assesses what is required to install Checkbox and run the
PC Sanity test plans on Ubuntu arm64 systems. It distinguishes between:

1. installing the Checkbox engine;
2. installing the providers used by PC Sanity;
3. starting a PC Sanity test plan; and
4. obtaining meaningful ARM test coverage rather than silently omitting
   x86-only checks.

The assessment is based on the repository state on 2026-10-13. Package
availability still needs to be verified against every target Ubuntu series
and pocket before support is declared.

## Executive summary

The Checkbox engine is architecture-independent and can run on arm64. The
`checkbox-ng` and `python3-checkbox-ng` binary packages are declared
`Architecture: all`, as is `python3-checkbox-support`.

The PC Sanity Debian package is not currently ready for arm64:

* `plainbox-provider-pc-sanity` is declared `Architecture: all`, but its build
  compiles and installs the native `uwake` executable. An amd64 build of that
  package cannot be reused on arm64. The package must be `Architecture: any`
  and built separately for arm64.
* It unconditionally depends on `msr-tools`, an x86-specific package. The
  dependency must be architecture-qualified or removed from hard
  dependencies.
* Its standalone autopkgtest helper is hard-coded to a Focal amd64 LXD image.
  The formal Debian autopkgtest control file does not run the smoke-plan test
  script. There is no arm64 package-install or plan-execution CI coverage.
* Six turbostat job IDs are included directly by `pc-sanity-base`, but no
  definitions for those IDs exist in this repository. If they are supplied
  only by a private or side-loaded provider, that dependency is undocumented.
  If they are not supplied, they are dangling test-plan references on every
  architecture.

After installation is fixed, the plans remain only partially ARM-ready. Most
Intel-specific templates are correctly filtered and will not be generated on
ARM. However, the smoke plans unconditionally nest an Intel thermal plan and
an x86-oriented CPU C-state plan. Silently omitting those jobs does not provide
equivalent ARM thermal, idle-state, suspend, firmware, or IOMMU validation.

The recommended approach is one provider package for all supported
architectures, architecture- and capability-gated jobs, and separate ARM
subplans for functionality that has no x86-independent implementation.

## Scope and target definition

"ARM support" needs a declared target. At minimum, decide all of the
following before calling the work complete:

* Ubuntu releases: 22.04, 24.04, 26.04, or a subset.
* Product classes: ACPI/UEFI laptops, device-tree laptops, desktops,
  workstations, servers, or development boards.
* CPU/platform families: for example Qualcomm, MediaTek, NVIDIA, Ampere, or
  Raspberry Pi.
* Firmware model: ACPI, device tree, or both.
* Graphics stacks: Mesa/Panfrost, Freedreno, V3D, NVIDIA, or others.
* Required test parity: identical job list, equivalent functional coverage,
  or a documented ARM-specific profile.

This matters because "arm64" identifies an instruction-set architecture, not
a common PC firmware or power-management interface. An ARM server using ACPI
has different useful tests from a device-tree development board or an ARM
laptop.

## Current installation state

### Core packages

| Component | Debian architecture | ARM64 state | Notes |
| --- | --- | --- | --- |
| `checkbox-ng` | `all` | Ready in principle | Python application; dependencies must exist in the target Ubuntu archive. |
| `python3-checkbox-ng` | `all` | Ready in principle | Architecture-independent Python library. |
| `python3-checkbox-support` | `all` | Ready in principle | Python library; recommended packages such as NumPy and OpenCV must be available for optional features. |
| `checkbox-provider-base` | `any` | Requires an arm64 build | Provider packaging must be published for each target series. |
| `checkbox-provider-resource` | `any` | Portable source, arm64 build required | Builds `80211_resource` against libnl and Linux nl80211 headers. |
| `checkbox-provider-certification-client` | `all` | Ready in principle | Runtime and recommended desktop packages still need archive verification. |
| `checkbox-provider-tpm2` | `all` | Ready in principle | Needed by nested client certification plans. |
| `plainbox-provider-pc-sanity` | incorrectly `all` | Blocked | Contains native `uwake`; must become `any`. |

The certification-client packaging already recognizes ARM for graphics: its
`checkbox-glmark2-es2-meta` package depends on `glmark2-es2` on `arm64` and
`armhf`.

### PC Sanity package blockers

#### Native executable in an architecture-independent package

`debian/rules` runs `make` in `contrib/pc-sanity/c`, and the Makefile compiles
`uwake.c` with the host compiler. The resulting ELF executable is installed
in the provider package. The source uses the Linux uinput API and appears
portable, but the resulting binary is architecture-specific.

Required fix:

* change `plainbox-provider-pc-sanity` to `Architecture: any`;
* change the Makefile from `CC = gcc` to an overridable compiler and consume
  Debian `CPPFLAGS`, `CFLAGS`, and `LDFLAGS`;
* retain `${shlibs:Depends}`;
* let debhelper strip the executable and remove the obsolete Lintian
  suppressions for architecture, static-link, and stripping problems;
* publish amd64 and arm64 builds from the same source package; and
* verify that the package build uses the build architecture compiler during
  native builds and the host compiler during cross-builds.

Alternative solutions:

* Replace `uwake` with an existing architecture-independent userspace tool,
  if one provides the same reliable uinput wake behavior. This could allow
  the provider to remain `Architecture: all`.
* Split `uwake` into a small `Architecture: any` helper package and keep the
  data-only provider package `Architecture: all`. This adds packaging
  complexity and is justified only if the provider must remain data-only.

#### Unconditional `msr-tools` dependency

`msr-tools` exposes x86 model-specific registers and has no ARM equivalent.
It is a hard dependency of `plainbox-provider-pc-sanity`, even though the
MSR-related jobs apply only to Intel systems.

Preferred fix:

```text
msr-tools [amd64 i386],
```

Use the exact architecture list published by each target Ubuntu series. Do
not use a broad negative qualifier such as `[!arm64]`, because that can pull
an x86-only dependency on unrelated architectures.

Alternatives:

* Move `msr-tools` to `Recommends` and retain package/executable requirements
  on every consuming job.
* Move it to the base provider package that owns the consuming
  `short-idle-check.sh` job, with an architecture qualifier there.
* Split x86-only dependencies into a `pc-sanity-x86` companion metapackage.
  This is more explicit but increases installation and release complexity.

ARM system registers are not a drop-in replacement for x86 MSRs. ARM power
tests should consume kernel interfaces such as cpuidle, cpufreq, thermal,
PSCI, and platform-specific debug data instead of installing an MSR tool.

### Prerequisites to verify per Ubuntu release

For each target release and enabled pocket, verify that arm64 binaries exist
and are co-installable for:

* `checkbox-ng`, `python3-checkbox-ng`, `python3-checkbox-support`;
* `checkbox-provider-base`, `checkbox-provider-resource`,
  `checkbox-provider-certification-client`, and `checkbox-provider-tpm2`;
* `libnl-3-200`, `libnl-genl-3-200`, and corresponding build dependencies;
* `openscap-scanner`, `python3-apt`, `jq`, `xautomation`, `bats`, and
  `shellcheck`;
* `fwts`, `glmark2-es2`, `mesa-utils`, `evemu-tools`, `i2c-tools`,
  `libinput-bin`, `modemmanager`, and `ubuntu-drivers-common`; and
* all nested client-certification plan dependencies for the selected Ubuntu
  release.

Use both archive metadata and an actual clean-system installation test. A
package being available for arm64 does not prove that its hardware-facing
functions work on a particular ARM platform.

Archive observations as of 2026-10-13:

* Ubuntu's package index lists `msr-tools` only for amd64 in
  [22.04](https://packages.ubuntu.com/jammy/msr-tools),
  [24.04](https://packages.ubuntu.com/noble/msr-tools), and
  [26.04](https://packages.ubuntu.com/resolute/msr-tools). This confirms the
  unconditional dependency as an arm64 installation blocker for all three
  plans' releases.
* `openscap-scanner` is listed for arm64 in
  [24.04](https://packages.ubuntu.com/noble/openscap-scanner) and
  [26.04](https://packages.ubuntu.com/resolute/openscap-scanner). It is not
  listed in the base or updates package pages checked for 22.04. The 22.04
  plan therefore needs a documented PPA source, a dependency replacement, or
  removal of the CVE job from that release's installable package.
* `glmark2-es2` is listed for arm64 in
  [22.04](https://packages.ubuntu.com/jammy/glmark2-es2). In 26.04 it is a
  virtual package supplied by `glmark2-es2-x11`; release-specific dependency
  resolution must be tested rather than assuming one binary package layout.

Minimum build prerequisites are an arm64 Ubuntu builder, matching kernel/libc
headers, a C compiler, debhelper, Python build dependencies, libnl development
packages for the resource provider, and access to every provider package from
the same release channel.

### Installation preflight

After the packaging fixes are published, run this on a clean target before
executing hardware tests:

```shell
test "$(dpkg --print-architecture)" = arm64
apt-cache policy checkbox-ng python3-checkbox-ng python3-checkbox-support \
  checkbox-provider-base checkbox-provider-resource \
  checkbox-provider-certification-client plainbox-provider-pc-sanity
apt-get --simulate install plainbox-provider-pc-sanity
sudo apt-get install plainbox-provider-pc-sanity
file /usr/bin/uwake
checkbox-cli list | grep 'pc-sanity-smoke-test'
```

The `file` output must identify an AArch64 executable. Also repeat the
simulation with the exact production repository and pocket configuration; a
developer checkout or already-installed provider can hide missing package
dependencies.

### Alternative engine delivery

Repository workflows and snap recipes already include arm64 Checkbox builds.
A Checkbox snap is therefore a possible alternative for delivering the
engine. It does not, by itself, make PC Sanity ARM-ready: the provider's host
commands and dependencies still need delivery, snap interfaces must grant the
required `/sys`, `/dev`, debugfs, uinput, firmware, display, and system-service
access, and the x86-only jobs still need gating or ARM replacements.

## Current test-plan state

### Plans under assessment

The following plans are the main ARM entry points:

| PC Sanity plan | Nested plans |
| --- | --- |
| `pc-sanity-base` | Direct PC Sanity jobs only. |
| `pc-sanity-smoke-test` | `pc-sanity-base`, `client-cert-desktop-22-04-automated`, `power-management-cpu-cstate-cert-automated`, `thermal-cert-automated`. |
| `pc-sanity-smoke-test-24-04` | Same structure with `client-cert-desktop-24-04-automated`. |
| `pc-sanity-smoke-test-26-04` | Same structure with `client-cert-desktop-26-04-automated`. |
| `pc-sanity-smoke-test-24-04-without-cert-desktop` | `pc-sanity-base`, CPU C-state plan, and thermal plan. |

The desktop certification plans add broad audio, Bluetooth, camera, display,
graphics, input, storage, networking, suspend, USB, TPM, firmware, and other
coverage. Most jobs are selected through hardware resources, but the plans
were designed for Ubuntu PC devices and are not, by themselves, an ARM
support contract.

## Comparison with IoT test plans

### Short answer

The IoT plans do not run the same test set as PC Sanity.

They share a substantial base-provider and certification-provider core, but
their top-level composition and product requirements differ:

* PC Sanity adds OEM image policy, package-origin, CVE, kernel-error, display,
  Intel power, Intel thermal, SMBIOS, NVIDIA, and production-suite checks.
* IoT certification adds GPIO, I2C, EEPROM, serial, SocketCAN, watchdog,
  device-tree, embedded firmware, Ubuntu Core, and image/model checks.
* The CE OEM IoT wrapper adds generic cpufreq, devfreq/DVFS, thermal-zone,
  regulator, OP-TEE, remoteproc/RPMsg, codec, accelerator, and SoC-specific
  tests.
* IoT plans explicitly exclude a number of laptop/PC assumptions. They do not
  include `pc-sanity-base`, the PC Sanity turbostat jobs,
  `intel_pmc_core`, `power-management-cpu-cstate-cert-automated`, or
  `thermal-cert-automated`.

IoT is also not synonymous with ARM. The suite includes Intel IoT Gateway
coverage as well as Dragonwing, MediaTek Genio, NVIDIA Jetson, Renesas RZ,
and Xilinx coverage. Individual jobs still need resource, manifest, or
platform gating; the fact that a job belongs to an IoT provider is not proof
that it is portable to every arm64 platform.

### Plan hierarchy

The principal IoT plans are in the certification-client provider:

* `client-cert-iot-desktop-<release>` for classic desktop images;
* `client-cert-iot-server-<release>` for classic server images; and
* `client-cert-iot-ubuntucore-<release>` for Ubuntu Core images.

The contrib CE OEM provider wraps those plans as `ce-oem-iot-*` and adds
generic embedded and SoC-specific plans. For example,
`ce-oem-iot-desktop-26-04-automated` nests the certification-client IoT plan,
the generic `ce-oem-automated` plan, and Dragonwing, Genio, IIoTG, Jetson,
Renesas RZ, and Xilinx desktop plans.

This is a useful model for ARM support: keep common Linux tests in shared
providers, and add capability- or SoC-specific overlays. It is not useful to
copy the entire IoT plan into PC Sanity because that would add many irrelevant
embedded interfaces and still omit PC Sanity's OEM image policy checks.

### Direct plan overlap

The following counts compare direct `nested_part` entries, not fully expanded
runtime jobs. Dynamic templates, resource selection, excludes, and manifest
values can change the final selected job set.

| Release and plans | PC subplans | IoT subplans | Same direct subplans | Interpretation |
| --- | ---: | ---: | ---: | --- |
| 24.04 `client-cert-desktop-24-04-automated` vs IoT desktop automated | 55 | 58 | 18 | Naming and composition differ substantially. Some differently named plans still exercise related devices. |
| 26.04 `client-cert-desktop-26-04-automated` vs IoT desktop automated | 34 | 61 | 30 | The 26.04 base-plan refactor creates a large shared core; IoT adds 31 direct subplans and omits four PC-only ones. |

The 30 shared 26.04 subplans cover ACPI, audio, suspend references,
Bluetooth, CPU, disk, Ethernet, fingerprint, fwupd, graphics, keys, LED,
media card, memory, miscellaneous client checks, monitor, networking, power,
snapd, submission, Thunderbolt, touchscreen, TPM, USB, wireless, WWAN, and
information attachments.

The four PC-only direct subplans are:

* `camera-base-26-04-automated`;
* `input-base-26-04-automated`;
* `optical-base-26-04-automated`; and
* `touchpad-base-26-04-automated`.

IoT has separate camera coverage and adds 31 direct plans, including generic
audio/camera/networking variants, Docker, EDAC, EEPROM, GPIO, I2C, ISH/MEI,
QEP, RTC, serial, SocketCAN, VA-API, watchdog, Wi-Fi AP mode, and their
applicable after-suspend variants.

The 24.04 plans have lower direct-name overlap because PC uses names such as
`cpu-cert-automated` while IoT uses `cpu-automated`. They still share jobs from
the same base provider, but their exact includes, certification statuses, and
after-suspend composition differ. An expanded-plan comparison is required to
measure job-level overlap accurately.

### IoT exclusions relevant to ARM PC Sanity

The 26.04 IoT desktop/server plans explicitly exclude several cases that are
poor defaults for embedded ARM products:

* `power-management/tickless_idle` and its after-suspend sibling;
* GLX gears jobs;
* `hdparm` disk benchmarks;
* laptop lid, light-sensor, and airplane-mode jobs in manual plans;
* selected disk detection/parking and multi-head cases; and
* selected CPU and memory stress jobs from the stress plan.

Ubuntu Core adds more exclusions for apt updates, debsums, desktop package
recommendations, GRUB, NTP, and some suspend/audio behavior because those
tests do not fit the immutable Core image model.

These exclusions should not automatically be copied to an ARM PC plan. An
ARM laptop may legitimately need touchpad, lid, display, airplane-mode, and
desktop package-policy coverage. Select by product capability and image type,
not by architecture alone.

### Existing ARM and architecture-neutral IoT coverage

The following implementations are directly relevant to filling PC Sanity's
ARM gaps:

| IoT/CE OEM test | What it provides | Reuse recommendation |
| --- | --- | --- |
| `cpu/arm64_vfp_support_aarch64` | Existing aarch64 floating-point capability check in the base provider. | Retain through the shared CPU plan; it does not replace idle or thermal tests. |
| `ce-oem-cpu-automated` | Discovers cpufreq policies and tests available governors. It excludes `intel_pstate` and operates on sysfs policies. | Strong candidate to replace part of the Intel/MSR CPU power coverage. Move generic functionality to the base provider if PC Sanity must consume it without CE OEM. |
| `ce-oem-dvfs-automated` | Discovers devfreq processors and validates governors, gated by `has_processor_dvfs_support`. | Use for GPU/NPU/memory-controller DVFS where the product manifest declares support. It is not equivalent to CPU C-state residency. |
| `ce-oem-thermal-automated` | Enumerates thermal zones, monitors temperatures, and compares zone identities before and after suspend. | Strong generic ARM thermal baseline. Add product-specific load, trip-point, cooling-device, and throttling acceptance criteria. |
| `ce-oem-dtb-automated` | Attaches the runtime device tree on aarch64/armv7l systems. | Use for device-tree inventory and diagnostics; add schema/policy validation if a pass/fail result is required. |
| `iot-fwts-automated` | Runs FWTS desktop diagnosis and attaches results. | Evidence that IoT uses FWTS, not proof that every FWTS test supports ARM. Gate individual categories on FWTS capability and firmware model. |
| GPIO, I2C, EEPROM, serial, SocketCAN, RTC, watchdog plans | Embedded peripheral validation selected by resources/manifests. | Include only when those interfaces are product requirements. |
| Dragonwing, Genio, Jetson, RZ, and Xilinx plans | Vendor-specific camera, codec, AI/ML, accelerator, thermal, firmware, and watchdog tests. | Use only for the matching SoC/platform; do not put these jobs in a generic arm64 plan. |

### Coverage that IoT does not solve

Adopting the IoT plans does not fix these PC Sanity requirements:

* PC Sanity Debian packaging (`Architecture: all`, native `uwake`, and
  `msr-tools`) remains broken for arm64.
* PC Sanity's dangling turbostat includes remain unresolved.
* OEM archive, platform metapackage, production-suite, public/private package,
  and image-release policy checks are absent or different.
* The PCI-only `check-gpu-driver` false pass and PC display policy remain.
* SMBIOS token behavior remains inappropriate for many ARM systems.
* IoT cpufreq and thermal-zone checks are not equivalent to system suspend
  residency, measured platform power, ARM SMMU isolation, or complete thermal
  throttling validation.
* A classic ARM laptop still needs input, touchpad, camera, display, desktop,
  and suspend policy that an embedded IoT plan may exclude.

### Recommended reuse strategy

Do not replace `pc-sanity-smoke-test-*-automated` wholesale with an IoT plan.
Instead:

1. Extract a `pc-sanity-common` plan containing architecture-neutral OEM image
   and kernel checks.
2. Continue using the shared 26.04 base plans for common desktop hardware.
3. Keep Intel C-state and Intel thermal plans as capability-gated x86
   overlays, not common nested plans.
4. Upstream generic CE OEM cpufreq, devfreq, thermal-zone, and device-tree
   functionality into `providers/base`, or package CE OEM as an explicit
   dependency if its release lifecycle is acceptable.
5. Add an ARM platform overlay selected by manifest/resource data, with
   separate SoC overlays where required.
6. Compare fully expanded job IDs and results on native hardware. Direct plan
   names alone cannot establish equivalent coverage.

A possible 26.04 structure is:

```text
pc-sanity-smoke-test-26-04-arm64
  pc-sanity-common
  client-cert-desktop-26-04-automated
  arm64-cpu-power-automated
  arm64-thermal-automated
  arm64-firmware-automated
  <optional SoC/product overlay>
```

Use the IoT desktop plan instead of the desktop certification plan only when
the target is genuinely an IoT product and its exclusions match the product
requirements.

### Result classifications

The tables below use these terms:

* **Installation blocker**: prevents apt from installing the provider.
* **Unresolved**: the test plan references a job absent from this repository.
* **Not generated/not selected**: Checkbox requirements or template filters
  exclude the job. This is safe execution behavior but is a coverage gap.
* **Fail**: the job is selected and its command is expected to return nonzero.
* **Risk**: selection and outcome depend on firmware, resources, or hardware;
  an ARM execution result is needed.

## Known affected test cases

### Package and plan blockers

| Item | Current ARM behavior | Required change | Alternative |
| --- | --- | --- | --- |
| Provider installation | Blocked or invalid because of `msr-tools` and the amd64 `uwake` binary in an `all` package. | Qualify `msr-tools`; build provider as `any` on arm64. | Split native/x86 dependencies into companion packages. |
| Six `power-management/check-turbostat-*` includes | Unresolved: no definitions exist in this repository. | Restore/version the definitions or remove the includes; add architecture and capability requirements. | Keep them in a documented external provider and make that provider an explicit dependency. |
| `autopkgtest.sh` | Focal amd64 only. Formal `debian/tests/control` runs help/list/bootstrap and CVE tests, but does not list the existing `pc-sanity-smoke-test` script. | Parameterize series and architecture; add package installation, plan expansion, and a non-destructive smoke invocation on arm64. | Use Launchpad arm64 builds plus Ubuntu autopkgtest infrastructure instead of the helper script. |

The unresolved turbostat IDs are:

* `power-management/check-turbostat-long-idle-cpu-residency`
* `power-management/check-turbostat-long-idle-s0ix-residency`
* `power-management/check-turbostat-long-idle-gfxrc6-residency`
* `power-management/check-turbostat-s2i-cpu-residency`
* `power-management/check-turbostat-s2i-s0ix-residency`
* `power-management/check-turbostat-s2i-gfxrc6-residency`

The local `check-turbostat-power-residency.sh` implementation exits nonzero
when `turbostat` is absent and reads Intel-specific `Pkg%pc10`, `SYS%LPI`, and
`GFX%rc6` counters. If job definitions are restored without requirements,
all six will fail on ARM.

### Direct `pc-sanity-base` jobs

| Job or pattern | Expected ARM behavior | Gap and required action | Alternative |
| --- | --- | --- | --- |
| `miscellanea/check-i2c-hid-existence` | Risk on ARM laptops identified by DMI. It fails if no input device reports an `i2c` physical path. | Gate on an explicit touchpad requirement and accept valid USB, SPI, or platform-specific touchpads where product policy permits. | Replace with a capability test that verifies a working pointer device rather than its bus. |
| `miscellanea/check_GenuineIntel_unchecked_msr_access_error` | Not generated because the template requires `GenuineIntel`. | No execution fix; document the x86-only coverage. | Add ARM-specific kernel error patterns only where they represent stable platform requirements. |
| `miscellanea/intel_pmc_core` | Not selected because it requires `GenuineIntel` and `s2idle`. | No execution fix; remove it from the common base plan or retain it as explicitly x86-only. | Add an ARM idle-driver/PSCI readiness job selected by actual interfaces. |
| `miscellanea/acpi-bios-error_*` | Not generated because the template permits only Intel and AMD CPU types. | This misses ACPI-based ARM systems. Gate on ACPI availability instead of CPU vendor if ACPI ARM is in scope. | Add a separate ARM firmware-error job for ACPI and/or device-tree platforms. |
| `miscellanea/intel-vtd-enabled_*` | Not selected because it requires `GenuineIntel`. | No execution fix; ARM SMMU coverage is absent. | Add an ARM SMMU/IOMMU attachment test for devices that require isolation. |
| `miscellanea/intel-hid_*` | Not generated because the template requires `GenuineIntel`. | No execution fix; do not treat omission as ARM HID coverage. | Add capability-based input/HID checks for the target ARM product. |
| `miscellanea/dump_libsmbios_tokens` | Failure if `apt-file` cannot find an arm64 package or `smbios-token-ctl` cannot access tokens. It has no applicability gate and performs `apt-get update/install` during the test. | Move dependencies into packaging, add executable and firmware requirements, and decide whether SMBIOS tokens are mandatory on supported ARM products. | Skip it for device-tree products or collect `/sys/firmware/devicetree` data instead. |
| `miscellanea/dump_libsmbios_tokens_attachment` | Depends on the dump output and otherwise produces no useful ARM evidence. | Select only with the producer. | Add a device-tree/firmware attachment job. |
| `miscellanea/check-display_*` | Risk. `uwake` is portable after a native arm64 build; DRM connector and DPMS layout still needs platform testing. | Fix packaging, require `uwake`, and test internal-panel DRM behavior on each target graphics stack. | Wake through logind/desktop APIs or use a platform-neutral display helper. |
| `miscellanea/check-gpu-driver` | Misleading pass for a platform-bus ARM GPU: the script enumerates only PCI display classes, then exits successfully when that list is empty and no NVIDIA module exists. | Make GPU discovery bus-neutral, fail/not-select when no expected GPU is examined, and define what "signed" means for built-in/in-tree ARM drivers. | Split proprietary-module signature checks from generic GPU-driver binding checks. |
| `miscellanea/renderer-mesa-driver-check_*` | Risk but potentially portable. | Validate expected renderers for Panfrost, Freedreno, V3D, and other supported stacks. Avoid x86-only renderer allowlists. | Maintain platform-specific expected renderer data. |
| `miscellanea/check_windowing_system_*` | Risk. It selects X11 only when `lspci` reports NVIDIA and otherwise expects Wayland. | Detect the active driver/session directly and define ARM GPU policy; do not infer architecture support solely from PCI output. | Restrict this OEM policy job to products for which that policy is defined. |
| `miscellanea/check-nvidia` | Not selected without an NVIDIA resource; risk on ARM systems that do have NVIDIA hardware. | Validate `nvidia-smi`, driver packaging, and PRIME assumptions on the target ARM product. | Keep a separately qualified NVIDIA-on-ARM profile. |
| `miscellanea/check_nvidia_modalias_*` | Not generated without an NVIDIA PCI device. | Validate `ubuntu-drivers` ARM package recommendations if NVIDIA PCI devices are in scope. | Use a product-specific driver assertion. |
| `miscellanea/touchpad-firmware-version_*` | Normally not generated because it targets specific device IDs and DMI SKUs. | No generic ARM action. Validate only if those exact devices are shipped. | Keep as a product-specific overlay. |
| `miscellanea/check-fcclock-state_*` | Risk when a matching Intel or Qualcomm WWAN device is present. | Exercise the script with matching Qualcomm ARM hardware and remove any PCI-only assumptions. | Move it to a modem/product-specific plan. |
| `miscellanea/gate_rste_raid` | Harmless pass when the Intel AHCI remapping path is absent, but supplies no ARM storage coverage. | Mark/gate as Intel-specific to avoid a misleading pass. | Add storage-controller checks appropriate to the target platform. |
| `miscellanea/platform-meta-test`, `platform-userguide-test`, and `check_production_suite` | Product/repository-policy dependent. | Ensure ARM OEM archives publish architecture-correct metapackages and that scripts do not assume amd64 package indexes. | Exclude commercial OEM policy checks from a generic ARM profile. |
| `miscellanea/boot-up-time-under-2-min` | Risk when DMI classifies an ARM product as a laptop. | Validate the threshold and boot-complete definition on representative ARM hardware. | Use product-specific performance thresholds. |
| `miscellanea/cvescan` | Installation blocker on 22.04 unless another configured repository supplies `openscap-scanner`; architecture-neutral on releases that provide arm64 OpenSCAP. | Document the package source per release and test OVAL data download/evaluation on arm64. | Use another supported Ubuntu vulnerability scanner or omit this job only with an explicit coverage waiver. |

Other direct jobs based on generic Linux interfaces, package metadata, kernel
logs, Bluetooth, Wi-Fi, CVE data, and debsums are likely portable but still
require an arm64 execution pass.

### CPU C-state nested plan

| Job | Expected ARM behavior | Gap and required action | Alternative |
| --- | --- | --- | --- |
| `power-management/idle-screen-on-residency-check` | Not selected: requires `GenuineIntel`, `msr-tools`, and `s2idle`. | Treat as x86-only and remove the package-level MSR dependency on ARM. | Measure ARM cpuidle state residency before/after screen-off. |
| `power-management/cpu-low-power-idle` | Usually not selected unless the resource reports one of two expected LPI files. If selected through `low_power_idle_cpu_residency_us`, it may be portable; the fallback is Intel PMC-specific. | Split generic LPIT-counter and Intel PMC implementations into separately gated jobs. | Implement a cpuidle residency delta check using the target idle driver. |
| `power-management/system-low-power-idle` | Usually not selected. One LPIT path may work on ACPI ARM; the fallback reads Intel `slp_s0_residency_usec`. | Split the two backends and require the exact readable interface used by each command. | Validate suspend through PSCI and platform counters; retain functional suspend tests separately. |

Do not use x86 C-state names as ARM acceptance criteria. Define equivalent
outcomes such as residency increasing in an expected idle state, successful
suspend/resume, and acceptable power draw.

### Intel thermal nested plan

`thermal-cert-automated` describes itself as Intel coverage but is nested
unconditionally by every PC Sanity smoke plan.

| Job or pattern | Expected ARM behavior | Gap and required action |
| --- | --- | --- |
| `thermal/thermald`, `thermal/thermald-cpu-support` | Not selected unless the manifest says thermald is supported. | Ensure the ARM manifest does not claim Intel thermald support accidentally. Define the ARM thermal daemon/policy requirement separately. |
| `thermal/intel-rapl` | Dependency-blocked when `thermal/thermald` is not selected; would fail without Intel RAPL if forced. | Keep in an Intel-only subplan. |
| `thermal/intel-rapl-mmio_*`, `thermal/proc_thermal_*` | Not generated without the exact Intel PCI device. | No ARM execution fix; these are Intel-only. |
| `thermal/intel-p-state` | Dependency-blocked in a correct ARM manifest; would fail if forced. | Keep in an Intel-only subplan. ARM commonly uses `cpufreq` drivers such as `cppc_cpufreq` or platform drivers. |
| `thermal/intel-powerclamp` | Dependency-blocked; implementation is Intel-specific. | Keep in an Intel-only subplan. |
| `thermal/intel-cpu-thermal`, `thermal/intel-x86-pkg-temp-thermal` | Dependency-blocked; accepted zone types are x86/Intel-specific. | Keep in an Intel-only subplan. |
| `thermal/valid-thermal-zone-trip-points` | Potentially useful on ARM but currently depends on the Intel thermald job. | Extract a generic thermal-zone test with ARM-appropriate exclusions and expected trip-point policy. |
| `thermal/thermal-policy-set_*`, `thermal/adaptive-fallback`, `thermal/check-thermald-unknown-cond` | Intel DPTF/thermald-oriented or conditionally selected. | Keep in the Intel subplan unless the same userspace policy is explicitly supported on an ARM product. |

Preferred structural fix: rename or retain the existing plan as an Intel
thermal plan, stop nesting it unconditionally, and add an ARM thermal plan
covering thermal zones, cooling devices, trip points, throttling response,
and the platform's actual thermal policy service.

### Nested desktop certification plans

The 22.04, 24.04, and 26.04 automated desktop plans are capability-heavy and
too broad to certify from static inspection alone. Before declaring ARM
support, execute their fully expanded job lists on each representative
platform.

Known CPU, ACPI, and power-management outcomes are:

| Job or pattern | Expected ARM behavior | Required action |
| --- | --- | --- |
| `acpi/oem_osi` | Not selected because it explicitly accepts only i386 and x86_64. | This is correct for the existing x86 DSDT/SSDT policy, but an ACPI ARM plan needs its own applicable firmware checks. |
| `cpu/cstates`, `after-suspend-cpu/cstates`, and attachments | Not selected because aarch64 is explicitly excluded. | Add cpuidle/PSCI coverage instead of x86 C-state names. |
| `cpu/maxfreq_test` and after-suspend variant | Not selected because only i386 and x86_64 are accepted. | Add an ARM cpufreq maximum-frequency/transition test if required. |
| `cpu/topology` and after-suspend variant | Not selected because only i386 and x86_64 are accepted. | Extend the topology implementation and resource parsing to aarch64, or add an ARM topology test. |
| `power-management/tickless_idle` and after-suspend sibling | Not selected because aarch64 is not in the platform list. | Decide whether `CONFIG_NO_HZ` is an ARM product requirement and extend the test if so. |
| `cpu/arm64_vfp_support_aarch64` | Generated on aarch64 and checks the CPU resource for floating-point support. | Retain as useful existing ARM coverage; verify `/proc/cpuinfo` parsing on each target kernel. |
| `cpu/scaling_test` and after-suspend variant | Risk: selected when FWTS exists and the `userspace` governor is reported; aarch64 is not excluded. | Run FWTS `cpufreq` on native targets, gate on a supported FWTS test category, and use a native cpufreq test when FWTS lacks ARM support. |
| `cpu/offlining_test` and after-suspend sibling | Potentially portable and selected when the resource reports support. | Validate hotplug behavior and platform restrictions on native ARM hardware. |
| `cpu/clocktest` and after-suspend sibling | Selected on aarch64 because only s390x is excluded. | Validate the helper binary and timing thresholds on arm64. |
| `power-management/fwts_wakealarm` and after-suspend variant | Risk: selected whenever FWTS is executable, with no ACPI/architecture requirement. | Require the FWTS `wakealarm` category and a usable RTC/wakealarm interface; add a non-FWTS RTC wake test where appropriate. |
| `power-management/rtc` and after-suspend sibling | Potentially portable; selected from the RTC resource. | Validate `/sys/class/rtc/*/since_epoch` and configured RTC device selection. |

The wider nested suite must also be reviewed in at least these areas:

* **ACPI and firmware:** distinguish ACPI ARM from device-tree systems; gate
  `fwts`, wakealarm, and ACPI jobs on the interfaces they use.
* **Suspend and power:** verify `rtcwake`, RTC wake alarms, logind suspend,
  wake sources, and post-suspend comparisons. Do not substitute Intel S0ix
  counters for successful ARM suspend.
* **Graphics:** support platform-bus GPUs and in-tree DRM drivers, not only
  PCI Intel/AMD/NVIDIA devices.
* **CPU:** remove assumptions about x86 vendor strings, C-states, MSRs,
  `intel_pstate`, RAPL, and `/proc/cpuinfo` field layout.
* **Firmware update:** verify fwupd has a supported transport and metadata for
  the target product; absence may be valid only if product policy says so.
* **Thunderbolt/PCIe:** select only when the hardware resources exist. USB4 on
  ARM must be validated by capability, not CPU architecture.
* **TPM:** verify the TPM interface, event log, and UEFI measurements on the
  target firmware model.
* **DMI-dependent selection:** resource jobs and templates that require DMI
  may disappear on device-tree products. Add a platform/product resource that
  works across firmware models before relying on chassis or SKU gates.

For this nested suite, a missing job can mean either correct hardware-based
selection or an undetected ARM device. The expansion report must therefore be
reviewed alongside `lspci`, `lsusb`, udev, DRM, input, DMI, ACPI, and
device-tree inventories.

## Required implementation work

### Phase 1: make installation possible

1. Change the PC Sanity package to `Architecture: any` and remove its Lintian
   binary-in-`all` override.
2. Make the native build honor the Debian compiler and build flags.
3. Qualify `msr-tools` for the architectures on which it exists.
4. Resolve the 22.04 `openscap-scanner` dependency from a documented archive
  or PPA, or replace it.
5. Build and publish all `Architecture: any` dependencies for arm64 in each
   supported Ubuntu series.
6. Resolve all package dependencies in a clean arm64 image with both normal
   apt behavior and `--no-install-recommends` documented.
7. Add native arm64 package build and installation CI.

### Phase 2: make plan execution deterministic

1. Resolve the six dangling turbostat job references.
2. Add requirements based on actual executable, resource, sysfs, firmware,
   and driver capabilities. Architecture should be a last-resort gate when
   the interface itself can be detected.
3. Split commands that contain both generic and Intel fallback paths so a
   selected ARM job cannot enter an Intel-only branch.
4. Gate SMBIOS, DMI, ACPI, PCI, and fwts tests according to the target
   firmware and bus model.
5. Make unsupported tests visibly `not-supported`/not selected, not passing
   no-op checks. Preserve the distinction in exported results.

### Phase 3: provide equivalent ARM coverage

Add ARM plans selected by platform capabilities. Candidate coverage includes:

* cpuidle driver and state discovery, usage/time deltas, and expected deepest
  state under controlled idle;
* cpufreq policy/driver discovery and frequency transition checks;
* PSCI/system suspend and wake-source validation;
* thermal zones, valid trip points, cooling devices, throttling, and recovery;
* ARM SMMU/IOMMU group attachment for devices requiring DMA isolation;
* device-tree validation and attachment, with ACPI checks retained for ACPI
  ARM systems;
* platform-bus and PCI GPU driver binding, DRM connectors, rendering, and
  Wayland/X11 policy;
* firmware update, secure boot, measured boot, and TPM behavior appropriate
  to the product; and
* platform-specific kernel error signatures maintained as data, not embedded
  assumptions in a generic ARM plan.

Use functional acceptance criteria where platforms expose different counters.
For example, require suspend/resume and a measurable residency increase rather
than requiring the Intel PC10 state by name.

### Phase 4: validate and release

Required CI and lab matrix:

| Layer | Minimum validation |
| --- | --- |
| Source | Provider validation, ShellCheck, Python tests, BATS, and package build on amd64 and arm64. |
| Installation | Clean supported-release arm64 image; install all packages from the intended PPA/archive without local files. |
| Discovery | Capture selected, not selected, missing, and unresolved jobs from each smoke plan. |
| Execution | Run on at least one ACPI ARM platform and one device-tree ARM platform if both are in scope. |
| Regression | Run unchanged amd64 PC Sanity plans to ensure architecture gating does not reduce existing coverage. |
| Results | Confirm skipped/not-supported jobs are distinguishable from pass and that attachments contain ARM firmware/hardware inventory. |

Do not use an amd64 host with arm64 userspace emulation for hardware tests.
QEMU is useful for package installation, provider loading, and plan expansion,
but power, firmware, graphics, suspend, input, and thermal acceptance requires
native hardware.

## Acceptance criteria

ARM64 PC Sanity support is complete only when all of the following are true:

* All required packages build and install from a supported repository on a
  clean arm64 target.
* No architecture-independent package contains an architecture-specific
  executable.
* Every included job ID resolves without private, undocumented side loads.
* Every selected job has all commands and kernel interfaces it uses.
* x86-only jobs are explicitly excluded and reported as not applicable, not
  counted as ARM test coverage.
* ARM replacements exist for agreed power, thermal, firmware, graphics, and
  IOMMU requirements.
* The expanded plan and execution results have been reviewed on every target
  platform class and supported Ubuntu release.
* The existing amd64 plans retain their current coverage and pass criteria.
* Installation, plan expansion, and a hardware smoke run are continuously
  tested on arm64.

## Evidence in this repository

* `checkbox-ng/debian/control`: core packages are `Architecture: all`.
* `checkbox-support/debian/control`: support library is `Architecture: all`.
* `providers/resource/debian/control` and `providers/resource/src`: native,
  portable nl80211 resource helper packaged as `Architecture: any`.
* `providers/certification-client/debian/control`: ARM-aware
  `glmark2-es2` dependency.
* `contrib/pc-sanity/debian/control`: current `Architecture: all`, hard
  `msr-tools` dependency, and `${shlibs:Depends}`.
* `contrib/pc-sanity/debian/rules`, `c/Makefile`, and `c/uwake.c`: native
  helper compilation and installation, including a hard-coded compiler.
* `contrib/pc-sanity/debian/lintian-overrides`: suppressions for a binary in an
  architecture-independent package and for native-binary quality checks.
* `contrib/pc-sanity/autopkgtest.sh` and `debian/tests/control`: hard-coded
  Focal amd64 helper and formal tests that do not execute the smoke-plan
  script.
* `units/pc-sanity/pc-sanity.pxu`: direct jobs and nested smoke plans.
* `units/pc-sanity/pc-sanity-check-devices.pxu`: Intel, DMI, display, input,
  GPU, and WWAN selection behavior.
* `providers/base/units/power-management/jobs.pxu`: Intel/MSR and LPIT/PMC
  CPU/system residency jobs.
* `providers/base/units/thermal/test-plan.yaml` and `jobs.yaml`: explicitly
  Intel thermal plan nested by PC Sanity.
* `providers/certification-client/units/client-cert-desktop-*.pxu`: broad
  nested desktop certification plans.

The local `./manage.py validate` run on 2026-10-13 was not a clean plan
resolution check: installed and workspace copies of the resource provider
produced duplicate-unit errors, and the validator then crashed while resolving
`platform-meta-test`. Validation must be repeated in a clean build/test
environment. This also reinforces the need for a dedicated expanded-plan test
that fails on unresolved includes.

## Open decisions

1. Which ARM product and firmware classes are officially in scope?
2. Is equivalent functional coverage acceptable, or must ARM expose an
   identical job list?
3. Should ARM support live in the existing smoke-plan IDs through dynamic
   nesting, or in explicit `*-arm64` plan IDs?
4. Which ARM power and thermal interfaces are stable requirements across the
   chosen product set?
5. Are private/sideloaded providers expected to supply the turbostat jobs? If
   so, how will that dependency be versioned, packaged, and tested?
6. Which Ubuntu archive/PPA publishes the arm64 provider packages for every
   supported release?