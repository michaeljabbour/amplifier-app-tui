# Amplifier TUI docs site and simple setup implementation plan

**Status:** ready for execution. This plan covers the remaining documentation/setup work requested after the install/update/reset simplification branch.

**For execution:** use subagent-driven development with the parallel task groups below. Do not start from scratch; this branch already contains the verified install/update/reset/provider-fallback work.

## Goal

Give Amplifier TUI the same simple public setup feel as Claude Code:

```sh
curl -fsSL https://raw.githubusercontent.com/michaeljabbour/amplifier-app-tui/main/scripts/install.sh | bash
amplifier-tui
```

Then publish a complete, navigable GitHub Pages documentation site with:

- a simple setup page;
- clean docs index/navigation;
- comprehensive pages for install, quickstart, update/reset, usage, config, reference, troubleshooting, and development;
- an `llms.txt` index for agents;
- tests that protect the public command story: `amplifier-tui`, `amplifier-tui update`, `amplifier-tui reset`.

## Non-goals

- Do not change TUI runtime behavior.
- Do not redesign the app UI.
- Do not add MkDocs, Docusaurus, or another local docs build dependency unless a later reviewer explicitly rejects the static/Jekyll Pages path.
- Do not reintroduce `--launch` into public docs.
- Do not claim signed releases, PyPI distribution, native binaries, background updates, or platform release proof that does not exist.

## Repository facts verified before writing this plan

- `AGENTS.md` says to read `docs/DEVELOPMENT.md`, respect the `ui/ -> model/ -> kernel/` layering rule, and keep `bundle.md` byte-identical with `src/amplifier_app_tui/data/bundles/tui.md` when those files are edited.
- No `docs-site/` directory currently exists.
- No `.github/` directory is present in this checkout, despite some docs referring to CI workflow files. Treat Pages workflow creation as additive and do not alter any CI workflow unless one appears during execution.
- `pyproject.toml` has no docs-site dependencies. Keep it that way.
- Existing docs live in `docs/*.md`, with deep internal docs such as `docs/ARCHITECTURE.md`, `docs/DESIGN-SPEC.md`, `docs/SETTINGS.md`, `docs/USER-GUIDE.md`, and `docs/INSTALL.md`.
- Existing plan convention is `docs/plans/YYYY-MM-DD-<slug>.md` plus optional registration in `docs/plans/README.md`.
- Current install contract code has `SOURCE_INSTALL_COMMAND` as the longer `bash -o pipefail -c "curl --proto ... | bash -s --"` string, and `source_install_argv()` as the programmatic hardened argv used by update/reset repair.

## Chosen approach

Use a low-friction GitHub Pages site rooted at `docs-site/`:

- author docs as Markdown;
- use GitHub's `actions/jekyll-build-pages` in `.github/workflows/pages.yml` to render Markdown without adding Python/Node/Ruby dependencies to this repo;
- keep styles local and small under `docs-site/assets/site.css`;
- expose `docs-site/llms.txt` at the site root;
- keep the existing `docs/` directory as internal engineering documentation and link to it where useful.

This preserves the repo's Python toolchain and avoids putting a docs generator in `uv.lock`.

## Public install command policy

After this plan lands, there are two install commands with different jobs:

1. **Canonical public install command** shown first in README and setup docs:

   ```sh
   curl -fsSL https://raw.githubusercontent.com/michaeljabbour/amplifier-app-tui/main/scripts/install.sh | bash
   ```

2. **Hardened/review-first option** shown lower down in advanced install docs:

   ```sh
   bash -o pipefail -c "curl --proto '=https' --tlsv1.2 -fsSL https://raw.githubusercontent.com/michaeljabbour/amplifier-app-tui/main/scripts/install.sh | bash -s --"
   ```

   and/or:

   ```sh
   curl --proto '=https' --tlsv1.2 -fsSL https://raw.githubusercontent.com/michaeljabbour/amplifier-app-tui/main/scripts/install.sh -o install.sh
   less install.sh
   bash install.sh
   ```

