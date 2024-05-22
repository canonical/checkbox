# This helps older pip version properly install editable version of checkbox
# inside the venv with `pip install -e .`

import os
from setuptools import setup

# this version adoption is a no-op in non-debian build as setuptools-scm does
# the same. Some pybuild versions are not triggering this behaviour correctly
# so this makes it uniform. Note that if this variable is missing the fallback
# to setuptools-scm is unchanged also in debian packages (so the package will
# get the default version calculated from setuptools-scm)
setup(version=os.getenv("SETUPTOOLS_SCM_PRETEND_VERSION"))
