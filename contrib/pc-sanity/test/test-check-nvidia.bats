#!/usr/bin/env bats

# execute this test file by `bats test/test-check-nvidia.bats`
BIN_FOLDER="bin"

function setup() {
    # shellcheck source=/dev/null
    source "$BIN_FOLDER"/check-nvidia.sh
}

@test "recognize current mode" {
    set -e
    function prime-select() {
        echo "$current_mode"
    }
    function check_ondemand_mode() {
        return "$on_demand_mode"
    }
    function check_nvidia_mode() {
        return "$nvidia_mode"
    }
    function check_intel_mode() {
        return "$intel_mode"
    }
    on_demand_mode=1
    nvidia_mode=2
    intel_mode=3

    echo "testing recognizing on-demand mode"
    current_mode="on-demand"
    run check_behavior_of_current_mode
    [ "$status" -eq $on_demand_mode ]
    echo "testing recognizing nvidia mode"
    current_mode="nvidia"
    run check_behavior_of_current_mode
    [ "$status" -eq $nvidia_mode ]
    echo "testing recognizing intel mode"
    current_mode="intel"
    run check_behavior_of_current_mode
    [ "$status" -eq $intel_mode ]

}

@test "Check renderer when OpenGL renderer string: Mesa Intel(R)" {
    set -e
    glxinfo_string=$'OpenGL vendor string: Intel\nOpenGL renderer string: Mesa Intel(R)'
    function glxinfo() {
        echo "$glxinfo_string"
    }
    echo run check_renderer intel
    run check_renderer intel
    [ "$status" -eq 0 ]

    echo run check_renderer on-demand-nvidia
    run check_renderer on-demand-nvidia
    [ "$status" -eq 1 ]
    echo run check_renderer on-nvidia
    run check_renderer nvidia
    [ "$status" -eq 1 ]

    function is_nv_bootvga() {
        echo "1"
    }
    echo run check_renderer on-demand-default
    run check_renderer on-demand-default
    [ "$status" -eq 1 ]

    function is_nv_bootvga() {
        echo "0"
    }
    echo run check_renderer on-demand-default
    run check_renderer on-demand-default
    [ "$status" -eq 0 ]
}

@test "Check renderer when OpenGL renderer string: GeForce GTX" {
    set -e
    glxinfo_string=$'OpenGL vendor string: NVIDIA Corporation\nOpenGL renderer string: GeForce GTX'
    function glxinfo() {
        echo "$glxinfo_string"
    }
    echo run check_renderer intel
    run check_renderer intel
    [ "$status" -eq 1 ]

    echo run check_renderer on-demand-nvidia
    run check_renderer on-demand-nvidia
    [ "$status" -eq 0 ]
    echo run check_renderer on-nvidia
    run check_renderer nvidia
    [ "$status" -eq 0 ]

    function is_nv_bootvga() {
        echo "1"
    }
    echo run check_renderer on-demand-default
    run check_renderer on-demand-default
    [ "$status" -eq 0 ]

    function is_nv_bootvga() {
        echo "0"
    }
    echo run check_renderer on-demand-default
    run check_renderer on-demand-default
    [ "$status" -eq 1 ]
}
@test "Check renderer when OpenGL renderer string: llvmpipe (LLVM 10.0.0, 256 bits)" {
    set -e
    glxinfo_string=$'OpenGL vendor string: Mesa/X.org\nOpenGL renderer string: llvmpipe (LLVM 10.0.0, 256 bits)'
    function glxinfo() {
        echo "$glxinfo_string"
    }
    echo run check_renderer intel
    run check_renderer intel
    [ "$status" -eq 1 ]

    echo run check_renderer on-demand-default
    run check_renderer on-demand-default
    [ "$status" -eq 0 ]

    echo run check_renderer on-demand-nvidia
    run check_renderer on-demand-nvidia
    [ "$status" -eq 1 ]
    echo run check_renderer on-nvidia
    run check_renderer nvidia
    [ "$status" -eq 1 ]
}

@test "Check Nvidia sleep in on-demand and Intel mode" {
    set -e
    OUTPUT_FOLDER="$(mktemp -d)"

    function get_nvidia_runtime_status() {
        echo "$state"
    }

    # the string will show by checkbox process
    state="active"

    echo "When Nvidia is active, then it should be failed."
    run check_nvidia_sleep
    [ "$status" -eq 1 ]
    echo "When Nvidia is suspended, it should be pass."
    state="suspended"
    run check_nvidia_sleep
    [ "$status" -eq 0 ]
}

