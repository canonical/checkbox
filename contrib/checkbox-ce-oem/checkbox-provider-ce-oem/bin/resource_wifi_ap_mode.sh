#!/usr/bin/env bash

# We will generate a default set of WIFI_AP_MODE to test both a and bg
# band in open and wpa-psk with the first avaliable interface
# if WIFI_AP_MODE has not been set.
if [ -z "$WIFI_AP_MODE" ]; then
  interface=$(iw dev | grep Interface | awk 'NR==1{print $2 }')
  if [ -n "$interface" ]; then
    WIFI_AP_MODE="$interface:a:36:none:none $interface:bg:5:none:none $interface:a:36:wpa-psk:ccmp $interface:bg:5:wpa-psk:ccmp"
  fi
fi
awk '{
    split($0, record, " ")
    for (i in record) {
        split(record[i], data, ":")
        printf "interface: %s\nband: %s\nchannel: %s\nkey_mgmt: %s\ngroup: %s\n\n", data[1], data[2], data[3], data[4], data[5]
    }
}' <<< "$WIFI_AP_MODE"