The public command optimizes for readability and community convention. The hardened command remains available where exit-code strictness and review-first posture matter. Programmatic self-update/repair may keep using the existing hardened argv because it is not user-facing copy.

## Maximum-parallelism execution model

The dependency graph is:

```text
Task 1 baseline/contract decisions
  -> Task 2 docs-site scaffold
  -> Task 3 install command constants/tests

Task 2 -> Tasks 4-9 content pages in parallel
Task 3 -> Tasks 4, 10, 11
Tasks 4-9 -> Task 10 llms/index coherence
Tasks 2-10 -> Task 11 docs contract tests
Task 11 -> Task 12 final docs links and local verification
Task 12 -> Task 13 review/fix loop
```

Safe parallel fan-out after Tasks 1-3: assign one subagent per content lane (Tasks 4-9) plus one subagent for Pages workflow/static shell if Task 2 is not complete.

---

## Task 1: Establish constants, scope, and current docs inventory

**Files to inspect only:**

- `README.md`
- `docs/INSTALL.md`
- `docs/USER-GUIDE.md`
- `docs/SETTINGS.md`
- `docs/ARCHITECTURE.md`
- `docs/DESIGN-SPEC.md`
- `src/amplifier_app_tui/install_contract.py`
- `tests/test_source_installer.py`
- `tests/test_commands_doctor.py`
- `tests/test_update_cli.py`

**Work:**

1. Reconfirm that public docs no longer contain `--launch`.
2. List current occurrences of the long installer command.
3. Decide final names for install contract constants before editing. Recommended:
   - `PUBLIC_SOURCE_INSTALL_COMMAND` or make existing `SOURCE_INSTALL_COMMAND` the short public command;
   - `HARDENED_SOURCE_INSTALL_COMMAND` for the current pipefail/proto/tls wrapper;
   - keep `source_install_argv()` as the hardened argv for app-driven update/reset repair.
4. Confirm all places that display install/update repair guidance to a user use the public short command unless the message explicitly says "hardened" or "review-first".

**Acceptance:**

- A short note in the implementation summary identifies whether `SOURCE_INSTALL_COMMAND` was repurposed or a new public constant was added.
- No application behavior changes are made in this task.

---

## Task 2: Add the GitHub Pages docs shell

**Files to create:**

- `docs-site/_config.yml`
- `docs-site/_layouts/default.html`
- `docs-site/assets/site.css`
- `docs-site/index.md`
- `docs-site/setup.md`
- `docs-site/quickstart.md`
- `docs-site/update-reset.md`
- `docs-site/troubleshooting.md`
- `docs-site/using-the-tui.md`
- `docs-site/configuration.md`
- `docs-site/reference.md`
- `docs-site/development.md`
- `docs-site/llms.txt`
- `.github/workflows/pages.yml`

**Work:**

1. Create a minimal Jekyll-compatible static shell.
2. Use a single default layout with:
   - title/header;
   - left navigation grouped as Getting started, Using the TUI, Configuration, Reference, Troubleshooting, Development;
   - main content area;
   - copyable-looking command blocks via CSS only, no JavaScript requirement.
3. Keep CSS self-contained and plain. Do not fetch external fonts, scripts, analytics, or CDNs.
4. Configure Pages workflow with GitHub's official Pages actions:
   - checkout;
   - configure-pages;
   - jekyll-build-pages with `source: docs-site` and `destination: _site`;
   - upload-pages-artifact;
   - deploy-pages.
5. Add permissions and concurrency per GitHub Pages examples.
6. If a `.github/workflows/ci.yml` appears during execution, do not modify it; create only `pages.yml`.

**Acceptance:**

- `docs-site/index.md` renders as the docs landing page.
- `docs-site/setup.md` is reachable from the landing page and navigation.
- `docs-site/llms.txt` is copied to the site root by the Pages build.
- The workflow does not require local dependency changes.

---

## Task 3: Shorten the public install command without weakening app-driven update/reset

