"""Static contract for the GitHub Pages documentation shell."""

from __future__ import annotations

import re
from pathlib import Path

import yaml

from amplifier_app_tui.install_contract import PUBLIC_SOURCE_INSTALL_COMMAND

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

# The public support story (docs-site plan, "Final done definition"): these three
# commands are the entire public contract. README and the core getting-started
# pages must all show every one of them.
THREE_COMMAND_SUPPORT_STORY = (
    "amplifier-tui",
    "amplifier-tui update",
    "amplifier-tui reset",
)

SUPPORT_STORY_PAGES = [
    "README.md",
    "docs-site/setup.md",
    "docs-site/update-reset.md",
    "docs-site/reference.md",
]

# Commands that have never existed in this codebase. A previous agent
# hallucinated `amplifier-tui setup`; guard against it recurring anywhere.
NONEXISTENT_COMMANDS = ["amplifier-tui setup"]


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


def _blocks(text: str) -> list[str]:
    """Split markdown text into blank-line-delimited blocks (~paragraphs/sections).

    Used to check that two related facts are stated *together* in the same
    place, rather than merely present somewhere on the same long, multi-topic
    page.
    """
    return [block for block in re.split(r"\n\s*\n", text) if block.strip()]


def _any_block_matches(text: str, *patterns: str) -> bool:
    """True if some single block in *text* matches every regex in *patterns*.

    Each pattern is matched case-insensitively with ``re.search`` against the
    block. Use word-bounded patterns (e.g. ``r"\\b1\\b"``) for bare numbers so
    a lone ``1`` does not spuriously match inside ``100``.
    """
    compiled = [re.compile(pattern, re.IGNORECASE) for pattern in patterns]
    return any(all(pattern.search(block) for pattern in compiled) for block in _blocks(text))


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


def test_docs_site_setup_shows_public_source_install_command() -> None:
    setup = _text("docs-site/setup.md")

    assert PUBLIC_SOURCE_INSTALL_COMMAND in setup
    assert "uv tool install amplifier-app-tui" not in setup
    assert "--launch" not in setup


def test_docs_site_pages_do_not_link_to_source_markdown_routes() -> None:
    """Docs-site pages must not link to source markdown as if it were a published route.

    A Jekyll build under ``docs-site/`` publishes ``setup.md`` at ``/setup/``, not at
    ``/setup.md`` — so a relative or site-local link ending in ``.md`` (e.g.
    ``docs/USER-GUIDE.md`` or ``./setup.md``) is always a broken link on the published
    site and stays forbidden.

    Carve-out: an ABSOLUTE ``https://github.com/...`` URL ending in ``.md`` is exempt.
    Content pages legitimately need to deep-link to the internal engineering docs (e.g.
    ``docs/USER-GUIDE.md``, ``docs/SETTINGS.md``) that live only as source markdown in
    the repository and are not, and never will be, routes this Jekyll site can serve —
    the GitHub blob URL is the only correct way to reach them. Only that absolute
    ``https://github.com/`` form is allowed; every other ``.md`` link remains forbidden.
    """
    link_re = re.compile(r"(?:href=\"|]\()([^\" )]+\.md(?:[#?][^\" )]*)?)")
    allowed_absolute_github_re = re.compile(r"^https://github\.com/")

    for page in DOC_PAGES:
        text = (DOCS_SITE / page).read_text(encoding="utf-8")
        source_markdown_links = [
            link for link in link_re.findall(text) if not allowed_absolute_github_re.match(link)
        ]
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


def test_docs_site_documents_the_three_command_support_story() -> None:
    """README and the core getting-started pages must show all three support commands.

    Acceptance criteria (docs-site plan, "Final done definition"): the public support
    story is consistently `amplifier-tui` / `amplifier-tui update` / `amplifier-tui
    reset` everywhere a new user is likely to land first: README, setup, update/reset,
    and reference.

    NOTE (TDD): expected to fail until the Getting Started / Reference content lanes
    land `amplifier-tui update` and `amplifier-tui reset` on every listed page.
    """
    missing: dict[str, list[str]] = {}
    for relative_path in SUPPORT_STORY_PAGES:
        text = _text(relative_path)
        absent = [command for command in THREE_COMMAND_SUPPORT_STORY if command not in text]
        if absent:
            missing[relative_path] = absent

    assert not missing, f"pages missing the three-command public support story: {missing!r}"


