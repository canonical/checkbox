
## <a id='top'>environ keys for spi tests</a>

- SPI_DEVICE_COUNT
    - Affected Test Cases:
        - [ce-oem-spi/detect](#ce-oem-spi/detect)

## Detailed test cases contains environ variable
### <a id='ce-oem-spi/detect'>ce-oem-spi/detect</a>
- **summary:**
To detect if the spi device exist

- **description:**
```
PURPOSE:
Check if the SPI devices exist
```

- **file:**
[source file](jobs.pxu#L1)

- **environ:**
SPI_DEVICE_COUNT

- **command:**
```
spidev_test.py -d "${SPI_DEVICE_COUNT:-1}"
```
[Back to top](#top)
