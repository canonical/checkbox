
## <a id='top'>environ keys for otg tests</a>

- OTG
    - Affected Test Cases:
        - [otg_ports](#otg_ports)

## Detailed test cases contains environ variable
### <a id='otg_ports'>otg_ports</a>
- **summary:**
Gather list of USB ports and UDC.

- **description:**
```
A USB port and UDC mapping resource that relies on the user specifying in config varirable.
Usage of parameter: OTG={port1}:{node1} {port2}:{node2} ...
e.g. OTG=USB-C1:11200000 USB-Micro:112a1000
```

- **file:**
[source file](jobs.pxu#L1)

- **environ:**
OTG

- **command:**
```
if [ "$OTG" ]; then
    multiple-otg.sh -c "$OTG"
else
    echo "OTG config variable: not found"
fi
```
[Back to top](#top)
