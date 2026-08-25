# RS485 Modbus peripheral tests

The RS485 Modbus peripheral test checks that the DUT can read raw registers
from one or more RS485 Modbus RTU devices. It is a general CE OEM serial test.

## Test plan

The generated jobs are included by `ce-oem-serial-automated` through the
`ce-oem-serial/rs485-modbus-read-tests` template ID. They also use
`flags: also-after-suspend`, so Checkbox can generate before-suspend and
after-suspend variants for suspend flows.

## Manifest

Enable the manifest gate before running the generated jobs:

```text
has_rs485_modbus_peripheral: True
```

If this manifest value is not `True`, the generated Modbus read jobs are not
selected even when `RS485_MODBUS_PERIPHERALS` is configured.

## Environment

Set `RS485_MODBUS_PERIPHERALS` in the Checkbox configuration. The value is a
space-separated list of entries with this format:

```text
NAME:NODE:BAUDRATE:UNIT_ID:REGISTER_TYPE:REGISTER_ADDRESS:REGISTER_COUNT:PARITY
```

Fields:

| Field | Description |
| --- | --- |
| `NAME` | Short unique name for the peripheral. It is normalized for the generated job ID. |
| `NODE` | Serial device node, such as `/dev/ttyS0`. |
| `BAUDRATE` | Serial baudrate, such as `9600`. |
| `UNIT_ID` | Modbus slave/unit ID. |
| `REGISTER_TYPE` | `holding` for holding registers or `input` for input registers. |
| `REGISTER_ADDRESS` | Starting register address. Use `0` when the first register is required. |
| `REGISTER_COUNT` | Number of registers to read. |
| `PARITY` | Serial parity: `N`, `E`, or `O`. |

Example with one peripheral:

```text
RS485_MODBUS_PERIPHERALS=device0:/dev/ttyS0:9600:1:holding:0:2:N
```

Example with two peripherals:

```text
RS485_MODBUS_PERIPHERALS="device0:/dev/ttyS0:9600:1:holding:0:2:N meter0:/dev/ttyS1:19200:2:input:10:4:E"
```

## Running the job

After setting the manifest and environment, run the automated serial plan:

```bash
checkbox-ce-oem.checkbox-cli run com.canonical.contrib::ce-oem-serial-automated
```

The resource job uses `rs485_modbus_test.py list` to generate resources from
`RS485_MODBUS_PERIPHERALS`. The generated test job uses
`rs485_modbus_test.py read` to read the configured registers with `pymodbus`
and print the raw register values. The command also reserves
`rs485_modbus_test.py write` for future Modbus write tests.

The job fails if the configuration is malformed, the serial device cannot be
opened, the Modbus read fails, or the peripheral returns a Modbus error
response.
