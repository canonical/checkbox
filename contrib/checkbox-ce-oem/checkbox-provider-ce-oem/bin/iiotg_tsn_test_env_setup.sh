#!/bin/bash

interface=$1

echo "## Disabling EEE status to prevent the network adapter from entering EEE mode..."
ethtool --set-eee "$interface" eee off
echo "## Displaying EEE status..."
ethtool --show-eee "$interface"

echo "## Disabling pause options to prevent from traffic interruption..."
ethtool -A "$interface" autoneg off rx off tx off

echo "## Disabling NTP clock sync to prevent interrupt with clock sync between boards..."
timedatectl set-ntp 0
