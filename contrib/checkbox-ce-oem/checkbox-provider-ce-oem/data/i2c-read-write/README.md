# I2C Read and Write Readme

In some test scenarios, there may be no corresponding device node in sysfs, yet read/write testing is still required for physical devices behind the I2C bus. Because device types vary, we cannot define this as a fixed job in Checkbox. Instead, we use an external JSON file together with a Checkbox resource job to dynamically generate the appropriate jobs and test steps.

Therefore, this document is intended to demonstrate how to write a JSON file that conforms to the required format.

# JSON Format

## Structure Diagram

See [i2c-read-write-schema.json](i2c-read-write-schema.json) for the
complete JSON structure and validation rules.

# Examples

## Example 1 - Write and Read the same device

This example performs a write-read verification on the same FT24C32 EEPROM.
It writes `0x11 0x22 0x33 0x44` to register address `0x0000` on bus `10`
(`chip_address` `0x50`), waits `5 ms`, then reads back `4` bytes from the
same register and compares the result with `expected_output`.

### JSON definition
```json
{
  "FT24C32 EEPROM Basic Write-Read": {
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
}
```

## Example 2 - Read and Write the different devices

This example demonstrates cross-device data transfer across different I2C
buses. It first reads dynamic data from an SHT30 sensor on bus `10`
(`chip_address` `0x44`) and stores the result in `sensor_temp`. It then
writes that stored value to an OLED device on bus `1` (`chip_address`
`0x3C`) by using `data_from_variable`, which shows how one step can consume
data produced by a previous step.

### JSON definition

```json
{
  "Cross-Bus Sensor to Display Bridge": {
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
}
```