**Files likely modified:**

- `src/amplifier_app_tui/install_contract.py`
- `README.md`
- `docs/INSTALL.md`
- `docs/USER-GUIDE.md` if it repeats the install command
- `docs/DEVELOPMENT.md` only if it repeats public install/update copy
- `tests/test_source_installer.py`
- `tests/test_commands_doctor.py`
- `tests/test_update_cli.py`

**Work:**

1. Make the public command exactly:

   ```sh
   curl -fsSL https://raw.githubusercontent.com/michaeljabbour/amplifier-app-tui/main/scripts/install.sh | bash
   ```

2. Keep the hardened command available for advanced docs and programmatic flows:

   ```sh
   bash -o pipefail -c "curl --proto '=https' --tlsv1.2 -fsSL https://raw.githubusercontent.com/michaeljabbour/amplifier-app-tui/main/scripts/install.sh | bash -s --"
   ```

3. Keep update/reset reinstall execution on `source_install_argv()` unless there is a strong reason to change it. The app can use the hardened argv while docs show the short public command.
4. Update doctor/updater human-facing hints to prefer:

   ```sh
   amplifier-tui update
   amplifier-tui reset
   curl -fsSL .../install.sh | bash
   ```

5. Preserve hidden/deprecated `scripts/install.sh --launch` compatibility but keep it out of public docs and help if prior branch already did so.

**Tests:**

- Update or add tests so:
  - README contains the short public command.
  - `docs/INSTALL.md` contains the short public command near the top.
  - `docs-site/setup.md` contains the short public command.
  - Public docs do not contain `--launch`.
  - The hardened command appears only in advanced/review-first sections.
  - `source_install_argv()` still returns a pipefail/proto/tls hardened argv for programmatic update/reset.

**Acceptance:**

- Users see the simple command first everywhere public.
- Advanced users can still find the hardened/review-first option lower down.
- `amplifier-tui update` and `amplifier-tui reset` remain the recommended repair/update commands.

---

## Task 4: Write the Getting Started docs lane

**Files:**

- `docs-site/index.md`
- `docs-site/setup.md`
- `docs-site/quickstart.md`
- `docs-site/update-reset.md`
- `README.md`
- `docs/INSTALL.md`

**Work:**

1. Landing page should answer in this order:
   - what Amplifier TUI is;
   - install command;
   - run command;
   - demo command;
   - links to setup, quickstart, troubleshooting, reference.
2. `setup.md` should mirror Claude Code's feel:
   - documentation index callout pointing to `/llms.txt`;
   - system requirements;
   - one-line install;
   - first run with `amplifier-tui`;
   - demo with `amplifier-tui --demo`;
   - advanced install/review-first section lower down;
   - uninstall.
3. `quickstart.md` should be a first-session walkthrough:
   - `cd` into a project;
   - run `amplifier-tui`;
   - use demo if no key;
   - send first prompt;
   - steer while running;
   - open command palette;
   - where sessions are saved.
4. `update-reset.md` should keep the support story simple:
   - `amplifier-tui update` updates the app;
   - `amplifier-tui reset` repairs safely and preserves config/keys/sessions/local bundles;
   - `amplifier-tui reset --no-reinstall` for cleanup-only;
   - advanced `amplifier-tui bundle refresh` is for bundle/module cache refresh, not app update.
5. README should become shorter, with the same simple install block and links to the docs site/pages. Do not delete useful repo-local engineering links; push details down to docs pages.
6. `docs/INSTALL.md` can remain the repo-local deep install reference, but its top should match the simple setup story.

**Acceptance:**

- A new user can install and launch by reading only the first screen of README or `docs-site/setup.md`.
- No first-run path requires `amplifier-tui init`.
- No page suggests exporting `ANTHROPIC_API_KEY` as the fix for provider priority misrouting.

---

## Task 5: Write the Using the TUI docs lane

**Files:**

- `docs-site/using-the-tui.md`
- `docs/USER-GUIDE.md` only for small link/consistency edits

