# Copyright (C) 2022 Canonical Ltd.
#
# Authors:
#   Maciej Kisielewski <maciej.kisielewski@canonical.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3,
# as published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""
An extended ArgParser that automatically creates subparsers.
"""

import argparse
import inspect
import re

def _parse_docstring(doc):
    # those are the defaults
    param_descs = {}
    return_desc = ''
    info = ''
    if not doc:
        return info, param_descs, return_desc
    lines = doc.strip().splitlines()
    # let's extract the text preceeding param specification
    # the first line that explains a param or a return value
    # means the end of general info
    info_lines = []
    for lineno, line in enumerate(lines):
        if line.startswith((':param', ':return')):
            # we're at the param description section
            # let's delete what we already read
            lines = lines[lineno:]
            break
        info_lines.append(line)
    info = '\n'.join(info_lines)
    # the rest of lines should now contain information about params or the 
    # return value
    param_re = re.compile(
        r":param(\s[A-Za-z_][A-Za-z0-9_]*)?\s([A-Za-z_][A-Za-z0-9_]*):(.*)")
    return_re = re.compile(
        r":returns(\s[A-Za-z_][A-Za-z0-9_]*)?:(.*)")
    for line in lines:
        param_match = param_re.match(line)
        if param_match:
            param_type, param_name, description = param_match.groups()
            param_type = {
                'str': str, 'int': int, 'float': float, 'bool': bool
            }.get(param_type.strip() if param_type else None)
            param_descs[param_name] = param_type, description.strip()
            continue
        return_match = return_re.match(line)
        if return_match:
            return_desc = return_match.groups()[1].strip()
    return info, param_descs, return_desc

class AutoArgParser(argparse.ArgumentParser):
    def __init__(self, *args, cls=None, **kwargs):
        if cls is None:
            super().__init__(*args, **kwargs)
            return
        self._cls = cls
        self._auto_args = []
        self._args_already_parsed = False
        cls_doc = (inspect.getdoc(cls) or '').strip()
        super().__init__(*args, description=cls_doc, **kwargs)
        subparsers = self.add_subparsers(dest='method')
        methods = inspect.getmembers(cls, inspect.isroutine)
        for name, method in methods:
            if name.startswith('__'):
                continue
            doc = inspect.getdoc(method)
            argspec = inspect.getfullargspec(method)
            args = argspec.args
            # if the function is a classmethod or instance method, let's pop
            # the first arg (the bound object)
            if args and args[0] in ['self', 'cls']:
                args = args[1:]
            info, params, return_desc = _parse_docstring(doc)
            sub = subparsers.add_parser(method.__name__, help=info)
            for arg in args:
                self._auto_args.append(arg)
                type, help = params.get(arg, (None, None))
                sub.add_argument(arg, type=type, help=help)

    def parse_args(self, *args, **kwargs):
        args = super().parse_args(*args, **kwargs)
        self._args_already_parsed = True
        self._picked_method = args.method
        # turn members of the args namespace into a normal dictionary so it's
        # easier later on to use them as kwargs. But let's take only the one
        # automatically generated.
        self._method_args = {
            a: v for a, v in vars(args).items() if a in self._auto_args}
        return args


    def run(self, obj=None):
        if not self._args_already_parsed:
            self.parse_args()
        if obj is None:
            obj = self._cls()
        if not self._picked_method:
            raise SystemExit(
                "No sub-command chosen!\n\n{}".format(self.format_help()))
            print("No subcommand chosen")
        return getattr(obj, self._picked_method)(**self._method_args)
