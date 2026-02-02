import json
import logging
from pathlib import Path
from functools import wraps
from itertools import takewhile


from plainbox.impl.secure.rfc822 import load_rfc822_records


def multiline_text(value):
    # no more trailing spaces
    lines = (x.rstrip() for x in value.splitlines())
    # line composed by a . is actually a hack to add an empty line in pxus
    lines = (x if x != "." else "" for x in lines)
    return "\n".join(lines)


class CommentedError(ValueError):
    def __init__(self, value, comment):
        self.value = value
        self.comment = comment
        super().__init__()


def commentable_value(value):
    """
    This returns the value or raises a CommentedError if the value contains
    a comment
    """
    # sibling will have mixed types (int), so we need to str it here
    value = str(value)
    # this is technically not proper, as these values are not stringable, but
    # validation is not the job of the translator
    value, comment = split_comment(value)
    if comment:
        # here we raise an exception as rumel.yaml doesn't support returning
        # commented fields
        raise CommentedError(value, comment)
    return value


class JinjaError(ValueError):
    pass


def dont_translate_jinja(f):
    """
    For backward compatibility, avoid touching jinja values

    Given that jinja may completely change the semantic of the unit, it is
    virtually impossible to translate it. For example:

        requires:
          package.name == 'bluez' or snap.name == 'bluez'
          {%- if __on_ubuntucore__ %}
          connections.slot == 'bluez:service'
          {% endif -%}

        This would correclty be translated as

        requires:
          - package.name == 'bluez' or snap.name == 'bluez'
          {%- if __on_ubuntucore__ %}
          - connections.slot == 'bluez:service'
          {% endif -%}

        but this wouldn't work if the value in the if was

        requires:
          package.name == 'bluez' or snap.name == 'bluez'
          {%- if __on_ubuntucore__ %}some.foo == 'bar'
          connections.slot == 'bluez:service'
          {% endif -%}


    """

    @wraps(f)
    def _f(value):
        if "{#" in value or "{%" in value:
            raise JinjaError()
        return f(value)

    return _f


def split_stringable(value, delimiter):
    """
    Split value given a delimiter respecting string delimiters

    When the delimiter is inside a string, it is part of the string and not
    to be used in the split. Classic example is:

        "abc #123" # <- this part is the comment, not 123
    """
    if delimiter not in value:
        return value, ""
    in_string = False  # False, ', "
    just_escaped = False
    start_of_comment = -1
    for i, c in enumerate(value):
        if just_escaped:
            just_escaped = False
        elif in_string and c == in_string:
            in_string = False
        elif c == "\\":  # escape char
            just_escaped = True
        elif c == delimiter and not in_string:
            start_of_comment = i
            break
        elif (
            c in ["'", '"'] and not in_string
        ):  # string contains ' or " handled above
            in_string = c
    if start_of_comment >= 0:
        return (
            value[:start_of_comment].rstrip(),
            value[start_of_comment + 1 :].lstrip(),
        )
    return value, ""


def split_comment(value):
    return split_stringable(value, "#")


def split_string_values(value):
    """
    These are strings delimited values separated by spaces

    Example:
        "bluetooth/bluez-internal-hci-tests_Read Country Code" certification-status=blocker
    """
    return split_stringable(value, " ")


def translate_raw_json(value):
    return json.loads(value)


@dont_translate_jinja
def translate_siblings(value):
    # value may be invalid json because it contains formatters, so objects
    # will be delimited with {{ and }}. Given that we are now parsing this as
    # data, this is no longer needed.
    class no_replace(dict):
        def __missing__(self, key):
            return "{" + key + "}"

    if "{{" in value:
        value = value.format_map(no_replace())
    units = json.loads(value)
    return [translate_unit(unit) for unit in units]


