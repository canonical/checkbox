# This file is part of Checkbox.
#
# Copyright 2012-2014 Canonical Ltd.
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

"""
:mod:`plainbox.impl.commands.inv_special` -- special sub-command
================================================================
"""
from logging import getLogger

from plainbox.impl.commands.inv_checkbox import CheckBoxInvocationMixIn


logger = getLogger("plainbox.commands.special")


class SpecialInvocation(CheckBoxInvocationMixIn):

    def __init__(self, provider_loader, config_loader, ns):
        super().__init__(provider_loader, config_loader)
        self.ns = ns

    def run(self):
        ns = self.ns
        job_list = self.get_job_list(ns)
        # Now either do a special action or run the jobs
        if ns.special == "list-jobs":
            self._print_job_list(ns, job_list)
        elif ns.special == "list-job-hashes":
            self._print_job_hash_list(ns, job_list)
        elif ns.special == "list-expr":
            self._print_expression_list(ns, job_list)
        elif ns.special == "dep-graph":
            self._print_dot_graph(ns, job_list)
        # Always succeed
        return 0

    def _get_matching_job_list(self, ns, job_list):
        matching_job_list = super(
            SpecialInvocation, self)._get_matching_job_list(ns, job_list)
        # As a special exception, when ns.special is set and we're either
        # listing jobs or job dependencies then when no run pattern was
        # specified just operate on the whole set. The ns.special check
        # prevents people starting plainbox from accidentally running _all_
        # jobs without prompting.
        if ns.special is not None and not ns.include_pattern_list:
            matching_job_list = job_list
        return matching_job_list

    def _print_job_list(self, ns, job_list):
        matching_job_list = self._get_matching_job_list(ns, job_list)
        for job in matching_job_list:
            print("{}".format(job.id))

    def _print_job_hash_list(self, ns, job_list):
        matching_job_list = self._get_matching_job_list(ns, job_list)
        for job in matching_job_list:
            print("{} {}".format(job.checksum, job.id))

    def _print_expression_list(self, ns, job_list):
        matching_job_list = self._get_matching_job_list(ns, job_list)
        expressions = set()
        for job in matching_job_list:
            prog = job.get_resource_program()
            if prog is not None:
                for expression in prog.expression_list:
                    expressions.add(expression.text)
        for expression in sorted(expressions):
            print(expression)

    def _print_dot_graph(self, ns, job_list):
        matching_job_list = self._get_matching_job_list(ns, job_list)
        print('digraph dependency_graph {')
        print('\tnode [shape=box];')
        for job in matching_job_list:
            if job.plugin == "resource":
                print('\t"{}" [shape=ellipse,color=blue];'.format(job.id))
            elif job.plugin == "attachment":
                print('\t"{}" [color=green];'.format(job.id))
            elif job.plugin == "local":
                print('\t"{}" [shape=invtriangle,color=red];'.format(
                    job.id))
            elif job.plugin == "shell":
                print('\t"{}" [];'.format(job.id))
            elif job.plugin in ("manual", "user-verify", "user-interact"):
                print('\t"{}" [color=orange];'.format(job.id))
            for dep_id in job.get_direct_dependencies():
                print('\t"{}" -> "{}";'.format(job.id, dep_id))
            prog = job.get_resource_program()
            if ns.dot_resources and prog is not None:
                for expression in prog.expression_list:
                    print('\t"{}" [shape=ellipse,color=blue];'.format(
                        expression.resource_id))
                    print('\t"{}" -> "{}" [style=dashed, label="{}"];'.format(
                        job.id, expression.resource_id,
                        expression.text.replace('"', "'")))
        print("}")
