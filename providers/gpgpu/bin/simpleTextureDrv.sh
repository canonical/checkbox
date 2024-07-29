#!/usr/bin/env sh
cp "$PLAINBOX_PROVIDER_DATA/simpleTexture_kernel64.fatbin" .
cp "$PLAINBOX_PROVIDER_DATA/teapot512.pgm" .
cp "$PLAINBOX_PROVIDER_DATA/ref_rotated.pgm" .
simpleTextureDrv
