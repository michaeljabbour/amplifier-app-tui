"""Static contract for the GitHub Pages documentation shell."""

from __future__ import annotations

import re
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
DOCS_SITE = REPO_ROOT / "docs-site"
PAGES_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "pages.yml"
SITE_BASEURL = "/amplifier-app-tui"

REQUIRED_FILES = [
    "docs-site/_config.yml",
    "docs-site/_layouts/default.html",
    "docs-site/assets/site.css",
    "docs-site/index.md",
    "docs-site/setup.md",
    "docs-site/quickstart.md",
    "docs-site/update-reset.md",
    "docs-site/troubleshooting.md",
    "docs-site/using-the-tui.md",
    "docs-site/configuration.md",
    "docs-site/reference.md",
    "docs-site/development.md",
    "docs-site/llms.txt",
    ".github/workflows/pages.yml",
]

DOC_PAGES = [
    "index.md",
    "setup.md",
    "quickstart.md",
    "update-reset.md",
    "using-the-tui.md",
    "configuration.md",
    "reference.md",
    "troubleshooting.md",
    "development.md",
]

NAV_GROUPS = [
    "Getting started",
    "Using the TUI",
    "Configuration",
    "Reference",
    "Troubleshooting",
    "Development",
]

OFFICIAL_PAGES_ACTIONS = [
    "actions/checkout",
    "actions/configure-pages",
    "actions/jekyll-build-pages",
    "actions/upload-pages-artifact",
    "actions/deploy-pages",
]

SHA_RE = re.compile(r"^[0-9a-f]{40}$")


def _text(relative_path: str) -> str:
    return (REPO_ROOT / relative_path).read_text(encoding="utf-8")


def _frontmatter(path: Path) -> dict[str, object]:
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n"), (
        f"{path.relative_to(REPO_ROOT)} must start with YAML frontmatter"
    )
    raw = text.split("---", 2)[1]
    data = yaml.safe_load(raw)
    assert isinstance(data, dict), f"{path.relative_to(REPO_ROOT)} frontmatter must be a mapping"
    return data


def test_docs_site_required_files_exist() -> None:
    missing = [
        relative_path
        for relative_path in REQUIRED_FILES
        if not (REPO_ROOT / relative_path).is_file()
    ]
    assert not missing, f"missing required docs-site files: {missing!r}"


def test_docs_site_default_layout_has_required_shell() -> None:
    layout = _text("docs-site/_layouts/default.html")
    css = _text("docs-site/assets/site.css")

    assert "{{ content }}" in layout
    assert "<header" in layout
    assert "<nav" in layout
    assert "<main" in layout
    assert "assets/site.css" in layout
    assert "skip-link" in layout
    for group in NAV_GROUPS:
        assert group in layout
    for page in DOC_PAGES:
        expected_href = "/" if page == "index.md" else f"/{page.removesuffix('.md')}/"
        assert expected_href in layout

    assert "copy" in css.lower()
    assert "pre" in css and "code" in css
    assert "<script" not in layout.lower()


def test_docs_site_config_uses_project_pages_baseurl() -> None:
    config = yaml.safe_load(_text("docs-site/_config.yml"))
    assert isinstance(config, dict)
    assert config.get("baseurl") == SITE_BASEURL


def test_docs_site_navigation_reaches_setup() -> None:
    index = _text("docs-site/index.md")
    layout = _text("docs-site/_layouts/default.html")

    assert "setup.md" not in index
    assert "{{ '/setup/' | relative_url }}" in index
    assert "Setup" in layout
    assert "/setup/" in layout


def test_docs_site_pages_do_not_link_to_source_markdown_routes() -> None:
    link_re = re.compile(r"(?:href=\"|]\()([^\" )]+\.md(?:[#?][^\" )]*)?)")

    for page in DOC_PAGES:
        text = (DOCS_SITE / page).read_text(encoding="utf-8")
        source_markdown_links = link_re.findall(text)
        assert not source_markdown_links, (
            f"{page} links to source markdown paths instead of published routes: "
            f"{source_markdown_links!r}"
        )


def test_docs_site_pages_have_default_layout_and_titles() -> None:
    for page in DOC_PAGES:
        frontmatter = _frontmatter(DOCS_SITE / page)
        assert frontmatter.get("layout") == "default", f"{page} must use the default layout"
        title = frontmatter.get("title")
        assert isinstance(title, str) and title.strip(), f"{page} must have a title"


def test_llms_txt_is_included_at_site_root() -> None:
    config = yaml.safe_load(_text("docs-site/_config.yml"))
    assert isinstance(config, dict)
    assert "llms.txt" in config.get("include", [])

    llms = _text("docs-site/llms.txt")
    for page in DOC_PAGES:
        path = (
            f"{SITE_BASEURL}/"
            if page == "index.md"
            else f"{SITE_BASEURL}/{page.removesuffix('.md')}/"
        )
        assert f"- {path} —" in llms


def test_pages_workflow_builds_docs_site_with_official_actions() -> None:
    workflow = _text(".github/workflows/pages.yml")

    assert "permissions:" in workflow
    assert "contents: read" in workflow
    assert "pages: write" in workflow
    assert "id-token: write" in workflow
    assert "concurrency:" in workflow
    assert "github-pages" in workflow
    assert "source: docs-site" in workflow
    assert "destination: _site" in workflow
    assert "upload-pages-artifact" in workflow
    assert "deploy-pages" in workflow

    for action in OFFICIAL_PAGES_ACTIONS:
        match = re.search(rf"uses:\s*{re.escape(action)}@([^\s#]+)", workflow)
        assert match is not None, f"pages workflow must use {action}"
        assert SHA_RE.match(match.group(1)), f"{action} must be pinned to a full commit SHA"


def test_docs_site_has_no_external_assets_or_scripts() -> None:
    shell_files = [
        DOCS_SITE / "_layouts" / "default.html",
        DOCS_SITE / "assets" / "site.css",
        DOCS_SITE / "_config.yml",
    ]
    combined = "\n".join(path.read_text(encoding="utf-8") for path in shell_files)

    assert "<script" not in combined.lower()
    assert "@import" not in combined.lower()
    assert "http://" not in combined.lower()
    assert "https://" not in combined.lower()
    assert "cdn" not in combined.lower()