@dont_translate_jinja
def translate_requires(value):
    from ruamel.yaml.comments import CommentedSeq

    requires_lines = value.splitlines()
    to_r = CommentedSeq()
    for requires_line in requires_lines:
        require, comment = split_comment(requires_line)
        if require:
            require = require.strip()
            to_r.append(require)
            if comment:
                to_r.yaml_add_eol_comment(comment, len(to_r) - 1)
        elif comment:
            if (
                len(to_r) != 0
            ):  # else this doesn't work, cant set for unknown line
                to_r.yaml_set_comment_before_after_key(
                    len(to_r), before=comment
                )
            else:
                to_r.yaml_set_start_comment(comment)
    return to_r


def translate_single_multiline_stringable_values(value):
    from ruamel.yaml.comments import CommentedSeq

    to_r = CommentedSeq()
    if "\n" not in value:
        depends, comment = split_comment(value)
        if "," in depends:
            to_r += [x.strip() for x in depends.split(",")]
        else:
            to_r += depends.split()
        if comment:
            to_r.yaml_set_start_comment(comment)
        return to_r
    depends = value.splitlines()
    for depend in depends:
        depend, comment = split_comment(depend)
        depend = depend.strip()
        if depend:
            to_r.append(depend)
            if comment:
                to_r.yaml_add_eol_comment(comment, len(to_r) - 1)
        elif comment:
            if (
                len(to_r) != 0
            ):  # else this doesn't work, cant set for unknown line
                to_r.yaml_set_comment_before_after_key(
                    len(to_r), before=comment
                )
            else:
                to_r.yaml_set_start_comment(comment)
    return to_r


@dont_translate_jinja
def translate_include(value):
    includes = value.splitlines()
    from ruamel.yaml.comments import CommentedSeq, CommentedMap

    to_r = CommentedSeq()
    for inclusion in includes:
        inclusion = inclusion.strip()
        value, comment = split_comment(inclusion)
        if value:
            value, overrides = split_string_values(value)
        else:
            value = overrides = ""
        if overrides:  # we can assume there is value as well here
            assert overrides.startswith("certification-status")
            assert " " not in overrides, "Multi overrides are not supported"
            assert "," not in overrides, "Multi overrides are not supported"
            overriden, override_value = overrides.strip().split(
                "="
            )  # assumes 1 per line
            translation = {value: {overriden: override_value}}
            if comment:
                translation = CommentedMap(translation)
                translation.yaml_add_eol_comment(comment, value)
            to_r.append(translation)
        elif value:
            to_r.append(value)
            if comment:
                to_r.yaml_add_eol_comment(comment, len(to_r) - 1)
        elif comment:
            if (
                len(to_r) != 0
            ):  # else this doesn't work, cant set for unknown line
                to_r.yaml_set_comment_before_after_key(
                    len(to_r), before=comment
                )
            else:
                to_r.yaml_set_start_comment(comment)
        else:
            assert False, "Tragedy"
    return to_r


def translate_options(value):
    assert "#" not in value
    return [x.strip() for x in value.split(",")]


field_translators = {
    "id": commentable_value,
    "unit": commentable_value,
    "name": commentable_value,
    "estimated_duration": commentable_value,
    "os-id": commentable_value,
    "plugin": commentable_value,
    "category_id": commentable_value,
    "user": commentable_value,
    "command": commentable_value,
    "value-type": commentable_value,
    "template-resource": commentable_value,
    "template-unit": commentable_value,
    "template-id": commentable_value,
    "template-engine": commentable_value,
    "entry_point": commentable_value,
    "file_extension": commentable_value,
    "Depends": commentable_value,
    "Suggests": commentable_value,
    "Recommends": commentable_value,
    "os-version-id": commentable_value,
    "group": commentable_value,
    "description": multiline_text,
    "description": multiline_text,
    "summary": multiline_text,
    "purpose": multiline_text,
    "steps": multiline_text,
    "prompt": multiline_text,
    "hidden-reason": multiline_text,
    "verification": multiline_text,
    "template-summary": multiline_text,
    "data": translate_raw_json,
    "environ": translate_single_multiline_stringable_values,
    "flags": translate_single_multiline_stringable_values,
    "after": translate_single_multiline_stringable_values,
    "salvages": translate_single_multiline_stringable_values,
    "depends": translate_single_multiline_stringable_values,
    "before": translate_single_multiline_stringable_values,
    "setup_include": translate_include,
    "include": translate_include,
    "bootstrap_include": translate_include,
    "nested_part": translate_include,
    "exclude": translate_include,
    "mandatory_include": translate_include,
    "requires": translate_requires,
    "template-imports": translate_requires,
    "imports": translate_requires,
    "template-filter": translate_requires,
    "siblings": translate_siblings,
    "certification_status_overrides": translate_requires,
    "options": translate_options,
}


