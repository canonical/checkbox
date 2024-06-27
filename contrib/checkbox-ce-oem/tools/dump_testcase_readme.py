#!/usr/bin/env python3
import os
import copy
import json
import yaml
import jinja2
import argparse
from collections import OrderedDict

from plainbox.impl.highlevel import Explorer, PlainBoxObject
from plainbox.impl.session.assistant import SessionAssistant


DEFAULT_TP_MAPPING = {
    "include_jobs": "include",
    "exclude_jobs": "exclude",
    "nested_plan": "nested_part",
    "file": "origin",
}
DEFAULT_JOB_MAPPING = {
    "unit_type": "unit",
    "summary": "summary",
    "description": "description",
    "require": "requires",
    "depends": "depends",
    "type": "plugin",
    "command": "command",
    "file": "origin",
    "environ": "environ",
}
TEMPLATE_JOB_MAPPING = {
    "template_resource": "template_resource",
    "template_summary": "template_summary",
    "template_filter": "template_filter",
    "summary": "raw_summary",
    "description": "template_description",
    "require": "requires",
    "depends": "depends",
    "type": "plugin",
    "command": "command",
    "file": "origin",
    "environ": "environ",
}


class ExplorerMore(Explorer):

    def _job_to_obj(self, unit):
        return PlainBoxObject(
            unit,
            group=unit.Meta.name,
            name=unit.id,
            attrs=OrderedDict(
                (
                    (
                        "broken_i18n",
                        unit.summary == unit.tr_summary()
                        or unit.description == unit.tr_description(),
                    ),
                    ("id", unit.id),
                    ("partial_id", unit.partial_id),
                    ("summary", unit.summary),
                    ("tr_summary", unit.tr_summary()),
                    ("raw_summary", unit.get_raw_record_value("summary")),
                    ("description", unit.description),
                    (
                        "raw_description",
                        unit.get_raw_record_value("description"),
                    ),
                    ("tr_description", unit.tr_description()),
                    ("plugin", unit.plugin),
                    ("command", unit.command),
                    ("user", unit.user),
                    ("environ", unit.environ),
                    ("estimated_duration", unit.estimated_duration),
                    ("depends", unit.depends),
                    ("requires", unit.requires),
                    ("origin", str(unit.origin)),
                    ("flags", unit.flags),
                )
            ),
        )

    def _test_plan_to_obj(self, unit):
        return PlainBoxObject(
            unit,
            group=unit.Meta.name,
            name=unit.id,
            attrs=OrderedDict(
                (
                    (
                        "broken_i18n",
                        unit.name == unit.tr_name()
                        or unit.description == unit.tr_description(),
                    ),
                    ("id", unit.id),
                    ("include", unit.include),
                    ("exclude", unit.exclude),
                    ("name", unit.name),
                    ("tr_name", unit.tr_name()),
                    ("description", unit.description),
                    ("tr_description", unit.tr_description()),
                    ("estimated_duration", unit.estimated_duration),
                    ("icon", unit.icon),
                    ("category_overrides", unit.category_overrides),
                    ("virtual", unit.virtual),
                    ("nested_part", unit.nested_part),
                    ("origin", str(unit.origin)),
                )
            ),
        )

    def _template_to_obj(self, unit):
        return PlainBoxObject(
            unit,
            group=unit.Meta.name,
            name=unit.template_id,
            attrs=OrderedDict(
                (
                    ("id", unit.id),
                    ("partial_id", unit.partial_id),
                    ("template_id", unit.template_id),
                    ("template_unit", unit.template_unit),
                    ("template_engine", unit.template_engine),
                    ("template_summary", unit.template_summary),
                    ("raw_summary", unit.get_raw_record_value("_summary")),
                    ("template_resource", unit.template_resource),
                    (
                        "template_description",
                        unit.get_raw_record_value(
                            "_description",
                            unit.get_raw_record_value("_purpose"),
                        ),
                    ),
                    ("template_filter", unit.template_filter),
                    ("template_imports", unit.template_imports),
                    ("origin", str(unit.origin)),
                    ("flags", unit.get_raw_record_value("flags")),
                    ("plugin", unit.get_raw_record_value("plugin")),
                    ("command", unit.get_raw_record_value("command")),
                    ("user", unit.get_raw_record_value("user")),
                    ("depends", unit.get_raw_record_value("depends")),
                    ("environ", unit.get_raw_record_value("environ")),
                    ("requires", unit.get_raw_record_value("requires")),
                )
            ),
        )


def _initial_provider_template(provider_ns, provider_ver, plugins_count):
    return {
        "namespace": provider_ns,
        "version": provider_ver,
        "count": plugins_count,
        "test_plans": [],
        "job_list": [],
        "template_job_list": [],
    }


