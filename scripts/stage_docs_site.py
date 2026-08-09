#!/usr/bin/env python3
"""Stage the public docs site together with source-synchronized repo guidance.

The friendly pages under ``docs-site/`` stay deliberately curated. Longer
authoritative documents remain in their established repository locations and
are copied into first-class public routes at build time. This gives readers one
site without creating a second hand-maintained copy of the engineering docs.
"""

from __future__ import annotations

import argparse
from html import unescape
import json
from pathlib import Path
import re
import shutil
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
DOCS_SITE = REPO_ROOT / "docs-site"
MANIFEST = DOCS_SITE / "_data" / "source-docs.json"
PRODUCT = DOCS_SITE / "_data" / "product.json"

MARKDOWN_LINK = re.compile(r"(?P<prefix>!?\[[^\]]*\]\()(?P<target>[^)\s]+)(?P<suffix>\))")
FIRST_H1 = re.compile(r"\A#\s+[^\n]+\n+")
LOCAL_ASSET_SUFFIXES = {".dot", ".gif", ".html", ".jpeg", ".jpg", ".png", ".svg"}
FRONTMATTER = re.compile(r"\A---\n(?P<frontmatter>.*?)\n---\n(?P<body>.*)\Z", re.DOTALL)
HEADING = re.compile(r"^(?P<level>#{1,4})\s+(?P<title>.+?)\s*#*\s*$", re.MULTILINE)
FENCED_CODE = re.compile(r"^```[^\n]*\n|^```\s*$", re.MULTILINE)
HTML_TAG = re.compile(
    r"</?(?:a|blockquote|br|code|details|div|em|figcaption|figure|h[1-6]|img|p|pre|span|strong|summary|table|tbody|td|th|thead|tr|ul|ol|li)\b[^>]*>",
    re.IGNORECASE,
)
LIQUID = re.compile(r"{%.*?%}", re.DOTALL)
LIQUID_OUTPUT = re.compile(r"{{.*?}}", re.DOTALL)
PRODUCT_OUTPUT = re.compile(r"{{\s*site\.data\.product\.(?P<key>[a-z_]+)(?:\s*\|[^}]*)?\s*}}")
MARKDOWN_IMAGE = re.compile(r"!\[([^]]*)\]\([^)]+\)")
MARKDOWN_TEXT_LINK = re.compile(r"\[([^]]+)\]\([^)]+\)")
SEARCH_INDEX = "search-index.json"
SEARCH_CHUNK_LIMIT = 1_050
SEARCH_CHUNK_OVERLAP = 160


def load_manifest() -> dict[str, Any]:
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if data.get("version") != 1 or not isinstance(data.get("documents"), list):
        raise ValueError("docs source manifest must be version 1 with a documents list")
    return data


def _relative_repo_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError as error:
        raise ValueError(f"source link escapes the repository: {path}") from error


def _route_expression(route: str, fragment: str) -> str:
    rendered = "{{ '" + route + "' | relative_url }}"
    return f"{rendered}#{fragment}" if fragment else rendered


def rewrite_links(
    text: str,
    *,
    source: Path,
    route_by_source: dict[str, str],
    aliases: dict[str, str],
    fragment_aliases: dict[str, str],
    repository_url: str,
    output: Path,
) -> str:
    """Rewrite repo-relative links to public routes, copied assets, or source code."""

    def replace(match: re.Match[str]) -> str:
        target = match.group("target")
        if target.startswith(("#", "http://", "https://", "mailto:")):
            return match.group(0)

        path_text, separator, fragment = target.partition("#")
        resolved = (source.parent / path_text).resolve()
        relative = _relative_repo_path(resolved)
        route = route_by_source.get(relative) or aliases.get(relative)
        if route is not None:
            rewritten_fragment = (
                fragment_aliases.get(f"{relative}#{fragment}", fragment) if separator else ""
            )
            replacement = _route_expression(route, rewritten_fragment)
        elif resolved.suffix.lower() in LOCAL_ASSET_SUFFIXES and resolved.is_file():
            asset_relative = Path("source-assets") / relative
            asset_output = output / asset_relative
            asset_output.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(resolved, asset_output)
            replacement = _route_expression("/" + asset_relative.as_posix(), fragment)
        else:
            suffix = f"#{fragment}" if separator else ""
            replacement = f"{repository_url}/blob/main/{relative}{suffix}"
        return f"{match.group('prefix')}{replacement}{match.group('suffix')}"

    return MARKDOWN_LINK.sub(replace, text)


