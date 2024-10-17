#!/usr/bin/env sh
cp "$PLAINBOX_PROVIDER_DATA/matrixMul_kernel64.fatbin" .
matrixMulDrv
rm -f matrixMul_kernel64.fatbin
