#!/usr/bin/env python3

import re
import os
import sys
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import List, Sequence, Tuple, Callable, Optional

# type aliases
DfsCbRtn = Tuple[bool, str]
DfsCb = Callable[[ET.Element, List[str]], DfsCbRtn]
TagGetter = Callable[[ET.Element], str]


class Package:
    def __init__(self, json_obj: dict):
        self.json_obj = json_obj

    @property
    def name(self) -> str:
        return self.json_obj["name"]

    @property
    def version(self) -> str:
        return self.json_obj["version"]

    @property
    def is_source(self) -> bool:
        return self.json_obj["is_source"]

    @property
    def is_visible(self) -> bool:
        return self.json_obj.get("is_visible", not self.is_source)

    @property
    def need_ubuntu_pro(self) -> bool:
        return self.json_obj["pocket"].startswith("esm")

    def __repr__(self) -> str:
        additional = " (Ubuntu Pro)" if self.need_ubuntu_pro else ""
        return f"{self.name} - {self.version}{additional}"


class SecurityNotice:
    def __init__(self, json_obj: dict):
        self.json_obj = json_obj

    @property
    def published(self) -> datetime:
        return datetime.fromisoformat(self.json_obj["published"])

    def get_packages(self, release: str) -> Sequence[Package]:
        packages = self.json_obj["release_packages"].get(release, [])
        return [Package(p) for p in packages]


def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)


def ns_skipper(html: ET.Element) -> TagGetter:
    rgx = re.compile(r"^({http[s]?://(www.|)w3.org/[\w+/]+})?html$")
    match = rgx.match(html.tag)
    if match is None:
        raise ValueError('Root element\'s tag should be "html"!')
    ns_prefix = match.group(1)

    def real_tag(elem: ET.Element) -> str:
        tag = elem.tag
        return tag.replace(ns_prefix, "")

    return real_tag


def identify(elem: ET.Element, tag_getter: Optional[TagGetter] = None) -> str:
    class_list = elem.attrib.get("class")
    tag = elem.tag if tag_getter is None else tag_getter(elem)
    class_parts = [] if class_list is None else class_list.split(" ")
    return ".".join([tag] + class_parts)


def dfs(elem: ET.Element, paths: List[str], cb: DfsCb) -> bool:
    early_stop, ident = cb(elem, paths)
    if early_stop:
        return True

    paths.append(ident)
    for child in elem:
        if dfs(child, paths, cb):
            paths.pop()
            return True

    paths.pop()
    return False


def main(
    report: str,
    buffer_days: int,
    ignore: Callable[[str], bool],
    release: str,
):
    tree = ET.parse(report)
    root = tree.getroot()
    real_tag = ns_skipper(root)

    head = None
    body = None

    for child in root:
        tag = real_tag(child)
        if tag == "head":
            head = child
        elif tag == "body":
            body = child

    if head is None or body is None:
        raise ValueError("Cannot locate <head> and <body> tags under <html>.")

    target_css = ["resultbadA", "resultbadB"]

    def has_css_classes(targets: List[str]) -> DfsCb:
        def validator(elem: ET.Element, paths: List[str]) -> DfsCbRtn:
            tag = real_tag(elem)
            if paths != ["html", "head"]:
                return False, tag
            if tag != "style":
                return False, tag
            for selector in (f".{t}" for t in targets):
                if elem.text is not None and elem.text.find(selector) < 0:
                    return False, tag
            return True, tag

        return validator

    is_valid = dfs(head, ["html"], has_css_classes(target_css))
    if not is_valid:
        raise ValueError(
            "Cannot find target css under <style>, it is very likely "
            + "that this script is outdated!"  # noqa: W503
        )

    has_vuln = False

    def peek_vuln(elem: ET.Element, paths: List[str]) -> DfsCbRtn:
        ident = identify(elem, real_tag)
        if (
            paths[-2:] != ["table", "tr.LightRow.Center"]
            or ident != "td.SmallText.resultbadB"   # noqa: W503
        ):
            return False, ident
        nonlocal has_vuln
        has_vuln = int(elem.text or 0) > 0
        if has_vuln:
            eprint(f'* {elem.attrib["title"]}: {elem.text}')
        return True, ident

    is_valid = dfs(body, ["html"], peek_vuln)
    if not is_valid:
        raise ValueError(
            "Cannot find target HTML element, it is very likely "
            + "that this script is outdated!"   # noqa: W503
        )
    if not has_vuln:
        print("All avaliable CVEs are patched!")
        sys.exit(0)

    vuln_idents = [f"tr.{c}" for c in target_css]

    def report_vuln(elem: ET.Element, paths: List[str]) -> DfsCbRtn:
        ident = identify(elem, real_tag)
        if paths[-1:] == ["table"] and ident in vuln_idents:
            if len(elem) > 0:
                eprint(elem[-1].text)
            if len(elem) > 1 and len(elem[-2]) > 0:
                anchor = elem[-2][0]
                report_vuln_detail(anchor, "\t")

        return False, ident

    def report_vuln_detail(elem: ET.Element, indent: str):
        import json
        from urllib import request

        if identify(elem, real_tag) != "a.Hover":
            return
        href = elem.attrib["href"]
        eprint(f"{indent}- {href}")
        if buffer_days == 0:
            return

        endpoint = f"https://ubuntu.com/security/notices/{elem.text}.json"
        with request.urlopen(endpoint) as fd:
            raw_body = fd.read().decode("utf-8")
        security_notice = SecurityNotice(json.loads(raw_body))

        need_fixing = False
        for package in security_notice.get_packages(release):
            if not package.is_visible:
                continue

            sign = "+"
            if ignore(package.name):
                sign = "-"
            elif not package.need_ubuntu_pro:
                nonlocal critical_vulns
                critical_vulns += 1
                need_fixing = True
            eprint(f"{indent}\t{sign} {package}")
        # end for vuln

        passed = datetime.now() - security_notice.published
        need_fixing = need_fixing and passed.days > buffer_days
        log_lvl = "ERROR" if need_fixing else "WARNING"
        display_date = security_notice.published.strftime("%d %B %Y")
        eprint(f"{indent}- [{log_lvl}] Published: {display_date}")

    critical_vulns = 0
    dfs(body, ["html"], report_vuln)
    sys.exit(1 if critical_vulns > 0 else 0)


def ignore_package(include_list_file: Optional[str]) -> Callable[[str], bool]:
    if include_list_file is None or not os.path.exists(include_list_file):
        return lambda _: False

    include_list = set()
    with open(include_list_file, "r") as fd:
        for line in fd:
            package = line.strip().split(":")[0]
            include_list.add(package)

    def ignore(package: str) -> bool:
        return package not in include_list

    return ignore


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(prog="oval-report")
    parser.add_argument("--report", metavar="report.html", required=True)
    parser.add_argument("--buffer-days", type=int, default=7)
    parser.add_argument("--include-packages", metavar="dpkg.list")
    parser.add_argument("--release", default="jammy")
    parser.add_argument(
        "--version", action="version", version="%(prog)s 0.3.2"
    )

    args = parser.parse_args()
    main(
        args.report,
        args.buffer_days,
        ignore_package(args.include_packages),
        args.release,
    )