**Work:**

Cover the user-facing TUI features in plain language:

- transcript + composer;
- modes and trust posture;
- steering and queued steering;
- approvals;
- subagent lanes;
- rewind/checkpoints;
- sessions/resume;
- command palette;
- copying text;
- demo mode.

Prefer short sections with links to `docs/USER-GUIDE.md` for exhaustive detail. The public docs site should not become a duplicate 40k-word user guide.

**Acceptance:**

- Page explains core workflows without requiring architecture knowledge.
- Page links to `docs/USER-GUIDE.md` for complete keybindings/commands.
- Page uses current command names: `bundle refresh`, not top-level `update`, for cache/module refresh.

---

## Task 6: Write the Configuration docs lane

**Files:**

- `docs-site/configuration.md`
- `docs/SETTINGS.md` only for small link/consistency edits

**Work:**

Cover:

- config location: `~/.amplifier/`, project `.amplifier/`, local ignored settings;
- credentials: environment variables and `keys.env`;
- providers and priorities, including the important rule that user-configured vLLM/Kimi should win by using a lower priority than the packaged fallback;
- bundled Anthropic is fallback priority `100` after the existing branch;
- routing matrices;
- bundles and overlays;
- allowed/denied dirs;
- where to find the full settings reference.

**Acceptance:**

- The page makes it clear that provider priority, not adding an Anthropic key, is the fix when the intended provider should win.
- The page links to `docs/SETTINGS.md` for exhaustive schema detail.
- No secrets are shown inline except placeholder environment variable names.

---

## Task 7: Write the Reference docs lane

**Files:**

- `docs-site/reference.md`
- Possibly `docs-site/cli.md`, `docs-site/keybindings.md`, or `docs-site/slash-commands.md` only if `reference.md` becomes too long; keep task count practical and prefer one page unless it is unreadable.

**Work:**

Reference page should include compact tables for:

- public support commands:
  - `amplifier-tui`;
  - `amplifier-tui update`;
  - `amplifier-tui reset`.
- common CLI commands:
  - `--demo`;
  - `doctor`;
  - `sessions` / `resume`;
  - `run` and JSON/JSONL modes;
  - `bundle list/show/use/refresh/warm`;
  - `routing manage/use`;
  - `allowed-dirs` / `denied-dirs`.
- slash commands and palette overview;
- core keybindings;
- file locations;
- SDK/headless JSONL contract.

**Acceptance:**

- Top of reference still reinforces the three-command public support story.
- Advanced commands are discoverable but not presented as required setup.
- `bundle refresh` is documented as advanced cache refresh.

---

## Task 8: Write Troubleshooting docs lane

**Files:**

- `docs-site/troubleshooting.md`
- `docs/INSTALL.md` only for link/consistency edits if needed
- `README.md` only for a short troubleshooting link if needed

**Work:**

Troubleshooting page should include concise symptoms and fixes:

- `amplifier-tui: command not found`;
- install download failed;
- uv missing/broken;
- Python 3.12 requirement;
- provider credential missing;
- wrong provider selected / Anthropic fallback selected unexpectedly;
- Kimi/vLLM priority example;
- reset safely;
- exact executable path via `"$(uv tool dir --bin)/amplifier-tui"`;
- when to run `doctor`;
- when to run `bundle refresh`.

**Acceptance:**

- It separates install success from runtime/provider failure.
- It never says a missing Anthropic key is always the right fix.
- It tells users when to use `amplifier-tui reset` vs `amplifier-tui bundle refresh`.

---

## Task 9: Write Development docs lane

**Files:**

- `docs-site/development.md`
- `docs/DEVELOPMENT.md` only for a small public-docs link if desired

**Work:**

Development page should be public-facing but concise:

- clone and `uv sync`;
- `uv run amplifier-tui --demo`;
- test gates:
  - `uv run ruff check .`;
  - `uv run pyright src/`;
  - `uv run pytest -q`;
