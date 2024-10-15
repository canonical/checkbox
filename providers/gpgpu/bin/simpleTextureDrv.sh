#!/usr/bin/env sh
cp "$PLAINBOX_PROVIDER_DATA/simpleTexture_kernel64.fatbin" .
cp "$PLAINBOX_PROVIDER_DATA/ref_rotated.pgm" .
cp "$PLAINBOX_PROVIDER_DATA/teapot512.pgm" .
cp "$PLAINBOX_PROVIDER_DATA/teapot512_out.pgm" .
simpleTextureDrv
rm -f simpleTexture_kernel64.fatbin ref_rotated.pgm teapot512.pgm teapot512_out.pgm
