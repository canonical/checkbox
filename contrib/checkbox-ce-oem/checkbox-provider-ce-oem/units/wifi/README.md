# This is a file introducing WiFi AP mode test jobs.
To perform WiFi AP mode test, you will need following environment:
>Both DUT and HOST with Netwrok-Manager installed and wireless interface is managed by Network-Manager\
And must have network connection between DUT and HOST via ethernet port, since we are intend to test wireless.

## id: ce_oem_wifi_ap_mode
  This resource job requires the checkbox environment variable `WIFI_AP_MODE`.
  It defines which WiFi AP mode should be test includes different wireless interface,
  band, key_mgmt, group and password.\
  Usage of parameter:\
  WIFI_AP_MODE={interface_name}:{band in a|bg}:{channel}:{key_mgmt}:{group in one of ciphers wep40|wep104|tkip|ccmp}
>WIFI_AP_MODE=wlan0:a:44:wpa-psk:ccmp wlan0:bg:5:none:none

Above config defined two different AP mode that intend to test.
The following will break down first part of the config.\
>wlan0:a:44:wpa-psk:ccmp:insecure
>>wlan0: The interface name to use\
  a: The band to use\
  44: The channel to use\
  wpa-psk: The key_magmt to use\
  ccmp: The cipher group to use

>waln0:bg:5:none:none
>>wlan0: The interface name to use\
  bg: The band to use\
  5: The channel to use\
  none: Setup as open AP\
  none: No need cipher group for a open AP

>Note: Netwrok Manager support only band A and BG. Please refer to follows for more detail.
 https://networkmanager.dev/docs/api/latest/settings-802-11-wireless.html
 https://networkmanager.dev/docs/api/latest/settings-802-11-wireless-security.html

## id: ce-oem-wireless/ap_open_{band}_ch{channel}_{group}_{interface}_manual
A template job for open AP mode manual test. It will depend on resource job `ce_oem_wifi_ap_mode` to generate the related jobs.\
In this job. It will setup the target AP mode on DUT, and tester need to connect to
the ssid `qa-test-ssid` and ping the DUT default IP address `10.42.0.1` on a HOST machine.

## id: ce-oem-wireless/ap_wpa_{key_mgmt}_{band}_ch{channel}_{group}_{interface}_manual
A template job for WPA AP mode manual test. It will depend on resource job `ce_oem_wifi_ap_mode` to generate the related jobs.\
In this job. It will setup the target AP mode on DUT, and tester need to connect to
the ssid `qa-test-ssid` with password `insecure`, and ping the DUT default IP address
`10.42.0.1` on a HOST machine.

## id: ce-oem-wireless/ap_open_{band}_ch{channel}_{group}_{interface}_automated
A template job for open AP mode automated test. It will depend on resource job `ce_oem_wifi_ap_mode` to generate the related jobs.\
This job requires the checkbox environment variables `WIFI_AP_HOST_DEVICE_IP` `WIFI_AP_HOST_DEVICE_USER` `WIFI_AP_HOST_DEVICE_PWD` to allow auto login to HOST machine
and perform connecting AP and ping DUT automaticlly by using `sshpass` command.

## id: ce-oem-wireless/ap_wpa_{key_mgmt}_{band}_ch{channel}_{group}_{interface}_automated
A template job for WPA AP mode automated test. It will depend on resource job `ce_oem_wifi_ap_mode` to generate the related jobs.\
This job requires the checkbox environment variables `WIFI_AP_HOST_DEVICE_IP` `WIFI_AP_HOST_DEVICE_USER` `WIFI_AP_HOST_DEVICE_PWD` to allow auto login to HOST machine
and perform connecting AP and ping DUT automaticlly by using `sshpass` command.
