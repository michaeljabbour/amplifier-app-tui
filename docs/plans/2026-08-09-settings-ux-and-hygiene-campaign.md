# Settings UX campaign + architecture hygiene (2026-08-09)

**Status:** 🔧 In progress (2026-08-09) — WS0, WS1 step 1 (strip_manager), WS2
(schema/service/trio), WS6 (drift CI + BACKLOG notes), and WS8 phase 1
(classification at the events boundary) implemented pending commit. Remaining:
WS1 steps 2–4, WS3 (panel), WS4, WS5, WS8 phase 2 (ErrorBlock), WS7 (separate).

Two halves, one campaign:

1. **Hygiene** — pay down the known watch-outs: `ui/app.py` at ~5× its ADR-0007
   budget, a layering contract that ADR-0007 calls "enforced by import-linter" but
   that does not exist in the repo, a 5497-line `main.py`, and upstream-drift
   checks that exist as scripts but run only when someone remembers them.
2. **Settings UX** — replace the numbered `click.prompt` control center and the
   text-only in-session `/config` with one settings domain model and one Textual
   panel, usable both as `amplifier-tui config` (standalone) and live inside a
   running session, with per-item honesty about *when* a change applies.

## Repository facts verified before writing this plan

- `ui/app.py` is **2723 lines**; ADR-0007 prescribes <500 and
  `docs/ARCHITECTURE.md:324` still claims "roughly double". `ui/app_support.py`
  adds 1360. Extraction precedent exists and shipped: `SessionOpsController`
  (issue #31), `LaneReducer` (#32), `transcript_render.py` split (#33),
  `directory_admin.py` / `config_admin.py` fake-host controller pattern.
- `main.py` is **5497 lines** holding nearly all interactive CLI flow code
  (provider/routing/notify/source/bundle wizards) as `click.prompt` loops.
- **No import-linter contract exists.** `pyproject.toml` has no
  `[tool.importlinter]` section and no import-linter dependency; no contract
  file is present anywhere. ADR-0007 §Layering and at least four plan docs cite
  it anyway. Enforcement today is review-only (ARCHITECTURE.md §1 says "tests
  and/or review").
- Config today is three disconnected surfaces: the CLI control center
  (`cli/config_console.py`, a 7-item numbered menu), the in-session `/config`
  (`commands/builtin.py:360` → `ui/config_admin.py` → `model/config.py` →
  `kernel/config_ops.py`, mount-plan scoped, persists under the `configurator:`
  settings key), and scattered live commands (`/model`, `/effort`, `/theme`,
  `/permissions`, `/allowed-dirs`, `/bundle load`).
- The durable-write machinery is already good:
  `kernel/bundle_admin.py` (atomic three-scope read/write),
  `kernel/setup.py` (provider catalog, masked `keys.env` writer),
  `kernel/routing_admin.py`, `kernel/notify_admin.py`,
  `kernel/source_admin.py`, `kernel/directory_permissions.py`. The gap is
  presentation and one shared domain model, not plumbing.
- Live-change capability boundaries are already proven and documented (BACKLOG
  supplemental items 20/21): additive providers/tools/hooks/agents and new or
  TUI-owned MCP servers mount into the *running* session via
  `kernel/bundle_compose.py` / `kernel/live_mcp.py`; bundle instruction prose,
  orchestrator/context identity, existing-provider reconfiguration, and
  boot-owned MCP replacement remain next-session boundaries. Any settings UX
  must present these boundaries, not paper over them.
- Non-interactive contracts already promised publicly (README,
  `docs/SETTINGS.md`): `config show --json`, `config paths --json`, bare
  `config` never hangs on redirected stdin, every direct command group remains
  the automation API. These stay byte-stable.
- Upstream-drift tooling exists but is manual:
  `scripts/bump_anchors_ref.py`, `scripts/bump_optional_source_refs.py`
  (check mode without `--write`), `tests/test_no_floating_dependencies.py`.
- `/goal` and `/goalify` were audited for this campaign and need **no item**:
  both call amplifier's native capabilities. `kernel/goal.py` writes the
  native `session_state["goal"]` contract and the mounted `loop-streaming`
  orchestrator owns the loop and stall detection; `orchestrator:goal_progress`
  normalizes at `kernel/events.py:179` and renders in the activity line
  (`ui/reducer.py:2382`). `/goalify` ships natively via the bundle's pinned
  app-cli skill source (`bundle.md:87–95`, pinned by
  `tests/test_skill_sources.py:29`), and its condition reaches the first turn
  through live skill activation (`ui/session_ops_controller.py:536`).

## Guiding decisions

0. **One word, one surface: `settings`.** The panel the user sees, the CLI
   command, and the in-session command all share one name. `config` is the
   programmer-CLI term (git, gh); `settings` is what the artifact *is*. So:
   `amplifier-tui settings` becomes the canonical command; `amplifier-tui
   config` keeps working forever as a compatibility alias — hidden from
   top-level help, prints a one-line stderr pointer on use, and its
   `--json`/`paths` contracts and the `amplifier-app-tui/config/v1` schema id
   stay byte-stable (scripts must not break). In-session, `/settings` opens the
   panel; `/config` retains its text show/toggle/set/diff/save contract for
   app-cli parity and transcript scripting, with docs recentered on
   `/settings`. `init` becomes a thin alias that opens settings at the
   Providers section (first-run gate routes there too).
1. **One schema, three shells.** A pure `model/settings_schema.py` registry
   describes every durable key: path, type, default, secret?, valid scopes,
   validation, help, and `applies: now | this-session | next-session | restart`.
   A kernel `settings_service.py` resolves effective values across the three
   scopes + env, and writes through the existing atomic scope writers with
   existing redaction rules. **Three** surfaces render from this one schema —
   the standalone panel, the in-session panel, and a flat scriptable trio
   `settings get|set|unset PATH [VALUE] --global|--project|--local` (gh-style
   typed, validated, secret-aware; no more "edit YAML by hand") — so no truth
   is presented twice and no settings semantics are invented at the UI layer.
2. **Textual for the interactive shell.** Textual is already a pinned runtime
   dependency; the app already ships overlay strips (palette, lanes, rewind,
   theme). The settings panel is a Textual app standalone and an overlay in
   session — same widget tree, two hosts. The numbered-menu code in
   `cli/config_console.py` is retired entirely, not reskinned.
3. **Honesty per item, not per surface.** Every settings row carries its
   `applies` badge sourced from the schema. Live application routes through the
   existing seams (`session_ops.py`, `bundle_compose.py`, `live_mcp.py`,
   governance adapter callables); everything else writes to a scope with an
   explicit "next session" label. Where Foundation has no live seam, the UI
   says so (the bundle-load notice pattern already does this).
4. **Complexity is budgeted, not just moved.** Success is countable: fewer
   concepts in the public story (one word for settings; curated top-level
   help), one panel instead of a numbered menu + text DSL + scattered commands,
   and a cap on `app.py`/`main.py` line counts enforced by test. New
   ergonomics must delete at least as much surface as they add.
5. **Extraction is mechanical, not redesign.** WS1 moves code into controllers
   with zero behavior change; the existing suite (flow + Pilot + goldens) is
   the regression net. No architectural novelty.
6. **Zero new runtime dependencies, offline tests.** The layering check is a
   stdlib-AST test in `tests/`, matching `test_no_floating_dependencies.py`'s
   precedent, rather than adding import-linter. (Import-linter remains the
   acceptable alternative if reviewers prefer the tool ADR-0007 named; the
   contract content is identical either way.)

## Workstream 0 — make the layering contract real (small, independent)

- Add `tests/test_layering_contract.py`: stdlib-AST walk of `src/`,
  asserting `kernel/` never imports `textual`, `model/` imports neither
  `textual` nor `amplifier_*`, `commands/` imports only `model/` + stdlib +
  `kernel`-free surfaces. Fails with the offending `file:line`.
- Update ARCHITECTURE.md §1 to name the test as the enforcement mechanism;
  fix the stale "roughly double" app.py claim in ARCHITECTURE.md §5.1 and
  DEVELOPMENT.md rule 6 with the real numbers and the extraction direction.
- Note the ADR-0007 deviation in its status line (contract enforced by test,
  not import-linter) rather than editing the resolutions retroactively.

**Acceptance:** test fails when a `kernel/` file gains `import textual`;
docs match reality; no behavior change.

## Workstream 1 — `ui/app.py` extraction (debt paydown)

Extract four controllers, in this order (each its own PR, mechanical moves,
suite green unchanged):

1. **`ui/strip_manager.py`** — the ~14 overlay open/close/type-through handlers
   (palette, lanes, rewind, timeline, sessions, queued, theme, keys) collapse
   into one registry keyed by strip. Largest line count, lowest logic density.
2. **`ui/session_admin_controller.py`** — `rename/branch/fork/tags/stash/
   sessions-strip` cluster (~app.py lines 1122–1320) behind the
   `directory_admin.py` fake-host pattern.
3. **`ui/submit_pipeline.py`** — `submit_prompt` / `_submit_prompt` /
   `submit_queued_message` / `_submit_queued_message` / `_queue_message` /
   `drain_turn_queues` / `_restore_unaccepted_*` / checkpoint-draft budget
   (lines 594–843). The admission/restore invariants stay bitwise identical.
4. **`ui/evidence_controller.py`** — evidence panel handlers
   (lines 2207–2303).

Target after WS1: `app.py` ≤ ~900 lines, composition root genuinely composing;
further shrink toward the <500 budget continues opportunistically but is not a
gate of this campaign.

**Acceptance:** `pytest`, `ruff`, `pyright` green; golden matrix byte-identical;
`app.py` line count regression guard added to the WS0 contract test (budget
constant ratcheted down per PR).

## Workstream 2 — settings domain model

- **`model/settings_schema.py`** (pure, no Textual/amplifier): `SettingsField`
  records as data, section ordering, validation functions, `parse_value`
  reuse from `model/config.py`, secret masking rules.
- **`kernel/settings_service.py`**: effective-value resolution
  (env → local → project → global → default, mirroring `kernel/config.py`'s
  merge order), atomic writes via `bundle_admin.write_scope`, secrets only via
  `setup.write_key`, change-record log for the diff view. Never raises into UI;
  returns `(ok, message)` like `config_ops.save_config`.
- Migrate `cli/config_console.snapshot()` to read through the service (same
  redacted values, one resolver); keep the `config/v1` JSON schema additive-only.
- Ship the flat scriptable trio on top of the schema: `amplifier-tui settings
  get PATH [KEY]` (read one value or one section, redacted), `settings set
  PATH VALUE`, `settings unset PATH` — all with one shared
  `--global/--project/--local` flag, validation errors in plain language, and
  secret values routed to `keys.env` via `setup.write_key` (never echoed back).
  This trio is the same service API the panels call, exercised through click.
- The legacy `configurator:` key keeps working (read and written by `/config
  save`); the schema maps those keys rather than replacing them.

**Acceptance:** pure unit tests for schema/validation/diff at the model layer;
kernel tests for merge, redaction, atomicity, failure messages; `config show
--json` diff is empty against `main` for unchanged settings; the trio round-trips
against tmp scopes (`AMPLIFIER_HOME` override pattern).

## Workstream 3 — settings panel (the UX centerpiece)

- **`ui/settings_panel/`** — section sidebar (Providers · Models & routing ·
  Bundles · Directory access · Notifications · Behavior · Maintenance), form
  rows rendered from schema (bool toggle / choice / masked secret / path list),
  inline validation with plain-language errors, scope picker (global/project/
  local) with the exact target file shown, dirty tracking, and a
  diff-before-save review ("3 changes → project scope?"). Search filters across
  sections. Colors are theme tokens only; keymap is `ui/keymap.py` data.
- **Standalone host:** `amplifier-tui settings` runs the panel as a slim Textual
  app over `settings_service` — no bundle prepare, no session boot (current
  control center boots neither; the panel must not regress that). `amplifier-tui
  config` invokes the identical entry (compatibility alias, per decision 0).
  `init` is the same panel opened at Providers; the first-run gate routes
  there. Non-TTY stdin keeps today's behavior (error with pointer to `--json`
  surfaces — verified intact post-#238). Deep links like `amplifier-tui
  settings notifications` open the panel at a section, and in-TUI notices about
  unset/misconfigured values offer an `open settings` action.
- **In-session host:** `/settings` (new; `/config` keeps its text contract)
  opens the same panel as an overlay. Rows whose schema says `applies: now`
  route through the live adapter: theme → existing theme path, effort/model →
  `session_ops`, notifications → display policy, allowed/denied dirs →
  governance adapter callables, new MCP server → `live_mcp`, additive bundle
  module → `bundle_compose`. Everything else writes the chosen scope and shows
  the `next session` badge from the schema — including the known boundaries
  (routing matrix, orchestrator/context, existing-provider edit, boot-owned MCP
  replacement, bundle instruction prose).
- `update` / `reset` / `doctor` surface inside Maintenance as read-only
  previews + "run in terminal" hints where the operation must outlive the
  session.

**Acceptance:** Pilot tests per section incl. scope writes to `tmp_path`
(via `AMPLIFIER_HOME` override, the `config_ops.py` probe pattern); masked
secret fields never echo; goldens unchanged (panel is outside the transcript
renderer); a forge demo-lane scenario added for panel open/edit/save (opt-in
tier, not the default gate).

## Workstream 4 — update / reset / doctor terminal UX

- **`cli/presentation.py`**: shared rich components (step lists, result tables,
  preserve-lists) so all lifecycle commands speak one visual language.
- `update`: **largely shipped in PR #238 (bf931f0)** — installed revision,
  target revision, animated progress, streamed installer phases, final
  verification are live. Remaining here: extract those one-off components into
  the shared presentation module and add `--json` for scripts; failure output
  names the next command.
- `reset`: a preview table of exactly what is preserved (keys, config,
  sessions, local bundles) and what is rebuilt, confirmed before acting;
  semantics unchanged from `kernel/reset.py`.
- `doctor`: group findings by area with the fix command per finding (current
  behavior) in the shared presentation; exit codes unchanged.

**Acceptance:** existing CLI tests pass unchanged; new snapshot tests for the
happy-path output of each command at fixed width; `--json` outputs stable.

## Workstream 5 — `main.py` split + help curation

Move interactive flow bodies into `cli/` — `cli/provider_flow.py`,
`cli/routing_flow.py`, `cli/notify_flow.py`, `cli/source_flow.py`,
`cli/bundle_flow.py` — leaving `main.py` as click wiring + the launch path
(target ≤ ~800 lines). Pair with WS3/WS4 so flows are rewritten into the new
presentation layer exactly once.

- **Curated top-level help.** `--help` leads with the daily surface (launch,
  `settings`, `doctor`, `update`, `reset`, `run`) and groups the power
  commands (`bundle`, `provider`, `routing`, `source`, `notify`, `tool`,
  `serve`, `control-token`, dir lists, session ops) under a clearly labeled
  advanced section — nothing hidden, everything still in its own `--help`.
  Custom click group formatting only; no command changes.
- **`settings` registered, `config` hidden-aliased** per decision 0; `init`
  rewired as the Providers-section alias.
- **Documentation sweep lands in the same PRs** as the code it describes:
  README.md, USER-GUIDE.md §7, SETTINGS.md, INSTALL.md, docs-site
  (configuration/setup/quickstart/reference/troubleshooting/update-reset/
  using-the-tui), llms.txt — and the contract tests that pin them
  (`test_docs_site_contract.py`: three-command story, nonexistent-command
  list, reference rows; `test_docs_content_sync.py`) updated in lockstep.
  `settings` must be documented working (the #previous-`setup`-incident test
  at `test_docs_site_contract.py:445` is the guard).

**Acceptance:** no command-surface change beyond decision 0's rename+alias;
`tests/test_config_cli.py` and the command tests green; help text snapshot
tests cover the curated layout; docs contract tests green in the same PR.

## Workstream 6 — upstream drift hygiene

- Scheduled CI (weekly, `upstream-drift.yml`): run the check modes of
  `scripts/bump_anchors_ref.py` and `scripts/bump_optional_source_refs.py`;
  open/refresh a tracking issue on drift instead of failing the default gate.
- Publish the upstream-bound items (context-simple compaction hysteresis,
  Foundation prepare cross-process locking, MCP aggregate ownership
  reconciliation) as labeled upstream workstream notes in BACKLOG.md so they
  stop reading as local partials.
- Spike (time-boxed, decision doc): a thin typed boundary over
  amplifier-core/Textual/rich hot paths — the documented precondition for
  flipping pyright strict per DEVELOPMENT.md's trial verdict.

## Workstream 8 — exact-error fidelity (connection/auth/runtime failures)

Today a mid-session provider failure is a *footer transient* by contract
(`kernel/events.py:285` types `ProviderNotice` as exactly that): the toast
fades, one line clips the real exception, and nothing durable records what
happened. Boot is better (`preflight_verify.py` returns scrubbed exact errors
+ remediation) — this workstream brings runtime failure display up to the boot
standard, through the same single normalization boundary.

- **`kernel/events.py`:** extend the provider-notice normalization into a
  classified record — `category: auth | quota | network | timeout | model |
  unknown`, the verbatim message scrubbed at THE boundary via
  `scrub_provider_error` / `model.redaction.scrub_text` (never truncated —
  clipping moves to display, not data), plus provider id. Classification is a
  data-driven table, app-local, no upstream changes.
- **`model/blocks.py`:** a durable `ErrorBlock` (new block kind): branded
  problem title, the full scrubbed error wrapped (not clipped), a remediation
  line, and — for `auth` — an action to open `/settings` at Providers (WS3
  deep link) or run `/doctor` (`unknown`). Toast stays as the ping; the block
  is the record.
- **`ui/reducer.py`:** on `notice == "error"` and on terminal orchestrator
  error/incomplete states, emit the durable block alongside the existing
  toast + attention ladder, deduped by the envelope's event_id. Audit the
  failure matrix first — auth mid-turn, network drop mid-stream, quota/429,
  model-not-found, mount failure — and map each to the same block so no
  failure path is toast-only.
- **Boot path:** confirm `_render_preflight_failure` (main.py) prints the
  verbatim scrubbed provider exception (preflight_verify already supplies
  it); keep `--dry-run --json` error/remediation fields stable.
- **Tests:** kernel unit tests for classification + scrubbing (a fake secret
  embedded in an exception message must never render); reducer tests that
  block + toast both fire once; one scripted error turn added to DemoRuntime
  so goldens and the forge tier cover the block (goldens regenerated in the
  same commit); Pilot test for the settings deep link.

**Non-goals:** no auto-retry policy changes, no upstream error-shape changes,
no new error vocabulary in amplifier-core — classification stays a TUI-side
view.

**Acceptance:** every failure path in the audit matrix produces a durable,
exact, scrubbed error block + remediation in ≤2 displayed lines of chrome;
no secret value appears in any test fixture assertion; `demo` mode renders
the error turn through the same code path as the real runtime.

## Workstream 7 — release trust (separate approval)

PyPI publish with sigstore attestation; installer gains pinned-tag
verification; `amplifier-tui update` prints provenance. The curl-from-source
channel remains as the dev channel but stops being the only channel. Tracked
here for completeness; sequenced outside this campaign.

## Execution order

WS0 (anytime, small) → WS1 (extraction PRs, parallel-safe with nothing
touching `app.py`) → WS2 → WS3 → WS4/WS5 (together) → WS8 (normalization +
ErrorBlock anytime after WS2; deep-link wiring after WS3) → WS6 (anytime) →
WS7 (separate). Each workstream is independently mergeable.

## Non-goals

- No background self-update; `amplifier-tui update` stays user-invoked.
- `amplifier-tui config` is **never removed** in this campaign — it is a
  deprecated-but-working alias with byte-stable JSON contracts. Same for
  `/config`'s text mode in-session; the panel is additive (`/settings`), not
  a replacement.
- No shell-completion installer: deliberately out, matching the recorded
  BACKLOG non-goal (`--install-completion` belongs to a separate admin CLI).
- No new runtime dependencies; no change to the JSONL `run` contract, the
  `config show --json` v1 schema (additive only), or secret redaction rules.
- No TUI-ification of the headless `run`/`serve` surfaces; those stay
  machine-first.
- No bundle-system redesign; no live replacement of singleton modules beyond
  the proven additive seam.

## Risks

| Risk | Mitigation |
|---|---|
| WS1 extraction drifts behavior in the submit pipeline | Move only; the flow/steer/queue/checkpoint suites gate; one controller per PR |
| Schema registry ossifies and hides settings | Schema is data + tests enumerate it; `config show --json` parity test against `main` |
| Standalone panel regresses to booting a bundle | Explicit test: `config` launches with no bundle cache touched; boot-path test asserts no `prepare()` |
| Live-apply honesty drifts from item 20/21 reality | `applies` metadata reviewed against `bundle_compose.py`/`live_mcp.py` boundaries; ordering test enumerates which keys claim `now` |
| Two new hosts double widget-test burden | One widget tree, two thin hosts — Pilot tests target the panel; hosts tested as adapters only |