def test_docs_site_distinguishes_app_update_from_bundle_refresh() -> None:
    """`amplifier-tui update` updates the app; `bundle refresh` is separate/advanced.

    Acceptance criteria (docs-site plan, Tasks 4/5/7/11): the top-level `amplifier-tui
    update` command must be described as updating the app itself, while `amplifier-tui
    bundle refresh` -- a distinct, advanced command -- must be described as refreshing
    mounted bundle/module source caches. Both `update-reset.md` and `reference.md` must
    mention `bundle refresh` at all (today neither does). No docs-site page may revert
    to the old, wrong claim that top-level `update` itself refreshes bundles/modules.

    NOTE (TDD): expected to fail until the Getting Started and Reference content lanes
    add `bundle refresh` and the app-update-vs-cache-refresh distinction.
    """
    pages_that_must_distinguish = ["docs-site/update-reset.md", "docs-site/reference.md"]

    for relative_path in pages_that_must_distinguish:
        text = _text(relative_path)
        assert "bundle refresh" in text, f"{relative_path} must mention `bundle refresh`"
        assert _any_block_matches(text, r"amplifier-tui update", r"\bapp\b"), (
            f"{relative_path} must state that `amplifier-tui update` updates the app itself"
        )
        assert _any_block_matches(text, r"bundle refresh", r"\bcache\b"), (
            f"{relative_path} must state that `amplifier-tui bundle refresh` refreshes "
            "bundle/module source caches"
        )

    for page in DOC_PAGES:
        text = (DOCS_SITE / page).read_text(encoding="utf-8")
        for block in _blocks(text):
            lowered = block.lower()
            if "amplifier-tui update" not in lowered or "bundle refresh" in lowered:
                continue
            claims_refresh = re.search(r"\brefresh(?:es|ing)?\b", lowered)
            claims_bundle_or_module = re.search(r"\b(?:bundle|module)s?\b", lowered)
            assert not (claims_refresh and claims_bundle_or_module), (
                f"{page} incorrectly implies top-level `update` refreshes bundles/modules "
                f"(that is `amplifier-tui bundle refresh`'s job): {block!r}"
            )


def test_docs_site_configuration_documents_provider_priority_and_fallback() -> None:
    """`configuration.md` must teach the priority model, not just mention the word.

    Acceptance criteria (docs-site plan, Task 6): the page must make clear that
    provider *priority* selection is lower-number-wins, must name the bundled
    Anthropic provider's fallback priority as `100`, and must show a user-configured
    provider at priority `1` winning over that fallback -- the concrete example that
    answers "why is Anthropic still being used?" instead of "export ANTHROPIC_API_KEY".

    NOTE (TDD): expected to fail until the Configuration content lane lands; today
    the page does not mention priority, fallback, or `100` at all.
    """
    text = _text("docs-site/configuration.md")

    assert _any_block_matches(text, r"\blower\b", r"\bpriority\b", r"\bwins?\b"), (
        "configuration.md must explain that provider selection is lower-priority-wins"
    )
    assert _any_block_matches(text, r"\banthropic\b", r"\b100\b", r"\bfallback\b"), (
        "configuration.md must name the bundled Anthropic fallback priority `100`"
    )
    assert _any_block_matches(text, r"\bpriority\b", r"\b1\b"), (
        "configuration.md must show a user-configured provider set to priority `1`"
    )
    assert _any_block_matches(text, r"\b1\b", r"\b100\b"), (
        "configuration.md must show priority `1` alongside the fallback priority `100` "
        "so a reader can see the lower value winning"
    )


def test_docs_site_pages_do_not_document_nonexistent_commands() -> None:
    """Guard against hallucinated CLI surface: `amplifier-tui setup` does not exist.

    A previous agent invented an `amplifier-tui setup` subcommand that has never
    existed in this codebase -- the real first-run entry point is bare
    `amplifier-tui`, and read-only verification is `amplifier-tui doctor`.
    """
    offenders: dict[str, list[str]] = {}
    for page in DOC_PAGES:
        text = (DOCS_SITE / page).read_text(encoding="utf-8")
        found = [command for command in NONEXISTENT_COMMANDS if command in text]
        if found:
            offenders[page] = found

    assert not offenders, f"docs-site pages document nonexistent commands: {offenders!r}"