def render_source_page(
    document: dict[str, str],
    *,
    route_by_source: dict[str, str],
    aliases: dict[str, str],
    fragment_aliases: dict[str, str],
    repository_url: str,
    output: Path,
) -> str:
    source_relative = document["source"]
    source = REPO_ROOT / source_relative
    body = FIRST_H1.sub("", source.read_text(encoding="utf-8"), count=1)
    body = rewrite_links(
        body,
        source=source,
        route_by_source=route_by_source,
        aliases=aliases,
        fragment_aliases=fragment_aliases,
        repository_url=repository_url,
        output=output,
    )
    frontmatter = (
        "---\n"
        "layout: default\n"
        f"title: {json.dumps(document['title'])}\n"
        f"description: {json.dumps(document['description'])}\n"
        f"permalink: {document['route']}\n"
        f"source_document: {json.dumps(source_relative)}\n"
        "---\n\n"
    )
    note = (
        f"> **Source-synchronized reference.** This page is built directly from "
        f"`{source_relative}` so the public site and repository guidance stay together.\n\n"
    )
    return frontmatter + note + body


def _frontmatter_value(frontmatter: str, key: str, default: str = "") -> str:
    match = re.search(rf"^{re.escape(key)}:\s*(.+?)\s*$", frontmatter, re.MULTILINE)
    if match is None:
        return default
    value = match.group(1).strip()
    if value.startswith(('"', "'")):
        try:
            loaded = json.loads(value)
        except json.JSONDecodeError:
            loaded = value.strip("'\"")
        return str(loaded)
    return value


def _slugify_heading(title: str) -> str:
    """Approximate Kramdown's stable ASCII heading identifiers."""

    plain = _clean_markdown(title).lower()
    slug = re.sub(r"[^a-z0-9\s-]", "", plain)
    return re.sub(r"[-\s]+", "-", slug).strip("-") or "section"


def _clean_markdown(text: str) -> str:
    def table_row(match: re.Match[str]) -> str:
        cells = [cell.strip() for cell in match.group(1).split("|")]
        if cells and all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells):
            return " "
        return " — ".join(cell for cell in cells if cell) + ". "

    text = LIQUID.sub(" ", text)
    text = LIQUID_OUTPUT.sub(" ", text)
    text = FENCED_CODE.sub("", text)
    text = re.sub(r"^\s*\|(.+)\|\s*$", table_row, text, flags=re.MULTILINE)
    text = MARKDOWN_IMAGE.sub(r"\1", text)
    text = MARKDOWN_TEXT_LINK.sub(r"\1", text)
    text = HTML_TAG.sub(" ", text)
    text = re.sub(r"^\s{0,3}(?:>|[-+*]|\d+[.)])\s+", "", text, flags=re.MULTILINE)
    text = text.replace("~~", "")
    text = re.sub(r"[`*|]", "", text)
    text = re.sub(r"\s+", " ", unescape(text))
    return text.strip()


def _search_chunks(text: str) -> list[str]:
    """Create compact overlapping chunks without splitting words."""

    if len(text) <= SEARCH_CHUNK_LIMIT:
        return [text] if text else []
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(len(text), start + SEARCH_CHUNK_LIMIT)
        if end < len(text):
            boundary = text.rfind(" ", start, end)
            if boundary > start + SEARCH_CHUNK_LIMIT // 2:
                end = boundary
        chunks.append(text[start:end].strip())
        if end >= len(text):
            break
        start = max(end - SEARCH_CHUNK_OVERLAP, start + 1)
        next_space = text.find(" ", start)
        if next_space != -1 and next_space < end:
            start = next_space + 1
    return [chunk for chunk in chunks if chunk]


