# This makefile can be used to create a snapcraft.yaml
# from the provided template, customizing it for the
# target snap base: e.g. run `make SNAPBASE=core24` to
# create a snapcraft.yaml based on core24.
#
# SNAPBASE is the only required input, other variables
# are obtained dynamically from the base.

SNAP_VERSION = 0.4.0

SNAP_OUTPUT = snapcraft.yaml
SNAP_WORK_FOLDER = build
SNAP_TEMPLATE = snap/snapcraft.yaml.in

ifndef SNAPBASE
$(error SNAPBASE is not set)
endif

PYTHONVER := $(shell \
    if [ "$(SNAPBASE)" = "core" ]; then \
        echo "python3.5"; \
    elif [ "$(SNAPBASE)" = "core18" ]; then \
        echo "python3.6"; \
    elif [ "$(SNAPBASE)" = "core20" ]; then \
        echo "python3.8"; \
    elif [ "$(SNAPBASE)" = "core22" ]; then \
        echo "python3.10"; \
    elif [ "$(SNAPBASE)" = "core24" ]; then \
        echo "python3.12"; \
    else \
        echo ""; \
    fi \
)

ifndef PYTHONVER
$(error SNAPBASE is not valid: pick between core, core18, core20, core22, or core24)
endif

CHECKBOX_RUNTIME := $(shell \
    if [ "$(SNAPBASE)" = "core" ]; then \
        echo "checkbox16"; \
    elif [ "$(SNAPBASE)" = "core18" ]; then \
        echo "checkbox18"; \
    elif [ "$(SNAPBASE)" = "core20" ]; then \
        echo "checkbox20"; \
    elif [ "$(SNAPBASE)" = "core22" ]; then \
        echo "checkbox22"; \
    elif [ "$(SNAPBASE)" = "core24" ]; then \
        echo "checkbox24"; \
    else \
        echo ""; \
    fi \
)

export SNAPBASE
export SNAP_VERSION
export PYTHONVER
export CHECKBOX_RUNTIME

$(SNAP_OUTPUT): $(SNAP_TEMPLATE)
	mkdir -p $(SNAP_WORK_FOLDER)/snap
	rsync -r --links ../checkbox-provider-oem/* $(SNAP_WORK_FOLDER)/
	envsubst '$$CHECKBOX_RUNTIME $$SNAPBASE $$SNAP_VERSION $$PYTHONVER' < $< > $(SNAP_WORK_FOLDER)/snap/$@

all: $(SNAP_OUTPUT)

clean:
	rm -rf $(SNAP_WORK_FOLDER)

.PHONY: clean $(SNAP_OUTPUT)
