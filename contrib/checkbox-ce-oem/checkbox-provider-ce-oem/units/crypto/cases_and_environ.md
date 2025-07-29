
## <a id='top'>environ keys for crypto tests</a>

- HWRNG
    - Affected Test Cases:
        - [ce-oem-crypto/hwrng-current](#ce-oem-crypto/hwrng-current)

## Detailed test cases contains environ variable
### <a id='ce-oem-crypto/hwrng-current'>ce-oem-crypto/hwrng-current</a>
- **summary:**
Check if current Hardware Random Number Generate is expected.

- **description:**
```
None
```

- **file:**
[source file](accelerator.pxu#L1)

- **environ:**
HWRNG

- **command:**
```
path_hwrng='/sys/class/misc/hw_random/'
if [ -e "$path_hwrng/rng_available" ]; then
    echo "HWRNG_Available: $(cat "$path_hwrng"rng_available)"
fi
if [ -e "$path_hwrng/rng_current" ]; then
    echo "HWRNG_Current: $(cat "$path_hwrng"rng_current)"
fi
if [ -e "$path_hwrng/rng_qulity" ]; then
    echo "HWRNG_Quality: $(cat "$path_hwrng"rng_qulity)"
fi
if [ -e "$path_hwrng/rng_selected" ]; then
    echo "HWRNG_Selected: $(cat "$path_hwrng"rng_selected)"
fi
if [ -z "$HWRNG" ];then
    echo "FAIL: Checkbox config HWRNG has not been set!"
    exit 1
elif [ "$HWRNG" == "$(cat "$path_hwrng"rng_current)" ];then
    echo "PASS: $HWRNG is available"
    exit 0
else
    echo "FAIL: $HWRNG is not available"
    exit 1
fi
```
[Back to top](#top)
