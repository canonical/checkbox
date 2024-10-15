#!/usr/bin/env sh
cp -r "$PLAINBOX_PROVIDER_DATA/vectorAdd_kernel64.fatbin" .
vectorAddDrv
rm -f vectorAdd_kernel64.fatbin
