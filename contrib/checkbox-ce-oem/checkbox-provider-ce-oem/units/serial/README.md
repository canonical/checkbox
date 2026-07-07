# Serial raw UART loopback tests

The serial raw UART loopback tests check that one or more raw UART ports can
transmit and receive data when each port has its TX and RX pins connected
together.

## Test plan

The generated jobs are included by `ce-oem-serial-automated` through these
template IDs:

```text
ce-oem-serial/raw-uart-loopback-quick-tests
ce-oem-serial/raw-uart-loopback-stress-tests
```

The jobs also use `flags: also-after-suspend`, so Checkbox can generate
before-suspend and after-suspend variants for suspend flows.

## Manifest

Enable the manifest gate before running the generated jobs:

```text
has_serial_raw_uart_loopback: True
```

If this manifest value is not `True`, the generated raw UART jobs are not
selected even when `RAW_UART_PORTS` is configured.

## Environment

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

## Resource input and output

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

## Test input and output

Quick test input:

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

Stress test input:

```bash
serial_raw_uart_test.py stress --target /dev/ttyS1 --baud 115200 --count 100 --size 1024
```

Example success output:

```text
PASS: /dev/ttyS1 115200 baud PASSED
```

## Safety defaults

The helper is conservative for certification runs:

* USB serial adapters are blocked for raw UART loopback.
* Active system console UARTs are blocked.
* Hardware-address targets are resolved from Linux UART driver data.
* Device-node targets are used directly after the same safety checks.
