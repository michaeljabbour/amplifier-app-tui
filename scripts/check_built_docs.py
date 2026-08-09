#!/usr/bin/env python3
"""Fail when a built documentation site contains a broken internal link."""

from __future__ import annotations

import argparse
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urljoin, urlparse


class PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.ids: set[str] = set()
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        identifier = values.get("id")
        if identifier:
            self.ids.add(identifier)
        if tag == "a" and values.get("href"):
            self.links.append(values["href"] or "")


def _route_for_file(root: Path, page: Path) -> str:
    relative = page.relative_to(root).as_posix()
    if relative == "index.html":
        return "/"
    if relative.endswith("/index.html"):
        return "/" + relative[: -len("index.html")]
    return "/" + relative


def _strip_baseurl(path: str, baseurl: str) -> str:
    normalized = "/" + baseurl.strip("/") if baseurl.strip("/") else ""
    if normalized and path == normalized:
        return "/"
    if normalized and path.startswith(normalized + "/"):
        return path[len(normalized) :]
    return path


def check_site(root: Path, *, baseurl: str = "") -> list[str]:
    pages: dict[str, PageParser] = {}
    for page in sorted(root.rglob("*.html")):
        parser = PageParser()
        parser.feed(page.read_text(encoding="utf-8"))
        pages[_route_for_file(root, page)] = parser

    failures: list[str] = []
    for route, parser in pages.items():
        current = "https://docs.invalid" + route
        for href in parser.links:
            parsed_raw = urlparse(href)
            if parsed_raw.scheme in {"http", "https", "mailto", "tel"} or href.startswith("//"):
                continue
            parsed = urlparse(urljoin(current, href))
            target_path = unquote(_strip_baseurl(parsed.path, baseurl)) or "/"
            if target_path.endswith("/"):
                target_route = target_path
            elif Path(target_path).suffix.lower() in {"", ".html"}:
                target_route = target_path
            else:
                asset = root / target_path.lstrip("/")
                if not asset.exists():
                    failures.append(f"{route}: missing asset {href}")
                continue

            target = pages.get(target_route)
            if target is None:
                failures.append(f"{route}: missing route {href}")
                continue
            if parsed.fragment and parsed.fragment not in target.ids:
                failures.append(f"{route}: missing anchor {href}")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("--baseurl", default="")
    args = parser.parse_args()
    failures = check_site(args.root, baseurl=args.baseurl)
    if failures:
        print("Broken documentation links:")
        for failure in failures:
            print(f"- {failure}")
        return 1
    print(f"Documentation links OK: {args.root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
