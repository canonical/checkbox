# GPIO Tests

The GPIO tests validate GPIO lines through `libgpiod`. The resource jobs
discover lines with the `gpio_test_subprocess.py` helper and generate one test
job for each eligible GPIO line or loopback pair.

These tests do not use the deprecated `/sys/class/gpio` interface.

## Common setup

Enable the `libgpiod` GPIO tests with the `has_gpiod_gpio` manifest entry:

```ini
[manifest]
has_gpiod_gpio = true
```

The test device needs the `gpiod` command-line tools available in the test
environment:

```bash
sudo apt install gpiod
```

To inspect GPIO chips and line names on the target device, run:

```bash
sudo gpioinfo
```

Use the stable chip name and line offset shown by `gpioinfo`, for example
`gpiochip0-8`. The scripts support both `libgpiod` v1 and v2 command output.

## `ce-oem-gpiod-gpio/simple-input-GPIO_CHIP-GPIO_LINE`

This template job requests one generated GPIO line as input and reads its value.
Generated jobs come from the `ce-oem-gpiod-gpio/simple-resource` resource job.

## `ce-oem-gpiod-gpio/simple-output-GPIO_CHIP-GPIO_LINE`

This template job requests one generated GPIO line as output, drives it low and
high, then restores the original direction and value when possible. Generated
jobs come from the `ce-oem-gpiod-gpio/simple-resource` resource job.

### Optional environment variables

Use these variables in the launcher `[environment]` section when needed:

| Variable                 | Description                                 | Default |
|--------------------------|---------------------------------------------|---------|
| `GPIOD_GPIO_IGNORE`      | GPIO lines, ranges, or chips to skip.       | Not set |
| `GPIOD_GPIO_ALLOW_NAMED` | Compatibility option; named lines are used. | Not set |

`GPIOD_GPIO_IGNORE` accepts multiple values separated by commas. Each value can
be one of:

- one line, for example `gpiochip0-2`
- a line range, for example `gpiochip16-0..4`
- a whole chip, for example `gpiochip14`
- a whole chip wildcard, for example `gpiochip14-*`

### Example simple-test launcher environment

```ini
[environment]
GPIOD_GPIO_IGNORE = gpiochip14-*,gpiochip16-0..4
GPIOD_GPIO_ALLOW_NAMED = true
```

Named unused GPIO lines are included by default. Use `GPIOD_GPIO_IGNORE` to skip
lines that appear unused but should not be driven, such as platform reset,
power, interrupt, or externally connected I/O lines.

## `ce-oem-gpiod-gpio/loopback-input-GPIO_INPUT_CHIP-GPIO_INPUT_LINE-output-GPIO_OUTPUT_CHIP-GPIO_OUTPUT_LINE`

This template job drives one GPIO output line and verifies that a physically
connected GPIO input line follows low and high states. Generated jobs come from
the `ce-oem-gpiod-gpio/loopback-resource` resource job.

### Required environment variables

Use this variable in the launcher `[environment]` section:

| Variable                   | Description                                    | Default  |
|----------------------------|------------------------------------------------|----------|
| `GPIOD_GPIO_LOOPBACK_PAIRS` | Comma-separated loopback pairs in `INPUT:OUTPUT` format. | Not set |

Each pair uses `INPUT:OUTPUT` order. For example, if `gpiochip0-100` is wired
to read the signal driven by `gpiochip0-0`, use:

```ini
[environment]
GPIOD_GPIO_LOOPBACK_PAIRS = gpiochip0-100:gpiochip0-0
```

Multiple pairs are separated by commas:

```ini
[environment]
GPIOD_GPIO_LOOPBACK_PAIRS = gpiochip0-100:gpiochip0-0,gpiochip1-2:gpiochip1-1
```

Before enabling loopback jobs, verify the physical wiring and any board-level
requirements such as common ground, external power, or isolated digital I/O
terminal wiring. Some lines shown by `gpioinfo` are control lines for external
I/O circuitry and may not behave as direct SoC GPIO loopbacks.