class ProviderContainer:

    allowable_plugins = [
        "manual",
        "shell",
        "user-interact",
        "user-interact-verify",
        "attachment",
        "resource",
        "unknown",
    ]

    def __init__(self):
        self.provider_data = {}
        self.cur_provider_name = ""
        self.cur_provider_ns = ""
        self.cur_provider_ver = ""

    def get_data(self, pd_obj):
        if pd_obj.group == "provider":
            self._handle_provider_data(pd_obj)
        elif pd_obj.group == "test plan":
            self._handle_tp_data(pd_obj)
        elif pd_obj.group == "job":
            self._handle_job_data(pd_obj)
        elif pd_obj.group == "template":
            self._handle_template_data

        for child in pd_obj.children:
            if (
                child.group
                in [
                    "job",
                    "test plan",
                ]
                and child.name.split("::")[0] != self.cur_provider_ns
            ):
                print("#Mismatch namespace#")
                print(f"\t{child.group}: {child.name}")
                print(f"\tProvider namespace: {self.cur_provider_ns}")
            self.get_data(child)

    def _handle_provider_data(self, obj):
        self.cur_provider_name = obj.name
        self.cur_provider_ns = obj.attrs["namespace"]
        self.cur_provider_ver = obj.attrs["version"]
        plugins_count = {"total": 0}
        for key in self.allowable_plugins:
            plugins_count.update({key: 0})
        self.provider_data.update(
            {
                self.cur_provider_name: _initial_provider_template(
                    self.cur_provider_ns,
                    self.cur_provider_ver,
                    plugins_count,
                )
            }
        )

    def _handle_tp_data(self, obj):
        pd = self.provider_data[self.cur_provider_name]
        if obj.name in [tmp.get("name") for tmp in pd["test_plans"]]:
            raise KeyError(f"duplicate test plan name: {obj.name}")

        _, _name = obj.name.split("::")
        _tmp_dict = {"name": _name}
        for _key, _value in DEFAULT_TP_MAPPING.items():
            _tmp_dict.update({_key: obj.attrs.get(_value, None)})

        pd["test_plans"].append(_tmp_dict)

    def _handle_job_data(self, obj):

        if any(
            [obj.name in pd["job_list"] for pd in self.provider_data.values()]
        ):
            raise KeyError(f"\tJob is duplicated. job: {obj.name}")
        pd = self.provider_data[self.cur_provider_name]
        _ns, _name = obj.name.split("::")

        pd["count"]["total"] += 1
        job_plugin = (
            obj.attrs["plugin"]
            if obj.attrs["plugin"] in self.allowable_plugins
            else "unknown"
        )
        pd["count"][job_plugin] += 1
        _tmp_dict = {"name": _name}
        for _key, _value in DEFAULT_JOB_MAPPING.items():
            _tmp_dict.update({_key: obj.attrs.get(_value, None)})
        pd["job_list"].append(_tmp_dict)

    def _handle_template_data(self, obj):
        pd = self.provider_data[self.cur_provider_name]
        _ns, _name = obj.name.split("::")

        pd["count"]["total"] += 1
        job_plugin = (
            obj.attrs["plugin"]
            if obj.attrs["plugin"] in self.allowable_plugins
            else "unknown"
        )
        pd["count"][job_plugin] += 1
        _tmp_dict = {"name": _name}
        for _key, _value in TEMPLATE_JOB_MAPPING.items():
            _tmp_dict.update({_key: obj.attrs.get(_value, None)})
        pd["template_job_list"].append(_tmp_dict)

    def _remove_comments_from_records(self, data):
        new_records = []
        for record in data:
            if not record.startswith("#"):
                new_records.append(record.strip())
        return new_records

    def _handle_multiple_records(self, data):
        if isinstance(data, str):
            return self._remove_comments_from_records(data.splitlines())
        elif isinstance(data, list):
            return self._remove_comments_from_records(data)
        else:
            return data


def go_through_providers(provider_root):
    print("## Start to browse objects from providers")
    obj_pd_container = ProviderContainer()
    obj_pd_container.get_data(provider_root)
    print("## End to browse objects from providers")

    return obj_pd_container.provider_data


def dump_test_plans(providers=["all"], output_format="yaml"):
    sa = SessionAssistant(
        "com.canonical:checkbox-cli",
        "0.99",
        "0.99",
        ["restartable"],
    )

    installed_providers = sa.get_selected_providers()
    if not providers:
        raise SystemExit("providers variable should not be empty")
    elif providers != ["all"]:
        for provider in copy.copy(installed_providers):
            if provider.name not in providers:
                installed_providers.remove(provider)

    if not installed_providers:
        raise SystemExit(
            f"{providers} are not available in current environment"
        )

    print("## Browsing...")
    root = ExplorerMore(installed_providers).get_object_tree()
    return go_through_providers(root)


