#!/bin/bash

session=$(loginctl | grep seat0 | awk '$3!="gdm" {print $1}')
if [ -z "$session" ];then
    echo "Can't get valid session"
    exit 1
fi
if lspci | grep -q NVIDIA;then
    expect=x11
else
    expect=wayland
fi
current=$(loginctl show-session "$session" -P Type --value)
if [ "$current" != "$expect" ];then
    echo Session type is "$current", expected type is "$expect"
    exit 1
fi