- docs-site editing workflow;
- Pages workflow overview;
- links to `docs/DEVELOPMENT.md`, `docs/ARCHITECTURE.md`, and `docs/DESIGN-SPEC.md`.

**Acceptance:**

- Development page does not duplicate the whole internal development guide.
- It states that default tests are offline and credentials-free.
- It notes that docs site is static/Jekyll via GitHub Pages and has no repo-local docs dependency.

---

## Task 10: Add `llms.txt` and docs index coherence

**Files:**

- `docs-site/llms.txt`
- `docs-site/index.md`
- `docs-site/setup.md`
- possibly root `llms.txt` only if the owner wants raw GitHub discovery outside the Pages site. Default: do not create root `llms.txt`; expose it through Pages at `/llms.txt`.

**Work:**

`llms.txt` should be a plain text/Markdown-style index for agents, modeled after Claude Code's pattern:

```text
# Amplifier TUI Documentation

Use this file to discover all available pages before exploring further.

## Getting started
- Overview: /
- Setup: /setup/
- Quickstart: /quickstart/
- Update and reset: /update-reset/

## Using Amplifier TUI
- Using the TUI: /using-the-tui/
- Configuration: /configuration/
- Reference: /reference/
- Troubleshooting: /troubleshooting/
- Development: /development/

## Source repository references
- README: https://github.com/michaeljabbour/amplifier-app-tui/blob/main/README.md
- Install guide: https://github.com/michaeljabbour/amplifier-app-tui/blob/main/docs/INSTALL.md
- User guide: https://github.com/michaeljabbour/amplifier-app-tui/blob/main/docs/USER-GUIDE.md
- Settings: https://github.com/michaeljabbour/amplifier-app-tui/blob/main/docs/SETTINGS.md
- Architecture: https://github.com/michaeljabbour/amplifier-app-tui/blob/main/docs/ARCHITECTURE.md
- Design spec: https://github.com/michaeljabbour/amplifier-app-tui/blob/main/docs/DESIGN-SPEC.md
```

Use relative site URLs for Pages content and absolute GitHub URLs for source repository docs.

**Acceptance:**

- Every docs-site page appears in `llms.txt`.
- Every link in the navigation appears in `llms.txt` or the landing page.
- `setup.md` has a visible Documentation Index callout pointing to `/llms.txt`.

---

## Task 11: Add docs contract tests

**Files to create/modify:**

- `tests/test_docs_site_contract.py` new
- `tests/test_source_installer.py` update existing install command assertions
- `tests/test_commands_doctor.py` / `tests/test_update_cli.py` update if install constant names change

**Work:**

Add offline tests that parse files as text. Keep them simple; no Jekyll build in pytest.

Recommended assertions in `tests/test_docs_site_contract.py`:

1. Required docs-site files exist:
   - `docs-site/index.md`
   - `docs-site/setup.md`
   - `docs-site/quickstart.md`
   - `docs-site/update-reset.md`
   - `docs-site/using-the-tui.md`
   - `docs-site/configuration.md`
   - `docs-site/reference.md`
   - `docs-site/troubleshooting.md`
   - `docs-site/development.md`
   - `docs-site/llms.txt`
2. Public install command appears in README, `docs/INSTALL.md`, and `docs-site/setup.md`.
3. Public pages do not contain `--launch`.
4. `llms.txt` lists every docs-site page.
5. Public support story appears in README and docs-site setup/update/reset/reference pages:
   - `amplifier-tui`
   - `amplifier-tui update`
   - `amplifier-tui reset`
6. Top-level `amplifier-tui update` is described as app update, while `amplifier-tui bundle refresh` is described as bundle/module cache refresh.
7. `docs-site/configuration.md` mentions provider priority and fallback priority `100`.
8. Pages workflow exists and references `docs-site`.

Also update source installer tests:

- `test_documented_install_and_update_commands_use_the_shared_contract` should be split or renamed so it accepts both:
  - short public command in public docs;
  - hardened command in advanced/review-first docs or argv tests.