def translate_unit(unit_dict: dict) -> dict:
    from ruamel.yaml.comments import CommentedMap

    def no_more_translations(x):
        if x.startswith("_"):
            return x[1:]
        return x

    to_return = CommentedMap()
    for key, value in unit_dict.items():
        key = no_more_translations(key)
        try:
            translated = field_translators[key](value)
            to_return[key] = translated
        except KeyError as e:
            logging.error(
                (
                    "Unit {} has invalid field '{}', is it a typo? "
                    "Dumping it as-is in the unit"
                ).format(unit_dict.get("id", str(unit_dict)), str(e))
            )
            to_return[key] = value
        except JinjaError as e:
            logging.error(
                (
                    "Refusing to translate field '{}' of unit '{}' as it "
                    "contains jinja markers. Dumping it as-is in the unit"
                ).format(key, unit_dict.get("id", str(unit_dict)))
            )
            to_return[key] = value
        except CommentedError as e:
            to_return[key] = e.value
            to_return.yaml_add_eol_comment(e.comment, key)

    return to_return


def multiline_str_representer(dumper, data):
    """
    Render multiline strings as blocks, leave other strings unchanged.

    This is a custom YAML representer for strings.
    """
    # see section "Constructors, representers resolvers"
    # at https://pyyaml.org/wiki/PyYAMLDocumentation
    # and https://yaml.org/spec/1.2.2/#literal-style
    if "\n" in data:
        # remove trailing whitespace from each line
        # (suggested fix for https://github.com/yaml/pyyaml/issues/240)
        data = "\n".join(line.rstrip() for line in data.splitlines()) + "\n"
        return dumper.represent_scalar(
            "tag:yaml.org,2002:str", data, style="|"
        )
    return dumper.represent_scalar("tag:yaml.org,2002:str", data)


def get_header_comment(text: str) -> str:
    lines = iter(text.splitlines())
    to_return = "\n".join(
        # remove # and possible following spaces
        x[1:].strip()
        for x in takewhile(lambda x: x.startswith("#"), lines)
    )
    # if there are more comments, lets warn the user they will be ignored
    other_comments = (x for x in lines if x.startswith("#"))
    for comment in other_comments:
        logging.error(
            "Translator doesn't support non-header comments, ignoring: '%s'",
            comment,
        )
    return to_return


class Translator:
    def register_arguments(self, parser):
        parser.add_argument(
            "paths",
            nargs="+",
            help="Units to be translated",
            type=Path,
        )

    def invoked(self, ctx):
        try:
            from ruamel.yaml import YAML
        except ModuleNotFoundError:
            raise SystemExit(
                "The translator can be used only by installing Checkbox "
                "from source with:\n"
                "  pip install checkbox-ng[translator]"
            )

        print("Starting...")
        for path in ctx.args.paths:
            with path.open("r") as f:
                text = f.read()
            loaded = load_rfc822_records(text, source=str(path))
            documents = []

            yaml = YAML()
            for unit_dict in loaded:
                documents.append(translate_unit(unit_dict.data))

            header_comment = get_header_comment(text)
            if header_comment:
                documents[0].yaml_set_start_comment(header_comment)

            yaml.width = 120
            yaml.default_flow_style = False
            yaml.representer.add_representer(str, multiline_str_representer)
            yaml.indent(mapping=2, sequence=4, offset=2)
            with path.with_suffix(".yaml").open("w+") as f:
                yaml.dump_all(documents, f)
