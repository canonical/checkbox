.PHONY: help test validate develop run clean all

help:
	@echo "Targets:"
	@echo "  make test     - Run unit tests (./manage.py test)"
	@echo "  make validate - Validate PXU syntax (./manage.py validate)"
	@echo "  make develop  - Register provider for local development"
	@echo "  make test     - Run unit tests (./manage.py test)"
	@echo "  make validate - Validate PXU syntax (./manage.py validate)"
	@echo "  make develop  - Register provider for local development"
	@echo "  make run      - Full end-to-end: validate + test + develop + run all codec tests"
	@echo "  make all      - Run unit tests and full end-to-end tests"
	@echo ""
	@echo "Single command to run everything: make run"

test:
	./manage.py test

validate:
	./manage.py validate

develop:
	./manage.py develop

clean:
	-rm -f /var/tmp/checkbox-providers-develop/checkbox-provider-multimedia.provider

run: validate test clean develop
	@echo ""
	@echo "=== Running all VA-API codec conformance tests (decode + encode) ==="
	@echo "Platform will be auto-detected (set PLATFORM_CONFIG for manual config)"
	@echo ""
	checkbox-cli run com.canonical.contrib::multimedia-codecs-vaapi
	@echo ""
	@echo "=== Running VA-API encoder-only tests ==="
	checkbox-cli run com.canonical.contrib::multimedia-codecs-vaapi-encode

all: test run