def _replace_product_tokens(text: str, product: dict[str, str]) -> str:
    def replace(match: re.Match[str]) -> str:
        value = product.get(match.group("key"), "")
        return value.lower() if "downcase" in match.group(0) else value

    return PRODUCT_OUTPUT.sub(replace, text)


def build_search_index(output: Path, product: dict[str, str]) -> list[dict[str, str]]:
    """Index every staged public Markdown page at section granularity."""

    entries: list[dict[str, str]] = []
    for path in sorted(output.rglob("*.md")):
        if any(part.startswith("_") for part in path.relative_to(output).parts):
            continue
        raw = _replace_product_tokens(path.read_text(encoding="utf-8"), product)
        parsed = FRONTMATTER.match(raw)
        if parsed is None:
            continue
        frontmatter = parsed.group("frontmatter")
        body = parsed.group("body")
        title = _frontmatter_value(frontmatter, "title", path.stem.replace("-", " ").title())
        description = _frontmatter_value(frontmatter, "description")
        route = _frontmatter_value(frontmatter, "permalink")
        if not route:
            relative = path.relative_to(output).with_suffix("")
            route = "/" if relative.as_posix() == "index" else f"/{relative.as_posix()}/"

        matches = list(HEADING.finditer(body))
        sections: list[tuple[str, str, str]] = []
        intro_end = matches[0].start() if matches else len(body)
        sections.append(("Overview", "", body[:intro_end]))
        for index, match in enumerate(matches):
            if len(match.group("level")) == 1:
                continue
            section_end = matches[index + 1].start() if index + 1 < len(matches) else len(body)
            heading = _clean_markdown(match.group("title"))
            sections.append((heading, _slugify_heading(heading), body[match.end() : section_end]))

        for section, anchor, section_body in sections:
            clean = _clean_markdown(section_body)
            if not clean and section != "Overview":
                continue
            searchable = " ".join(item for item in (section, description, clean) if item)
            for chunk in _search_chunks(searchable):
                entries.append(
                    {
                        "title": title,
                        "section": section,
                        "route": route,
                        "anchor": anchor,
                        "description": description,
                        "text": chunk,
                    }
                )
    return entries


def stage(output: Path) -> None:
    output = output.resolve()
    if output == REPO_ROOT.resolve() or output == DOCS_SITE.resolve():
        raise ValueError("refusing to stage over the repository or docs-site source")
    if output.exists():
        raise FileExistsError(f"output already exists: {output}")

    manifest = load_manifest()
    documents = manifest["documents"]
    route_by_source = {str(item["source"]): str(item["route"]) for item in documents}
    aliases = {str(key): str(value) for key, value in manifest.get("link_aliases", {}).items()}
    fragment_aliases = {
        str(key): str(value) for key, value in manifest.get("fragment_aliases", {}).items()
    }
    product = {
        str(key): str(value)
        for key, value in json.loads(PRODUCT.read_text(encoding="utf-8")).items()
    }
    repository_url = f"https://github.com/{product['repository']}"

    shutil.copytree(DOCS_SITE, output, ignore=shutil.ignore_patterns(".jekyll-cache", ".DS_Store"))
    for raw_document in documents:
        document = {str(key): str(value) for key, value in raw_document.items()}
        source = REPO_ROOT / document["source"]
        if not source.is_file():
            raise FileNotFoundError(f"mapped source document does not exist: {source}")
        destination = output / document["output"]
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            render_source_page(
                document,
                route_by_source=route_by_source,
                aliases=aliases,
                fragment_aliases=fragment_aliases,
                repository_url=repository_url,
                output=output,
            ),
            encoding="utf-8",
        )
    search_index = build_search_index(output, product)
    (output / SEARCH_INDEX).write_text(
        json.dumps(search_index, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="new staging directory")
    args = parser.parse_args()
    stage(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
