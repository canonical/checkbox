#
# This file is part of Checkbox.
#
# Copyright 2008 Canonical Ltd.
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
#
import re
import logging


EXTENDED_STRING = "_extended"


class Template:

    def _reader(self, file, size=4096, delimiter=r"\n{2,}"):
        buffer_old = ""
        while True:
            buffer_new = file.read(size)
            if not buffer_new:
                break

            lines = re.split(delimiter, buffer_old + buffer_new)
            buffer_old = lines.pop(-1)

            for line in lines:
                yield line

        yield buffer_old

    def dump_file(self, elements, file, filename="<stream>"):
        for element in elements:
            for long_key in list(element.keys()):
                if long_key.endswith(EXTENDED_STRING):
                    short_key = long_key.replace(EXTENDED_STRING, "")
                    del element[short_key]

            for key, value in element.items():
                if key.endswith(EXTENDED_STRING):
                    key = key.replace(EXTENDED_STRING, "")
                    file.write("%s:\n" % key)
                    for line in value.split("\n"):
                        file.write(" %s\n" % line)
                elif isinstance(value, (list, tuple)):
                    file.write("%s:\n" % key)
                    for v in value:
                        file.write(" %s\n" % v)
                else:
                    file.write("%s: %s\n" % (key, value))

            file.write("\n")

    def dump_filename(self, elements, filename):
        logging.info("Dumping elements to filename: %s", filename)

        with open(filename, "w") as stream:
            return self.dump_file(elements, stream, filename)

    def load_file(self, file, filename="<stream>"):
        elements = []
        for string in self._reader(file):
            if not string:
                break

            element = {}

            def _save(field, value, extended):
                extended = extended.rstrip("\n")
                if field:
                    if field in element:
                        raise Exception("Template %s has a duplicate "
                            "field '%s' with a new value '%s'." 
                                % (filename, field, value))
                    element[field] = value
                    if extended:
                        element["%s%s" % (field, EXTENDED_STRING)] = extended

            string = string.strip("\n")
            field = value = extended = ""
            for line in string.split("\n"):
                line.strip()
                if line.startswith("#"):
                    continue

                match = re.search(r"^([-_.A-Za-z0-9@]*):\s?(.*)", line)
                if match:
                    _save(field, value, extended)
                    field = match.groups()[0]
                    value = match.groups()[1].rstrip()
                    extended = ""
                    continue

                if re.search(r"^\s\.$", line):
                    extended += "\n\n"
                    continue

                match = re.search(r"^\s(\s+.*)", line)
                if match:
                    bit = match.groups()[0].rstrip()
                    if len(extended) and not re.search(r"[\n ]$", extended):
                        extended += "\n"

                    extended += bit + "\n"
                    continue

                match = re.search(r"^\s(.*)", line)
                if match:
                    bit = match.groups()[0].rstrip()
                    if len(extended) and not re.search(r"[\n ]$", extended):
                        if extended.endswith("\\"):
                            extended = extended[:-1].rstrip() + " "
                        else:
                            extended += "\n"

                    extended += bit
                    continue

                raise Exception("Template %s parse error at: %s" \
                    % (filename, line))

            _save(field, value, extended)

            elements.append(element)

        return elements

    def load_filename(self, filename):
        logging.info("Loading elements from filename: %s", filename)

        with open(filename, "r", encoding="utf-8") as stream:
            return self.load_file(stream, filename)
