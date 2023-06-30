#!/bin/bash

echo "Default output device:"
wpctl inspect @DEFAULT_AUDIO_SINK@ | grep "node.description" | cut -d '=' -f 2
echo "Default input device:"
wpctl inspect @DEFAULT_AUDIO_SOURCE@ | grep "node.description" | cut -d '=' -f 2
echo "If these are not you would like to test, please change them before testing"
