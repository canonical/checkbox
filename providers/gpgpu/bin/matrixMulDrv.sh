#!/usr/bin/env sh
cp -r "$PLAINBOX_PROVIDER_DATA/matrixMulDrv" ./data
matrixMulDrv
rm -r ./data