- Keep `test_documented_pipefail_wrapper_propagates_download_failure`, but scope it to the hardened command instead of the public command.

**Acceptance:**

- New docs tests fail if someone reintroduces `--launch` into public docs.
- New docs tests fail if public docs drift back to the long installer command as the first/canonical setup path.
- New docs tests fail if `llms.txt` omits a page.

---

## Task 12: Final linking, README/index cleanup, and local verification

**Files likely modified:**

- `README.md`
- `docs/INSTALL.md`
- `docs/USER-GUIDE.md`
- `docs/DEVELOPMENT.md`
- `docs/plans/README.md` if registering this plan is desired

**Work:**

1. Add a short README docs section near the top:
   - Setup docs page once Pages URL is known, or relative `docs-site/setup.md` until Pages is enabled.
   - `llms.txt` once Pages URL is known, or relative `docs-site/llms.txt` until Pages is enabled.
2. Keep README install block very short.
3. Avoid duplicating the new docs site inside README.
4. Optionally add this plan to `docs/plans/README.md` with status `planned` or `ready for execution`.
5. Run formatting/lint only where relevant:
   - Markdown does not need ruff format.
   - Python tests/code changed for constants should pass ruff/pyright.

**Verification commands:**

```sh
uv run ruff check .
uv run pyright src/
uv run pytest -q tests/test_docs_site_contract.py tests/test_source_installer.py tests/test_commands_doctor.py tests/test_update_cli.py
uv run pytest -q
```

If the executor changes only docs/tests and no Python production code, still run the focused pytest set plus `ruff check .`; run full suite before final handoff.

**Acceptance:**

- Focused docs/install/update tests pass.
- Full repo gate passes, or any unrelated failure is isolated, explained, and reviewed before claiming done.

---

## Task 13: Review/fix loop

**Parallel review recommended:**

Run two independent reviews after implementation:

1. **Spec/docs contract review**
   - Verify the user request is met: Claude-Code-style setup feel, docs index, clean navigation, complete Pages docs, `llms.txt`, short command, public support story.
   - Check for invented release/platform claims.
   - Check `--launch` is absent from public docs.

2. **Code quality/test review**
   - Verify constants are named clearly.
   - Verify app-driven update/reset still use the intended hardened argv if changed.
   - Verify tests are not brittle, networked, or dependent on Jekyll.
   - Verify Pages workflow is minimal and scoped.

Fix review failures, then rerun:

```sh
uv run ruff check .
uv run pyright src/
uv run pytest -q
```

**Acceptance:**

- Both reviews pass.
- Final summary names changed files, tests run, and any deliberate deviations from this plan.

## Suggested subagent assignment

After Tasks 1-3 are done, use maximum safe parallelism:

- Agent A: Task 4 Getting Started pages + README/INSTALL simplification.
- Agent B: Task 5 Using the TUI page.
- Agent C: Task 6 Configuration page.
- Agent D: Task 7 Reference page.
- Agent E: Task 8 Troubleshooting page.
- Agent F: Task 9 Development page.
- Agent G: Task 10 `llms.txt` and navigation/index coherence.
- Agent H: Task 11 docs contract tests.

Coordinator owns merge/conflict resolution, final consistency pass, and full gate.

## Final done definition

The work is done only when all of the following are true:

- README and setup docs show this first:

  ```sh
  curl -fsSL https://raw.githubusercontent.com/michaeljabbour/amplifier-app-tui/main/scripts/install.sh | bash
  amplifier-tui
  ```

- Hardened/review-first install remains available lower down, not as the default public command.
- Public support story is consistently:

  ```sh
  amplifier-tui
  amplifier-tui update
  amplifier-tui reset
  ```

- GitHub Pages docs exist under `docs-site/` with clean navigation.
- `docs-site/llms.txt` indexes every public docs page.
- Tests protect install command, `llms.txt`, and support-story contracts.
- No public docs advertise `--launch`.
- `uv run ruff check .`, `uv run pyright src/`, and `uv run pytest -q` pass.
