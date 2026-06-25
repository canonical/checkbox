# PWM Tests

The PWM tests discover PWM outputs from `/sys/kernel/debug/pwm` and generate one
test job for each eligible PWM output.

## Required launcher settings

Enable the PWM tests with the `has_pwm` manifest entry:

```ini
[manifest]
has_pwm = true
```

## Optional environment variables

Use these variables in the launcher `[environment]` section when needed:

| Variable              | Description                                      | Default   |
|-----------------------|--------------------------------------------------|-----------|
| `PWM_IGNORE`          | Comma-separated controller or consumer names to skip. | Not set   |
| `PWM_ALLOW`           | Comma-separated active consumers or controllers to include. | Not set   |
| `PWM_TEST_PERIOD`     | Period value in nanoseconds for the test.        | `1000000` |
| `PWM_TEST_DUTY_CYCLE` | Duty-cycle value in nanoseconds for the test.    | `500000`  |

Example:

```ini
[environment]
PWM_IGNORE = platform/208c000.pwm
PWM_ALLOW = pwm-fan
PWM_TEST_PERIOD = 1000000
PWM_TEST_DUTY_CYCLE = 500000
```

`PWM_IGNORE` and `PWM_ALLOW` should use stable controller names or consumer
names, not `/sys/class/pwm/pwmchipN` names.

