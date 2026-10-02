# Serial tests

This directory contains the CE OEM serial test jobs.

## Serial raw UART self-loopback tests

The serial raw UART self-loopback tests check that one or more raw UART ports can
transmit and receive data when each port has its TX and RX pins connected
together on the same physical UART port.

These tests only validate self-loopback wiring. They do not validate
communication between two different UART ports or two different devices.

### Test plan

The generated jobs are included by `ce-oem-serial-automated` through these
template IDs:

```text
ce-oem-serial/raw-uart-self-loopback-quick-tests
ce-oem-serial/raw-uart-self-loopback-stress-tests
```

The jobs also use `flags: also-after-suspend`, so Checkbox can generate
before-suspend and after-suspend variants for suspend flows.

### Manifest

Enable the manifest gate before running the generated jobs:

```text
has_serial_raw_uart_self_loopback: True
```

If this manifest value is not `True`, the generated raw UART jobs are not
selected even when `RAW_UART_PORTS` is configured.

### Environment

Set `RAW_UART_PORTS` in the Checkbox configuration. The value is a
space-separated list of entries with this format:

```text
NAME:TARGET:BAUD
```

Fields:

| Field | Description |
| --- | --- |
| `NAME` | Short unique name for the UART. It is normalized for the generated job ID. |
| `TARGET` | Hardware address such as `0x2260000`, or a device node such as `/dev/ttyS1`. |
| `BAUD` | Integer baud rate, `max`, `sweep`, or `autoscan-max`. |

Examples:

```text
RAW_UART_PORTS=uart0:0x2260000:max
RAW_UART_PORTS="uart0:0x2260000:max uart1:/dev/ttyS1:115200"
RAW_UART_PORTS="uart0:0x2260000:sweep uart1:/dev/ttyS1:autoscan-max"
```

Quick and stress jobs sweep downward from an explicit integer baud rate to 9600
by default. This default is used when `RAW_UART_SWEEP_DOWN` is not set:

```text
RAW_UART_SWEEP_DOWN=true
```

`RAW_UART_SWEEP_DOWN` supports integer baud values, such as `115200`, and
`max`, which starts from the driver-reported baud base. It is not valid with
`sweep` or `autoscan-max`.

Disable sweep-down explicitly when you only want to test the configured integer
baud rate:

```text
RAW_UART_SWEEP_DOWN=false
```

Stress jobs also support optional environment overrides. The PXU command uses
these defaults when the variables are not set:

```text
RAW_UART_STRESS_COUNT=100
RAW_UART_STRESS_SIZE=1024
```

Example override:

```text
RAW_UART_STRESS_COUNT=50
RAW_UART_STRESS_SIZE=512
```

### Hardware connection

Connect the same UART port's TX and RX pins together before running the test:

```text
UART TX -----+
             | (Jumper short)
UART RX -----+
```

The TX and RX pins must belong to the same UART controller and the same
physical port. This is why the test is named self-loopback. Do not connect TX
from one UART port to RX on a different UART port for this test case.

USB serial adapters are blocked by default because they are not raw UART
self-loopback targets for this CE OEM test.

### Resource input and output

Input:

```bash
serial_raw_uart_test.py list "uart0:0x2260000:max uart1:/dev/ttyS1:115200"
```

Output:

```text
name: uart0
name_id: uart0
target: 0x2260000
target_id: 0x2260000
target_type: addr
baud: max

name: uart1
name_id: uart1
target: /dev/ttyS1
target_id: dev_ttyS1
target_type: node
baud: 115200
```

### Test input and output

Quick self-loopback test input:

```bash
serial_raw_uart_test.py quick --target 0x2260000 --baud max
```

Example success output:

```text
PASS: /dev/ttyS0 115200 baud PASSED
```

Example failure output:

```text
FAIL: /dev/ttyS0 115200 baud FAILED
```

Quick self-loopback sweep-down input:

```bash
serial_raw_uart_test.py quick --target /dev/ttyS1 --baud 115200 --sweep-down
```

Stress self-loopback test input:

```bash
serial_raw_uart_test.py stress --target /dev/ttyS1 --baud 115200 --count 100 --size 1024
```

Stress self-loopback sweep-down input:

```bash
serial_raw_uart_test.py stress --target /dev/ttyS1 --baud 115200 --count 100 --size 1024 --sweep-down
```

Example success output:

```text
PASS: /dev/ttyS1 115200 baud PASSED
```

### Safety defaults

The helper is conservative for certification runs:

* USB serial adapters are blocked for raw UART self-loopback.
* Active system console UARTs are blocked.
* Hardware-address targets are resolved from Linux UART driver data.
* Device-node targets are used directly after the same safety checks.

## RS485 Modbus peripheral tests

The RS485 Modbus peripheral test checks that the DUT can read raw registers
from one or more RS485 Modbus RTU devices. It is a general CE OEM serial test.

### Test plan

The generated jobs are included by `ce-oem-serial-automated` through the
`ce-oem-serial/rs485-modbus-read-tests` template ID. They also use
`flags: also-after-suspend`, so Checkbox can generate before-suspend and
after-suspend variants for suspend flows.

### Manifest

Enable the manifest gate before running the generated jobs:

```text
has_rs485_modbus_peripheral: True
```

If this manifest value is not `True`, the generated Modbus read jobs are not
selected even when `RS485_MODBUS_PERIPHERALS` is configured.

### Environment

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

### Running the job

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
