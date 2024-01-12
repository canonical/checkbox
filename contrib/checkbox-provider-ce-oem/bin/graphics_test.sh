#!/bin/bash

is_ubuntu_frame_active() {
    if pgrep -if "ubuntu-frame" > /dev/null; then
        echo "The ubuntu-frame is active"
        echo
        return 0
    else
        echo "ubuntu-frame is not active"
        echo
        return 1
    fi
}

test_ubuntu_frame_launching() {
    if is_ubuntu_frame_active; then
        echo "No need to bring it up again"
        echo "journal log of ubuntu frame:"
        journalctl -b 0 -g "ubuntu-frame"
    else
        echo "Activating ubuntu-frame now..."
        echo
        # Expecting exit code 124 from the 'timeout' command
        # Capture any exit codes other than 0 and 124; return exit code 1 in such cases
        timeout 20s ubuntu-frame || ( [[ $? -eq 124 ]] && \
        echo -e "\nPASS: Timeout reached without any failures detected." )
    fi
}

test_glmark2_es2_wayland() {
    CMD="env XDG_RUNTIME_DIR=/run/user/0 graphics-test-tools.glmark2-es2-wayland"
    OUTPUT=""
    EXIT=0
    if is_ubuntu_frame_active; then
        echo "Running glmark2-es2-wayland benchmark..."
        echo
        OUTPUT=$($CMD)
    else
        echo "Activating ubuntu-frame now..."
        echo
        ubuntu-frame &
        FRAME_PID=$!
        sleep 10     # Sleep a while to make sure ubuntu-frame can be brought up before glamrk2-es2-wayland
        echo "Running glmark2-es2-wayland benchmark..."
        echo
        OUTPUT=$($CMD)
        kill "$FRAME_PID"
    fi

    echo "$OUTPUT"
    if [ -z "$GL_VENDOR" ] || [ -z "$GL_RENDERER" ];then
        echo "FAIL: 'GL_VENDOR' or 'GL_RENDERER' is empty. Please set them in config file!"
        exit 1
    fi
    if ! echo "$OUTPUT" | grep "GL_VENDOR" | grep -q "$GL_VENDOR"; then
        echo "FAIL: Wrong vendor!"
        echo "The expected 'GL_VENDOR' should include '$GL_VENDOR'!"
        EXIT=1
    else
        echo "PASS: GL_VENDOR is '$GL_VENDOR'"
    fi
    if ! echo "$OUTPUT" | grep "GL_RENDERER" | grep -q "$GL_RENDERER"; then
        echo "FAIL: Wrong renderer!"
        echo "The expected 'GL_RENDERER' should include '$GL_RENDERER'"
        EXIT=1
    else
        echo "PASS: GL_RENDERER is '$GL_RENDERER'"
    fi
    exit $EXIT
}

help_function() {
    echo "This script is used for graphics test cases"
    echo "Usage: graphics_test.sh <test_case>"
    echo
    echo "Test cases currently implemented:"
    echo -e "\t<frame>: test_ubuntu_frame_launching"
    echo -e "\t<glmark2>: test_glmark2_es2_wayland"
}

main(){
    case ${1} in
        frame) test_ubuntu_frame_launching ;;
        glmark2) test_glmark2_es2_wayland ;;
        *) help_function ;;
    esac
}

main "$@"
