# I2C Read and Write Readme

In some test scenarios, there may be no corresponding device node in sysfs, yet read/write testing is still required for physical devices behind the I2C bus. Because device types vary, we cannot define this as a fixed job in Checkbox. Instead, we use an external JSON file together with a Checkbox resource job to dynamically generate the appropriate jobs and test steps.

Therefore, this document is intended to demonstrate how to write a JSON file that conforms to the required format.

# JSON Format

## Structure Diagram

```json
{
  "scenarios": [                       // Mandatory, array
    {
      "scenario_name": "...",          // Mandatory
      "steps": [                       // Mandatory, array
        {
          "description": "...",        // Mandatory
          "operation": "write",        // Mandatory: "write" | "read"
          "i2c_bus": 10,               // Mandatory
          "chip_address": "0x50",      // Mandatory

          "reg_address": ["0x00"],     // Optional
          "delay_ms": 5,               // Optional, default 0

          "data": ["0x11", "0x22"]     // For write: exactly one of
          // "data_from_variable": "..."  // data or data_from_variable
        },
        {
          "description": "...",
          "operation": "read",
          "i2c_bus": 10,
          "chip_address": "0x44",

          "reg_address": ["0x00"],       // Optional
          "delay_ms": 0,                 // Optional

          "read_length": 2,              // Mandatory for read
          "expected_output": ["0x11"],   // Optional (verification use)
          "save_to_variable": "temp"     // Optional (dynamic data use)
        }
      ]
    }
  ]
}
```

### 1. Scenario-level fields

- `scenarios` (Mandatory)
  - Root node of the JSON document.
  - Must be an array.
- `scenario_name` (Mandatory)
  - Name of the scenario.
  - It does not affect command execution, but it is required for readable logs.
- `steps` (Mandatory)
  - Array containing all test steps in the scenario.

### 2. Step-level fields

The following fields are required for every step, regardless of operation type:

- `description` (Mandatory)
  - Step description used in log output.
- `operation` (Mandatory)
  - Operation type.
  - Allowed values: `"write"` or `"read"`.
- `i2c_bus` (Mandatory)
  - I2C bus number as an integer (for example, `10` or `1`).
- `chip_address` (Mandatory)
  - Chip address as a hexadecimal string (for example, `"0x50"`).

The following fields are optional depending on hardware behavior:

- `reg_address` (Optional)
  - Applicable to both `read` and `write`.
  - Required for devices with internal register/memory addresses (for example, EEPROM).
  - Omit for address-less devices (for example, PCF8574) or command-driven sensors when not needed.
- `delay_ms` (Optional)
  - Applicable to both `read` and `write` (most commonly after `write`).
  - Wait time after the step, in milliseconds.
  - If omitted, the default is `0`.

### 3. Conditional fields by operation

These fields are optional in the schema, but required in specific contexts.

#### When `operation` is `"write"`

- `data` and `data_from_variable` are conditionally required as an exclusive pair:
  - Provide exactly one of them.
  - Do not provide both.
  - Do not omit both.
- `data`
  - Static byte array to write (for example, `["0x11", "0x22"]`).
- `data_from_variable`
  - Variable name that references data saved from a previous step (for example, `"sensor_temp"`).

#### When `operation` is `"read"`

- `read_length` (Mandatory for `read`)
  - Number of bytes to read.
- `expected_output` (Optional)
  - Expected fixed output (for example, `["0x11", "0x22"]`).
  - Use this when the read step is for verification.
  - Omit this when reading dynamic sensor data.
- `save_to_variable` (Optional)
  - Variable name used to store dynamic read data for later steps (for example, `"sensor_temp"`).

# Examples

## Example 1 - Write and Read the same deivce

This example performs a write-read verification on the same FT24C32 EEPROM.
It writes `0x11 0x22 0x33 0x44` to register address `0x0000` on bus `10`
(`chip_address` `0x50`), waits `5 ms`, then reads back `4` bytes from the
same register and compares the result with `expected_output`.

### JSON definition
```json
{
  "scenarios": [
    {
      "scenario_name": "FT24C32 EEPROM Basic Write-Read",
      "steps": [
        {
          "description": "Write initial data to EEPROM",
          "operation": "write",
          "i2c_bus": 10,
          "chip_address": "0x50",
          "reg_address": ["0x00", "0x00"],
          "data": ["0x11", "0x22", "0x33", "0x44"],
          "delay_ms": 5
        },
        {
          "description": "Verify EEPROM data",
          "operation": "read",
          "i2c_bus": 10,
          "chip_address": "0x50",
          "reg_address": ["0x00", "0x00"],
          "read_length": 4,
          "expected_output": ["0x11", "0x22", "0x33", "0x44"]
        }
      ]
    }
  ]
}
```

## Example 2 - Read and Write the differenct devices

This example demonstrates cross-device data transfer across different I2C
buses. It first reads dynamic data from an SHT30 sensor on bus `10`
(`chip_address` `0x44`) and stores the result in `sensor_temp`. It then
writes that stored value to an OLED device on bus `1` (`chip_address`
`0x3C`) by using `data_from_variable`, which shows how one step can consume
data produced by a previous step.

### JSON definition

```json
{
  "scenarios": [
    {
      "scenario_name": "Cross-Bus Sensor to Display Bridge",
      "steps": [
        {
          "description": "Read from SHT30 Sensor on Bus 10",
          "operation": "read",
          "i2c_bus": 10,
          "chip_address": "0x44",
          "read_length": 2,
          "save_to_variable": "sensor_temp"
        },
        {
          "description": "Write sensor data to OLED on Bus 1",
          "operation": "write",
          "i2c_bus": 1,
          "chip_address": "0x3C",
          "reg_address": ["0x40"],
          "data_from_variable": "sensor_temp"
        }
      ]
    }
  ]
}
```