# This file is part of Checkbox.
#
# Copyright 2015 Canonical Ltd.
# Written by:
#   Zygmunt Krynicki <zygmunt.krynicki@canonical.com>
#
# Checkbox is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3,
# as published by the Free Software Foundation.
#
# Checkbox is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Checkbox.  If not, see <http://www.gnu.org/licenses/>.

VERSION:=$(shell python3 setup.py --version)

.PHONY: all
all: dist/plainbox_$(VERSION)_all.snap

.PHONY: clean
clean:
	rm -rf build/snappy/
	rm -f dist/plainbox*.snap
	rm -rf build/venv-pex

dist/plainbox_$(VERSION)_all.snap: build/snappy/plainbox.pex build/snappy/meta/package.yaml build/snappy/meta/readme.md | dist
	cd build/snappy && snappy build -o ../../dist/

define package_yaml
name: plainbox
version: $(VERSION)
vendor: Zygmunt Krynicki <zygmunt.krynicki@canonical.com>
architectures: ["all"]
source: http://launchpad.net/checkbox/
security-template: unconfined
type: app
binaries:
 - name: plainbox
   exec: plainbox.pex
   description: "The main plainbox executable"
endef

export package_yaml
build/snappy/meta/package.yaml: setup.py | build/snappy/meta
	echo "$$package_yaml" > $@

build/snappy/meta/readme.md: setup.py | build/snappy/meta
	./$^ --description > $@

dist build/snappy/meta: %:
	mkdir -p $@

build/snappy/plainbox.pex:
	virtualenv -p python3 build/venv-pex
	. build/venv-pex/bin/activate; pip install wheel pex
	. build/venv-pex/bin/activate; pex --python=python3 -r pex-requirements.txt -o $@ -m plainbox.public:main
	rm -rf build/venv-pex
