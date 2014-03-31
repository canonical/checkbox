import glob
import shlex
import os

from plainbox.abc import IBuildSystem
from plainbox.impl.secure.plugins import PkgResourcesPlugInCollection


# python3.2 doesn't have shlex.quote
# so let's use the bundled copy here
if not hasattr(shlex, 'quote'):
    from ._shlex import quote
    shlex.quote = quote


class MakefileBuildSystem(IBuildSystem):
    """
    A build system for projects using classic makefiles
    """

    def probe(self, src_dir: str) -> float:
        # If a configure script exists (autotools?) then let's not pretend we
        # do the whole thing and bail out. It's better to let test authors to
        # customize everything.
        if os.path.isfile(os.path.join(src_dir, "configure")):
            return 0
        if os.path.isfile(os.path.join(src_dir, "Makefile")):
            return 90
        return 0

    def get_build_command(self, src_dir: str, build_dir: str) -> str:
        return "VPATH={} make -f {}".format(
            shlex.quote(os.path.relpath(src_dir, build_dir)),
            shlex.quote(os.path.relpath(
                os.path.join(src_dir, 'Makefile'), build_dir)))


class GoBuildSystem(IBuildSystem):
    """
    A build system for projects written in go
    """

    def probe(self, src_dir: str) -> float:
        if glob.glob("{}/*.go".format(src_dir)) != []:
            return 50
        return 0

    def get_build_command(self, src_dir: str, build_dir: str) -> str:
        return "go build {}/*.go".format(os.path.relpath(src_dir, build_dir))


# Collection of all buildsystems
all_buildsystems = PkgResourcesPlugInCollection('plainbox.buildsystem')
