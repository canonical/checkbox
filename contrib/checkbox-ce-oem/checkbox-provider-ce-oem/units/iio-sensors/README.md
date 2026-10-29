# Introduction to Industrial I/O (IIO) Sensor Test Jobs

## id: ce-oem-iio-sensors/resource
This resource job generates the list of IIO sensors to be tested, based on
the checkbox configuration variable "IIO_SENSORS".
It relies on the manifest "has_iio_sensors" to be true.

The value of "IIO_SENSORS" is a `|`-separated list of sensor entries, each
in one of these forms:
- `{sensor_name}:{sensor_type}` for non-ADC sensors
  (`pressure`, `accelerometer`, `humidityrelative`)
- `{sensor_name}:adc:{expected_input_number}` for ADC sensors, where
  `expected_input_number` is the number of voltage input channels the
  device is expected to expose

`sensor_name` must match the `name` sysfs node under
`/sys/bus/iio/devices/iio:deviceX/` for the sensor (i.e. what
`cat /sys/bus/iio/devices/iio:deviceX/name` reports), not a device index.

For example:
- `IIO_SENSORS=adc128s052:adc:7|lps25h-press:pressure`

(A single-space-separated legacy format without ADC support,
`{sensor_name}:{sensor_type} {sensor_name}:{sensor_type}`, is still
accepted as a fallback for existing checkbox configurations.)

## id: ce-oem-iio-sensors/check-{{ type }}-{{ name }}
This is a template job, generated once per entry produced by the
`ce-oem-iio-sensors/resource` job above. It looks up the sensor by name
under `/sys/bus/iio/devices/` and validates that the sysfs nodes expected
for its `sensor_type` exist and report numeric readings:

- `pressure`: `in_pressure_input`, `in_pressure_oversampling_ratio`,
  `in_pressure_sampling_frequency`
- `accelerometer`: `in_accel_sampling_frequency`, `in_accel_scale`,
  `in_accel_{x,y,z}_calibbias`, `in_accel_{x,y,z}_raw`
- `humidityrelative`: `in_humidityrelative_integration_time`,
  `in_humidityrelative_scale`, `in_humidityrelative_raw`
- `adc`: `in_voltage{0..expected_input_number-1}_raw`,
  `in_voltage_scale`. The number of `in_voltage*_raw` nodes actually
  present is also checked against `expected_input_number` and the job
  fails if they don't match.

This job runs both before and after suspend (`flags: also-after-suspend`).

## Test Coverage
We cover four IIO sensor types:
- Pressure
- Accelerometer
- Relative humidity
- ADC (analog-to-digital converter) voltage input channels

## Manifest
- `has_iio_sensors` (bool): whether the platform has IIO sensors to test.
  All jobs in this unit require this to be `True`.
