---
layout: default
title: Development
permalink: /development/
---

Contributor quick start for working on Amplifier TUI from a repository checkout. The
authoritative guides live in the repository — `AGENTS.md` and `docs/DEVELOPMENT.md`, both
linked at the bottom of this page — and this page is a faithful short form of them. Where
they disagree with anything here, the repository wins.

If you only want to *use* the app, start at [Setup]({{ '/setup/' | relative_url }}) instead;
nothing on this page is required to run it.

## What you need

- macOS, Linux, or WSL.
- Python 3.12 or newer. `uv` provisions a compatible interpreter for you, so you do not
  have to install one first.
- `git` and `uv`.

## Clone and install

```sh
git clone https://github.com/michaeljabbour/amplifier-app-tui
cd amplifier-app-tui
uv sync
```

`uv sync` installs everything, including the pinned `amplifier-core` and
`amplifier-foundation` dependencies. Inside a clone, prefix app commands with `uv run`.

## Run what you just built

```sh
uv run amplifier-tui --demo     # scripted session — no bundle, no network, no credentials
uv run amplifier-tui doctor     # setup checkup; exit 0 = ready, exit 1 = findings exist
```

`--demo` is the fastest way to eyeball a UI change: it drives the app's scripted
`DemoRuntime` through the real UI, so you see the same widgets, events, and footer a real
session produces without touching a provider. It is a flag on the top-level command, not a
subcommand.

## Tests

```sh
uv run pytest -q                                                 # full suite
uv run pytest tests/test_ui_reducer_outcomes.py                  # one file
uv run pytest -q -k "steer"                                      # by keyword
uv run pytest -q --cov=src/amplifier_app_tui --cov-report=term   # with coverage
```

**The default suite is fully offline.** It needs no network, no API key, and no provider
account — cloning and running `uv run pytest -q` is the whole setup. If a test you are
writing needs credentials or a live service, it is designed wrong; `tests/test_runtime_offline.py`
shows how the provider side is faked.

One tier sits outside that default gate: `tests/forge/` drives the real shipped binary
through a real PTY. It is marked `forge` and excluded from `uv run pytest -q`, so it never
affects the normal run.

```sh
uv run pytest -q -m forge tests/forge/
```

## The gate

CI runs this sequence:

```sh
uv sync --frozen
ruff check .
ruff format --check .
pyright src/
pytest -q
```

From a clone that is:

```sh
uv sync --frozen
uv run ruff check .
uv run ruff format --check .
uv run pyright src/
uv run pytest -q
```

Passing all of those locally is the best local signal, but it is not a guarantee: CI's
`pytest` step additionally enforces a coverage floor (85%, via `--cov-fail-under=85`) that a
plain local `pytest -q` never checks, and reruns the performance and snapshot tests
uninstrumented in a separate step, because coverage tracing is slow enough to blow their
timing budgets. `pyright` runs in `basic` mode and is a hard gate at zero errors. PR titles
are linted for Conventional Commits format, because squash-merge titles become the permanent
history.

## Rules the code holds itself to

- **Layering** — `ui/` → `model/` → `kernel/`. Only `kernel/` touches amplifier-core and
  foundation, and `kernel/` never imports Textual.
- **Keymap is data** — new keys go in the `ui/keymap.py` table, which also drives the
  on-screen footer hints, so advertised keys cannot drift from working keys.
- **Goldens travel with the change** — a transcript-rendering change regenerates
  `tests/goldens/` in the same commit (`uv run python tests/goldens/regen.py`); the golden
  diff is the review.
- **Bundle byte-identity** — repo-root `bundle.md` and the packaged
  `src/amplifier_app_tui/data/bundles/tui.md` must stay byte-identical; after editing one,
  copy it over the other.
- **Never mount printing hooks** — they write ANSI escapes to stdout and corrupt the
  Textual screen.

## Working on this documentation site

The site you are reading is plain Markdown under `docs-site/`, built by GitHub Pages with
GitHub's own Jekyll action (`.github/workflows/pages.yml`, `source: docs-site`). There is no
local docs toolchain and no docs dependency in `pyproject.toml` or `uv.lock` — nothing to
install and nothing to build before editing a page. Push to `main` and Pages publishes it.

Conventions to keep when you edit a page:

- Every page opens with YAML frontmatter carrying the default layout and a title.
- Internal links go through Jekyll's `relative_url` filter so they keep working under the
  site's project base path. Never link to a `.md` file as if it were a published route —
  Jekyll serves `setup.md` at `/setup/`. Deep links into repository-only documents use
  their absolute GitHub URL instead.
- The shell is static on purpose: no JavaScript, no external fonts, no CDN assets.
- `llms.txt` is published at the site root as the agent-readable index of every page. Add
  an entry there whenever you add a page.

One offline test guards all of that:

```sh
uv run pytest -q tests/test_docs_site_contract.py
```

It checks that the required files exist, that frontmatter and titles are present, that the
navigation shell and page routes line up, that no page ships a script or an external asset,
that `llms.txt` lists every page, and that the documented command surface stays accurate.

## Before you open a pull request

- `uv run pytest -q` green, `uv run ruff check .` clean, `uv run ruff format --check .` clean,
  `uv run pyright src/` clean.
- New behavior has a test at the right layer.
- Layering rules hold.
- Rendering changed? Goldens regenerated in the same commit, diff reviewed.
- Key added? The `ui/keymap.py` table only — footer hints follow automatically.
- User-visible behavior changed? The user guide is updated and the strings match the design
  spec.
- Docs page added or renamed? `llms.txt` updated and the docs-site contract test green.

The complete checklist — including the SDK, event-boundary, and bundle-pin items — is in
the development guide below.

## Deeper references

These live in the repository, not on this site:

| Read | For |
|---|---|
| [AGENTS.md](https://github.com/michaeljabbour/amplifier-app-tui/blob/main/AGENTS.md) | the short contributor contract: quick commands and the non-negotiables |
| [docs/DEVELOPMENT.md](https://github.com/michaeljabbour/amplifier-app-tui/blob/main/docs/DEVELOPMENT.md) | the authoritative workflow: full test-suite map, goldens, bundle pins, PR checklist |
| [docs/ARCHITECTURE.md](https://github.com/michaeljabbour/amplifier-app-tui/blob/main/docs/ARCHITECTURE.md) | how it is built, module by module: boot, event pipeline, governance, persistence |
| [docs/DESIGN-SPEC.md](https://github.com/michaeljabbour/amplifier-app-tui/blob/main/docs/DESIGN-SPEC.md) | the behavioral spec the app is built to — authoritative for strings and states |

For the commands this site documents for users, see the
[reference]({{ '/reference/' | relative_url }}).
