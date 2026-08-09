"""Contracts for source-synchronized public documentation."""

from __future__ import annotations

import json
from pathlib import Path
import re
import subprocess
import sys
import tomllib

from amplifier_app_tui.product import (
    BRAND_NAME,
    DISPLAY_NAME,
    DISTRIBUTION_NAME,
    EXECUTABLE_NAME,
    REPOSITORY_SLUG,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
DOCS_SITE = REPO_ROOT / "docs-site"
MANIFEST_PATH = DOCS_SITE / "_data" / "source-docs.json"
PRODUCT_PATH = DOCS_SITE / "_data" / "product.json"
STAGE_SCRIPT = REPO_ROOT / "scripts" / "stage_docs_site.py"
LINK_CHECKER = REPO_ROOT / "scripts" / "check_built_docs.py"
HEADING_RE = re.compile(r"^#{2,4}\s+(.+?)\s*$", re.MULTILINE)
MARKDOWN_LINK_RE = re.compile(r"]\(([^)\s]+\.md(?:#[^)\s]+)?)\)")
OWN_REPO_MARKDOWN_RE = re.compile(
    r"https://github\.com/michaeljabbour/amplifier-app-tui/blob/[^/]+/[^)\s]+\.md"
)


def _manifest() -> dict[str, object]:
    data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def _documents() -> list[dict[str, str]]:
    raw = _manifest()["documents"]
    assert isinstance(raw, list)
    documents: list[dict[str, str]] = []
    for item in raw:
        assert isinstance(item, dict)
        documents.append({str(key): str(value) for key, value in item.items()})
    return documents


def _stage(tmp_path: Path) -> Path:
    output = tmp_path / "site"
    result = subprocess.run(
        [sys.executable, str(STAGE_SCRIPT), "--output", str(output)],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    return output


def test_source_manifest_has_unique_real_sources_routes_and_outputs() -> None:
    documents = _documents()
    sources = [item["source"] for item in documents]
    routes = [item["route"] for item in documents]
    outputs = [item["output"] for item in documents]

    assert len(sources) == len(set(sources))
    assert len(routes) == len(set(routes))
    assert len(outputs) == len(set(outputs))
    assert all(route.startswith("/") and route.endswith("/") for route in routes)
    assert all((REPO_ROOT / source).is_file() for source in sources)


def test_staged_pages_preserve_every_source_section_and_rewrite_doc_links(tmp_path: Path) -> None:
    staged = _stage(tmp_path)
    for document in _documents():
        source = (REPO_ROOT / document["source"]).read_text(encoding="utf-8")
        output = (staged / document["output"]).read_text(encoding="utf-8")
        for heading in HEADING_RE.findall(source):
            assert re.search(rf"^#{{2,4}}\s+{re.escape(heading)}\s*$", output, re.MULTILINE), (
                f"{document['source']} heading missing from {document['route']}: {heading}"
            )
        local_markdown = [
            link for link in MARKDOWN_LINK_RE.findall(output) if not link.startswith("https://")
        ]
        assert not local_markdown, (
            f"{document['route']} retained repo-relative Markdown links: {local_markdown!r}"
        )


def test_staged_search_index_covers_curated_and_source_content(tmp_path: Path) -> None:
    staged = _stage(tmp_path)
    search_index = json.loads((staged / "search-index.json").read_text())

    assert isinstance(search_index, list)
    assert len(search_index) > 100
    required_fields = {"title", "section", "route", "anchor", "description", "text"}
    assert all(
        isinstance(entry, dict) and required_fields <= entry.keys() for entry in search_index
    )
    assert any(entry["route"] == "/configuration/" for entry in search_index)
    assert any(entry["route"] == "/development/architecture/" for entry in search_index)
    assert any("reset --dry-run" in entry["text"].lower() for entry in search_index)
    assert any("amplifier-tui" in entry["text"] for entry in search_index)
    assert any("~/.amplifier/keys.env" in entry["text"] for entry in search_index)
    assert any("<project>/.amplifier/settings.yaml" in entry["text"] for entry in search_index)
    assert all("{{ site.data.product" not in entry["text"] for entry in search_index)


def test_reader_pages_do_not_send_repo_guidance_back_to_github() -> None:
    offenders: dict[str, list[str]] = {}
    for path in sorted(DOCS_SITE.rglob("*.md")):
        matches = OWN_REPO_MARKDOWN_RE.findall(path.read_text(encoding="utf-8"))
        if matches:
            offenders[path.relative_to(REPO_ROOT).as_posix()] = matches
    assert not offenders, f"reader-facing pages link to mapped repo Markdown: {offenders!r}"


def test_llms_indexes_every_source_synchronized_route() -> None:
    llms = (DOCS_SITE / "llms.txt").read_text(encoding="utf-8")
    baseurl = "/amplifier-app-tui"
    for document in _documents():
        assert f"- {baseurl}{document['route']} —" in llms
    assert f"- {baseurl}/engineering/ —" in llms


def test_docs_product_identity_matches_runtime_and_package_metadata() -> None:
    product = json.loads(PRODUCT_PATH.read_text(encoding="utf-8"))
    pyproject = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))

    assert product == {
        "display_name": DISPLAY_NAME,
        "brand_name": BRAND_NAME,
        "command": EXECUTABLE_NAME,
        "package": DISTRIBUTION_NAME,
        "repository": REPOSITORY_SLUG,
    }
    assert product["package"] == pyproject["project"]["name"]
    assert product["command"] in pyproject["project"]["scripts"]


def test_built_link_checker_accepts_routes_and_rejects_missing_anchors(tmp_path: Path) -> None:
    good = tmp_path / "good"
    (good / "guide").mkdir(parents=True)
    (good / "index.html").write_text(
        '<a href="/amplifier-app-tui/guide/#ready">Guide</a>', encoding="utf-8"
    )
    (good / "guide" / "index.html").write_text('<h2 id="ready">Ready</h2>', encoding="utf-8")
    passed = subprocess.run(
        [sys.executable, str(LINK_CHECKER), str(good), "--baseurl", "/amplifier-app-tui"],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert passed.returncode == 0, passed.stdout + passed.stderr

    bad = tmp_path / "bad"
    (bad / "guide").mkdir(parents=True)
    (bad / "index.html").write_text('<a href="/guide/#missing">Guide</a>', encoding="utf-8")
    (bad / "guide" / "index.html").write_text('<h2 id="ready">Ready</h2>', encoding="utf-8")
    failed = subprocess.run(
        [sys.executable, str(LINK_CHECKER), str(bad)],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert failed.returncode == 1
    assert "missing anchor" in failed.stdout