def dump_to_file(data, filename, file_format):
    with open(filename, "w") as tmpfile:
        if file_format == "yaml":
            yaml.dump(data, tmpfile, default_flow_style=False)
        elif file_format == "json":
            json.dump(data, tmpfile, indent=4)


def sort_by_directory_for_environ(data):

    sorted_cases = {}
    all_cases_with_env = {}

    for job_group, pattern in {
        "job_list": "job",
        "template_job_list": "template_job",
    }.items():
        for test_case in data.get(job_group, []):
            test_case.update({"job_type": pattern})
            primary_key = test_case.get("environ")
            secondary_key = test_case.get("name")
            path, _ = os.path.split(test_case.get("file"))

            if not primary_key:
                continue

            if secondary_key not in all_cases_with_env.keys():
                all_cases_with_env.update({secondary_key: test_case})

            if path not in sorted_cases.keys():
                sorted_cases[path] = {}

            for tmp_key in primary_key.split():
                if tmp_key in sorted_cases[path].keys():
                    sorted_cases[path][tmp_key].append(secondary_key)
                else:
                    sorted_cases[path][tmp_key] = [secondary_key]

    return sorted_cases, all_cases_with_env


README_TEMPLATE = """
## <a id='top'>environ keys for {{ unit }} tests</a>
{% for env, cases in env_cases.items() %}
- {{ env }}
    - Affected Test Cases:
{%- for case in cases %}
        - [{{ case }}](#{{ case }})
{%- endfor %}
{%- endfor %}

## Detailed test cases contains environ variable
{%- for case in all_cases %}
### <a id='{{ case.name }}'>{{ case.name }}</a>
{%- for key in JOB_OUTPUT_MAPPING.get(case['job_type']) %}
- **{{ key }}:**
{% if key in ['description', 'command'] -%}
```
{{ case[key] }}
```
{%- elif key in ['file'] -%}
[source file]({{ case[key] | basename }})
{%- else -%}
{{ case[key] }}
{%- endif %}
{% endfor -%}
[Back to top](#top)
{% endfor %}
"""


def render_readme_with_env(unit, env_cases, full_cases_set):
    JOB_OUTPUT_MAPPING = {
        "job": [
            "summary",
            "description",
            "file",
            "environ",
            "command",
        ],
        "template_job": [
            "summary",
            "template_summary",
            "description",
            "file",
            "environ",
            "command",
        ],
    }
    detailed_cases_with_env = []
    for cases in env_cases.values():
        for case in cases:
            if full_cases_set[case] not in detailed_cases_with_env:
                detailed_cases_with_env.append(full_cases_set[case])

    jinja2_env = jinja2.Environment(loader=jinja2.BaseLoader)
    jinja2_env.filters["basename"] = os.path.basename
    jinja_template = jinja2_env.from_string(README_TEMPLATE)
    return jinja_template.render(
        unit=unit,
        env_cases=env_cases,
        all_cases=detailed_cases_with_env,
        JOB_OUTPUT_MAPPING=JOB_OUTPUT_MAPPING,
    )


def generate_job_readme(provider_dir, provider_data):

    sorted_cases, all_cases = sort_by_directory_for_environ(provider_data)

    for key in sorted_cases.keys():
        _, filename = os.path.split(key)
        string = render_readme_with_env(
            filename, sorted_cases.get(key, {}), all_cases
        )

        output_file = os.path.join(
            provider_dir,
            "units",
            f"{filename}",
            "cases_and_environ.md",
        )
        print(f"Updating/Creating the {output_file}")
        with open(output_file, "w+") as fp:
            fp.write(string)


def main():

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "providers",
        nargs="*",
        default=["all"],
        help="list objects from the specified provider",
    )
    parser.add_argument(
        "-d", "--output-dir", type=str, help="output directory"
    )
    parser.add_argument(
        "-f",
        "--output-format",
        default="yaml",
        choices=["yaml", "json"],
        help="output file format",
    )
    args = parser.parse_args()

    provider_data = dump_test_plans(args.providers)
    if args.output_dir:
        if not os.path.exists(args.output_dir):
            os.makedirs(args.output_dir)
        os.chdir(args.output_dir)
    for provider, value in provider_data.items():
        if not os.path.exists(provider):
            os.makedirs(provider)
        generate_job_readme(provider, value)


if __name__ == "__main__":
    main()
