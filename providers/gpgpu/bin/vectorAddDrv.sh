#!/usr/bin/env sh
cp -r "$PLAINBOX_PROVIDER_DATA/vectorAddDrv" ./data
vectorAddDrv
rm -r ./data
