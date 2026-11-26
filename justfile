set positional-arguments

venv := justfile_directory() + "/.venv"
provider_path := venv + "/share/checkbox-providers"
providers := "providers/base providers/certification-client providers/certification-server providers/docker providers/genio providers/gpgpu providers/iiotg providers/resource providers/sru providers/tpm2 providers/tutorial metabox/metabox/metabox-provider"

[doc('List available recipes')]
default:
    @just --list

[doc('Sets up the full development environment')]
setup:
    #!/usr/bin/env bash
    set -euo pipefail

    if ! python3 -c "import venv, ensurepip" 2>/dev/null; then
        echo "Error: Python venv module is not available." >&2
        echo "Install it with: sudo apt install python3-venv" >&2
        exit 1
    fi

    if [ ! -d "{{venv}}" ]; then
        python3 -m venv "{{venv}}"
    fi

    "{{venv}}/bin/pip" install -e ./checkbox-ng -e ./checkbox-support -e ./metabox

    mkdir -p "{{provider_path}}"

    if ! grep -qF "PROVIDERPATH=" "{{venv}}/bin/activate"; then
        echo "export PROVIDERPATH={{provider_path}}" >> "{{venv}}/bin/activate"
    fi
    if [ -f "{{venv}}/bin/activate.fish" ] && ! grep -qF "PROVIDERPATH " "{{venv}}/bin/activate.fish"; then
        echo "set -gx PROVIDERPATH {{provider_path}}" >> "{{venv}}/bin/activate.fish"
    fi

    for provider in {{providers}}; do
        "{{venv}}/bin/python" "$provider/manage.py" build
        PROVIDERPATH="{{provider_path}}" "{{venv}}/bin/python" \
            "$provider/manage.py" develop -f -d "{{provider_path}}"
    done

    git config blame.ignoreRevsFile .git-blame-ignore-revs

    echo "Setup complete. Activate the venv with:"
    set +u
    if [ -n "$FISH_VERSION" ]; then
        echo "  source {{venv}}/bin/activate.fish"
    else
        echo "  source {{venv}}/bin/activate"
    fi

[doc('Refresh the development environment')]
refresh: setup

[doc('Run the Checkbox remote agent as root using the local .venv')]
run-agent *args:
    #!/usr/bin/env bash
    set -euo pipefail

    if [ ! -x "{{venv}}/bin/checkbox-cli" ]; then
        echo "Error: checkbox-cli is not installed in {{venv}}." >&2
        echo "Run 'just setup' first." >&2
        exit 1
    fi

    exec sudo env \
        PROVIDERPATH="{{provider_path}}" \
        PATH="{{venv}}/bin:$PATH" \
        "{{venv}}/bin/checkbox-cli" run-agent "$@"
