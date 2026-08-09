---
layout: default
title: Reference
permalink: /reference/
---

Every documented command, flag, slash command, keybinding, and file location Amplifier TUI ships today. Tables first; per-command detail follows.

## Command summary

Most sessions only ever need three commands:

```sh
amplifier-tui           # launch the interactive TUI
amplifier-tui update    # update the installed app
amplifier-tui reset     # repair or clean local app state
```

Everything else on this page is discoverable, advanced surface — never required for day-to-day use. The full top-level command surface, one line each:

| Command | Purpose |
|---|---|
| `amplifier-tui` | Launch the interactive TUI (bare invocation) |
| `run [PROMPT]` | One-shot: run a single prompt against a real session; text, JSON, or JSONL output |
| `serve` | Bidirectional JSONL session protocol over stdio, for out-of-process front-ends |
| `control-token` | Issue, list, or revoke credentials for `serve`'s control plane |
| `sessions` | List stored sessions for this project, newest first |
| `resume [SESSION_ID]` | Resume a stored session (interactive picker if no id is given) |
| `continue` | Resume the newest stored session directly, no picker |
| `tool` | List or invoke mounted tools from the CLI (governed, one-shot) |
| `session` | Stored-session lifecycle: list, rename, delete, cleanup, fork, export, import |
| `doctor` | Setup checkup; exit 0 = ready, exit 1 = findings exist |
| `version` | Print the installed app/core/foundation identity |
| `stats` | Cross-session cost and usage dashboard |
| `reset` | Category-scoped cleaner, plus default repair/reinstall of the app |
| `bundle` | Manage bundles: list, show, use, add, warm, remove, refresh |
| `allowed-dirs` | Manage directories the AI may write to |
| `denied-dirs` | Manage directories the AI may never write to |
| `init` | Configure a provider (and routing); no flags opens the setup console |
| `provider` | Manage configured providers: list, add, use, remove, dashboard |
| `notify` | Configure attention notifications: bell, desktop, ntfy push |
| `update` | Update the installed app itself |
| `source` | Override module/bundle source URIs |
| `routing` | Manage routing matrices: list, use, show, create, manage |

`--demo` is a **flag** on the bare `amplifier-tui` command above, not a subcommand of its own — see Launching, below.

## Launching

### Bare `amplifier-tui`

| Option | Kind | Help text |
|---|---|---|
| `--demo` | flag | Run the scripted DemoRuntime instead of a real session. |
| `--bundle` | value | Bundle name or URI (default: settings/bundled). |
| `--provider`, `-p` | value | Provider override for THIS launch only (not persisted to settings). |
| `--model`, `-m` | value | Model override for THIS launch only (requires --provider; not persisted). |
| `--mode` | value | Interaction mode to start in (chat, plan, brainstorm, build, auto). |
| `--dry-run` | flag | Resolve mounts/providers and report what would launch; change/launch nothing. |
| `--version` | flag | Print the app version and exit (Click's built-in flag — see `version`, below, for the fuller identity check). |

`--demo` is a flag on the top-level command, **not a subcommand**: `amplifier-tui --demo` is correct, `amplifier-tui demo` is not a real invocation.

With no subcommand given, `amplifier-tui`:

1. Validates overrides first — exits 1 if `--model` is given without `--provider`, or if `--mode` names anything outside `chat` / `plan` / `brainstorm` / `build` / `auto`.
2. If `--dry-run`: resolves mounts/providers and prints a "Would Launch" table (bundle, provider, model, routing, providers/tools configured), then exits — nothing launches. `--demo --dry-run` short-circuits straight to exit 0, since demo mode has no real mounts or providers to preflight.
3. Otherwise it launches: unless `--demo`, a first-run gate configures a provider if none exists yet (an interactive terminal is walked through `init`; a non-interactive shell tries environment auto-detection, or exits 1 with a remediation message). Then a preflight resolves the bundle and provider **before** the terminal takes over the screen — a failure prints `✗ cannot launch: <error>` / `→ <remediation>` to stderr and exits 1 without ever touching the screen. Only then does the TUI actually boot.

### `--version` vs `version`

`--version` is Click's built-in flag: it prints the hardcoded version string and exits. The `version` command (below) instead proves the *installed* identity via `importlib.metadata` and PEP 610 — not just that hardcoded string — and additionally prints the `core`/`foundation` dependency versions.

## Commands

### Scope options (shared)

Many subcommands below write to a **scope** — which settings file receives the change:

| Flag | Help text (verbatim) |
|---|---|
| `--local` | Write to .amplifier/settings.local.yaml. |
| `--project` | Write to .amplifier/settings.yaml. |
| `--global` | Write to ~/.amplifier/settings.yaml (default). |

Default scope when none is passed: **global**. Tables below list "scope options" as shorthand for these three flags.

### `run [PROMPT]`

One real session, one prompt (argument or piped stdin).

| Flag | Help text (verbatim) |
|---|---|
| `--bundle` | Bundle name or URI. |
| `--model`, `-m` | Model override for THIS invocation only (requires --provider; not persisted). |
| `--provider`, `-p` | Provider override for THIS invocation only (not persisted to settings). |
| `--mode` | Interaction mode to start in (chat, plan, brainstorm, build, auto). |
| `--resume SESSION_ID` | Seed this one-shot from an existing session's stored context. |
| `--output-format` | Response format; JSON modes reserve stdout for machine-readable output. (`text` \| `json` \| `json-trace` \| `jsonl`, default `text`) |
| `--dry-run` | Resolve mounts/providers and report what would launch; run nothing. |

With no prompt on an interactive terminal, nothing piped, and plain-text output, `run` launches the full-screen TUI with the same overrides instead of erroring; piped, non-interactive, or JSON invocations stay prompt-required. See "Headless and automation," below, for the four output formats' exact contract.

### `serve`

Runs an interactive session as a **bidirectional line protocol on stdio** — the contract an out-of-process front-end (for example, a Rust or web UI) drives against; it wraps `RealRuntime` and never touches `amplifier-core` directly.

| Flag | Help text (verbatim) |
|---|---|
| `--bundle` | Bundle name or URI. |
| `--model`, `-m` | Model override (requires --provider). |
| `--provider`, `-p` | Provider override for THIS invocation. |
| `--mode` | Interaction mode to start in. |
| `--resume SESSION_ID` | Resume a stored session. |
| `--attach REF` | Attach ref (amplifier-session:<id>[#<handoff>]); claims the handoff on boot. |
| `--actor ID` | Default actor id for control ops. |
| `--actor-kind` | Default actor kind (drives lease takeover precedence). (`human` \| `automation`, default `automation`) |
| `--attachable` / `--no-attachable` | Publish a live-attach endpoint so a second process can join THIS runtime. (default off) |

`--attach` joins a live-served session over its attach socket if one exists, or boots on the same session state and claims the handoff if not. `--resume` uses the same four exit codes as top-level `resume`, below. Full wire contract in "Headless and automation," below.

### `init`

| Flag | Help text (verbatim) |
|---|---|
| `--provider`, `-p` | Provider to set up (e.g. anthropic). |
| `--api-key` | API key (non-interactive; else prompted). |
| `--base-url` | Optional provider base-URL override. |
| `--model` | Default model for the provider. |
| `--from-env` | Non-interactive: configure a provider detected from env vars. |
| `--yes`, `-y` | Non-interactive: never prompt (needs --api-key). |

With **no flags**, `init` opens the combined setup **console**: it renders the configured-providers table plus the active routing resolution, then loops on `[p]` manage providers, `[r]` manage routing, `[w]` change write scope, `[d]` done. First run (no providers configured) drops straight into the provider console. Passing any flag bypasses the console and takes the non-interactive path.

### `doctor`

No options. Prints a setup checkup report. **Exit 0 = ready, exit 1 = findings exist.** Runs the same bundle/provider preflight an interactive boot does, in strict mode — it proves credentials actually work, not just that a bundle resolves.

### `version`

No options. Prints `amplifier-tui <identity>`, then `core <version>` / `foundation <version>`, all read via `importlib.metadata` rather than trusting the hardcoded version string alone. The identity includes the short commit for a git-sourced install.

### `update`

| Flag | Help text (verbatim) |
|---|---|
| `--check-only` | Report app update availability; change nothing. |
| `--yes`, `-y` | Update without the confirmation prompt. |
| `--force` | Run the source installer even if no update is detected. |
| `--verbose`, `-v` | Print the installer command before running it. |

`amplifier-tui update` updates the **app** itself — the installed `amplifier-tui` package/executable — by checking the upstream repository and running the source installer when a newer commit exists on `main`. It never touches bundle or module caches; that is the separate, advanced `amplifier-tui bundle refresh` command (below), which refreshes each mounted bundle's module source cache and never updates the app. Keep the two straight: `update` is the app; `bundle refresh` is the bundle/module cache. In an editable/dev-checkout install, `update` does not run the installer at all — it prints `git pull --ff-only && uv sync` instead, so it never clobbers a developer's own checkout.

### `reset`

| Flag | Help text (verbatim) |
|---|---|
| `--category`, `-c NAME` | Category to clear (repeatable or comma-separated). Default: cache,registry. |
| `--dry-run` | Preview what would be removed; change nothing. |
| `--yes`, `-y` | Skip the confirmation prompt (scripted use). |
| `--home PATH` | App home to reset (default: $AMPLIFIER_HOME or ~/.amplifier). |
| `--list` | List the category taxonomy and exit. |
| `--reinstall` | Compatibility no-op: reset repairs/reinstalls by default. |
| `--no-reinstall` | Only clear selected categories; do not repair/reinstall the tui tool. |
| `--install-source URI` | Repair/reinstall source (default: the tui git repo; use '.' from a clone). |

- **Default categories cleared:** `cache` and `registry` only — the two categories that auto-regenerate. `sessions`, `config`, `bundles`, and `keys` are all preserved unless named explicitly with `--category`.
- **Default behavior also repairs/reinstalls** the app after clearing (the tui analogue of app-cli's reset-and-reinstall); pass `--no-reinstall` for cleanup only, with no reinstall step.
- **`keys`** (which holds `keys.env`) is only ever cleared when named explicitly via `--category` — it is never in the default set, and selecting it prints a `WARNING: this clears secrets` line.
- Every removal target is re-checked as a strict descendant of the confirmed app home before deletion; `reset` refuses to run against `$HOME` itself or anything that doesn't look like an app home.
- `--list` prints the category taxonomy (name, description, and `[default]` / `[auto-regenerates]` / `[secret]` tags) and exits without changing anything.

### `bundle`

| Subcommand | Purpose |
|---|---|
| `list` | List discovered bundles; `●` marks the active one (`--all` includes nested dependency bundles) |
| `current` | Print the active bundle name, or `<default> (default)` |
| `use NAME` | Set the active bundle (scope options) |
| `clear` | Revert to the default bundle (scope options) |
| `show NAME` | Version, description, includes, and mount counts |
| `add URI` | Register a bundle, validated before it's added (`--name`/`-n`, `--app`, `--warm`, scope options) |
| `warm NAME` | Pre-install a bundle's modules once, outside the boot install burst |
| `remove NAME` | Drop a bundle from the discovery registry (scope options) |
| `update NAME` | One-line update-status check for a single bundle (via foundation) |
| `refresh` | **Advanced.** Refresh mounted bundle/module source caches (`--check-only`, `--yes`/`-y`, `--force`, `--verbose`/`-v`) |

`add` and `refresh` flags (verbatim):

| Flag | Help text (verbatim) |
|---|---|
| `--name`, `-n` | Registry name (default: the bundle's own name). |
| `--app` | Also compose onto every session (overlay). |
| `--warm` | Pre-install the bundle's modules now (out of the boot burst). |
| `--check-only` | Report available updates; change nothing. |
| `--yes`, `-y` | Apply without the confirmation prompt. |
| `--force` | uv cache clean first, then re-fetch every source. |
| `--verbose`, `-v` | List every skipped local/non-git source. |

`bundle refresh` never updates the app itself (that's `amplifier-tui update`, above); it only refreshes each composed bundle's module source cache, plus advisory app/core/foundation version rows and the pinned Anchors include's own freshness.

### `provider`

| Subcommand | Purpose |
|---|---|
| `list` | List configured providers; `★` marks the primary (lowest-priority) one |
| `add [PROVIDER_TYPE]` | Add a provider — interactive picker + field-driven wizard when `PROVIDER_TYPE` is omitted |
| `use NAME` | Set `NAME` to priority `1` |
| `remove NAME` | Remove `NAME` from every scope |
| `dashboard` | Show configured providers, the primary, and a switch hint |

`add`'s notable flags (verbatim where captured in source):

| Flag | Help text (verbatim) |
|---|---|
| `--instance-id` | Name a second instance of the same provider type (e.g. runpod). Routing matrices target this id. |
| `--scope` | Settings scope to write the provider entry into. (`global` \| `project` \| `local`, default `global`) |

`--api-key`, `--base-url`, and `--model` set those fields directly instead of using the interactive wizard; `--yes`/`-y` skips prompts. For how provider *priority* actually resolves (lower number wins, bundled Anthropic fallback at `100`), see [Configuration]({{ '/configuration/' | relative_url }}).

### `routing`

| Subcommand | Purpose |
|---|---|
| `list` | List routing matrices; `●` marks the active one |
| `use MATRIX_NAME` | Select a matrix — applies at next session start (scope options) |
| `show [MATRIX_NAME]` | Defaults to the active matrix (`--detailed` — "Show the full candidate waterfall per role.") |
| `create` | Interactive; persists under `~/.amplifier/routing` |
| `manage` | Interactive select / view / create loop (scope options) |

### `session` and `sessions`

Bare `session` (no subcommand) prints help. `session` is the stored-session lifecycle group; top-level `sessions` (below) is the quick listing.

| `session` subcommand | Flags | Purpose |
|---|---|---|
| `list` | `--limit`/`-n` (default 20) | Same renderer as top-level `sessions`, below |
| `rename SESSION_ID NAME...` | none | Renames metadata only — no file surgery |
| `delete SESSION_ID` | `--force`/`-f` | Deletes the session directory and everything under it |
| `cleanup` | `--days`/`-d` (default 30), `--force`/`-f` | Delete sessions older than N days |
| `fork SESSION_ID` | `--directive`/`-d` (**required**), `--name`/`-n` | Snapshot the parent's conversation into a NEW session, primed to run `DIRECTIVE` on resume |
| `export SESSION_ID` | `--sanitize`, `--tool-io`, `--output`/`-o FILE` | Structured, **re-importable** JSON — distinct from the in-app markdown `/export` |
| `import FILE` | `--name`/`-n` | Local file path only; mints a NEW session id, never clobbers an existing one |
| `resume` | — | A registered **alias** for the top-level `resume` command — the same command object, not a re-implementation |

Notable `session` flags (verbatim):

| Flag | Help text (verbatim) |
|---|---|
| `--limit`, `-n` | Number of sessions to show. |
| `--force`, `-f` | Skip the confirmation prompt. |
| `--days`, `-d` | Delete sessions older than N days. |
| `--directive`, `-d` | Starting instruction the forked child runs first on resume. |
| `--name`, `-n` (fork) | Custom name for the forked session. |
| `--sanitize` | Redact user filesystem paths (home dirs / usernames) for safe sharing. |
| `--tool-io` | Also redact tool inputs/outputs (implies --sanitize). |
| `--output`, `-o` | Write JSON to FILE (default: stdout). |
| `--name`, `-n` (import) | Name for the imported session. |

**`sessions`** (top level):

| Flag | Help text (verbatim) |
|---|---|
| `--limit`, `-n` | Number of sessions to show. (default 20) |
| `--plain` | Print bare session ids, one per line (machine-readable; no table). |

Lists stored sessions for **this project** (per working directory), newest first: Name · Session · Bundle · Msgs · Turns · Age (+ a `State` column only when a damaged session exists — `recovered`/`transcript_lost` in yellow, `indexing`/`corrupt` in red).

### `resume [SESSION_ID]`

| Flag | Help text (verbatim) |
|---|---|
| `--bundle` | Bundle name or URI. |
| `--limit`, `-n` | Sessions shown in the picker. (default 10) |

No id opens an interactive numbered picker of recent sessions; a single stored session auto-selects. Deterministic exit codes, shared by `resume`, `session resume`, `run --resume`, and `serve --resume`:

| Code | Meaning |
|---|---|
| `0` | Success — the resumed session's own exit status takes over |
| `2` | Not found — no stored session matches the id/prefix |
| `3` | Ambiguous — the prefix matches more than one session (a candidates table is printed) |
| `4` | Corrupt — the match is unambiguous, but its metadata (and `.backup`) could not be read |
| `1` | Generic/unexpected error — never reused for the three cases above |

### `continue`

| Flag | Help text (verbatim) |
|---|---|
| `--bundle` | Bundle name or URI. |

No-argument shortcut for `resume`: auto-selects the newest stored session and launches straight into it, skipping the picker.

### `allowed-dirs` / `denied-dirs`

Both groups share the identical shape — they manage directories the AI can (`allowed-dirs`) or cannot (`denied-dirs`) write to.

| Subcommand | Flags | Purpose |
|---|---|---|
| `list` | scope **filter** (`--global`/`--project`/`--local`; flag-valued, no help text captured in source) | Show directories for one scope |
| `add PATH` | scope options | Add a directory |
| `remove PATH` | scope options | Remove a directory |

### `source`

Module/bundle source overrides.

| Subcommand | Flags | Purpose |
|---|---|---|
| `add IDENTIFIER SOURCE_URI` | `--bundle`, `--module`, scope options | Point an identifier at a source URI |
| `remove IDENTIFIER` | `--bundle`, `--module`, scope options | Remove an override |
| `list` | none | List all source overrides |
| `show MODULE_ID` | none | Print the resolution-precedence chain: env var → workspace → settings `sources.modules` → effective |

Notable flags (verbatim): `--bundle` — "Force treating IDENTIFIER as a bundle (skip auto-detect)."; `--module` — "Force treating IDENTIFIER as a module (skip auto-detect)."

### `stats`

| Flag | Help text (verbatim) |
|---|---|
| `--days` | Window: last N days (0 = today, omit = all time). |
| `--models [N]` | Show the per-model rollup: bare --models = all; --models N = top N. |
| `--project SLUG` | Project to aggregate: default current project; 'all' = every project; else a slug. |
| `--json` | Emit the report as JSON (machine-readable). |

Cross-session cost/usage dashboard, reconstructed from each session's own usage events — the same source the live cost footer uses.

### `tool`

| Subcommand | Flags | Purpose |
|---|---|---|
| `list` | `--bundle`, `--output-format` | Boot a real session, list its mounted tools, tear it down |
| `invoke NAME [ARGS...]` | `--bundle`, `--json`, `--yes`/`-y`, `--output-format` | Invoke one tool from the CLI; `ARGS` are `key=value` pairs, each JSON-decoded when possible |

Notable flags (verbatim):

| Flag | Help text (verbatim) |
|---|---|
| `--output-format` (list) | Listing format; json reserves stdout for one machine-readable document. (`text` \| `json`, default `text`) |
| `--json JSON_ARGS` (invoke) | Pass ALL arguments as one JSON object (e.g. --json '{"file_path": "x"}'). |
| `--yes`, `-y` | Permit in-project write tools; exec/network/spend and out-of-project writes stay blocked. |
| `--output-format` (invoke) | Result format; json reserves stdout for one machine-readable document. (`text` \| `json`, default `text`) |

A one-shot CLI cannot answer an interactive approval, so `tool invoke` runs a SAFE posture by default: read/test tools run; write/exec/network/spend tools are refused unless `--yes` — and even then only in-project writes are permitted, still boundary-checked.

### `notify`

Configures the attention-notification ladder (bell/desktop) plus ntfy push. Bare `notify` shows the same thing as `notify show`.

| Subcommand | Flags | Purpose |
|---|---|---|
| `show` | none | Show current notification config |
| `set KEY VALUE` | scope options | Keys: `suppress`, `desktop.enabled`, `push.enabled`, `push.server`, `push.priority`, `push.tags`, `topic` |
| `enable [desktop\|push]` | scope options | Target defaults to `desktop` |
| `disable [desktop\|push]` | scope options | Target defaults to `desktop` |
| `test` | none | Fire a real test notification |

`topic` is a secret: it is saved to `keys.env`, never to a settings file.

### `control-token`

Issues/revokes credentials that make `serve`'s control plane require proof of identity instead of trusting the local pipe peer. Without a token, anyone on the pipe can claim `"kind": "human"` and outrank an automation controller for the write lease.

| Subcommand | Flags | Purpose |
|---|---|---|
| `issue PRINCIPAL` | `--kind`, `--permission`, `--display`, `--ttl` | Mint a token; prints the plaintext **once**, never writes it to disk (stored hashed) |
| `list` | none | List ids/grants only, never secrets |
| `revoke TOKEN_ID` | none | Effective on the next control op |

Notable flags (verbatim):

| Flag | Help text (verbatim) |
|---|---|
| `--kind` | The VERIFIED kind this token establishes; a bearer may not claim above it. (`human` \| `automation`, default `automation`) |
| `--permission` | Repeatable. Default: all three. (`read` \| `write` \| `control`) |
| `--display` | Human-readable label for the audit trail. |
| `--ttl` | Seconds until the token expires (default: never). |

Token store: `control-authz.json`, inside the project's sessions base directory — see File locations, below.

## Headless and automation

What makes `run` and `serve` scriptable: a fixed, versioned JSON/JSONL contract.

### `run` output modes

| Mode | stdout contract |
|---|---|
| `text` (default) | Plain response text. On error: `Error: <msg>` to **stderr**, exit 1. |
| `json` | Exactly one JSON document: `{"status": "success", "response", "session_id", "bundle", "model", "timestamp"}` or `{"status": "error", "error", "error_type", "session_id", "timestamp"}`. Module/runtime diagnostics go to stderr. |
| `json-trace` | The same one document as `json`, plus `"execution_trace"` (every queued normalized `UIEvent`) and `"metadata": {"event_count", "duration_ms"}`. |
| `jsonl` | A **live stream** of newline-delimited JSON records to stdout, flushed as they occur — not buffered to the end. |

`jsonl`'s exact record sequence: one `session.started`, then zero or more `runtime.event` (each wrapping a normalized `UIEvent`, emitted as it arrives — not deferred to turn completion), then **exactly one** terminal record: `turn.completed` (success, exit 0) or `error` (failure, exit 1).

### The JSONL schema contract

Every record is schema-versioned and closed to unknown fields:

- `schema_version: 1` on every line.
- `sequence` — monotonically increasing from 1 per invocation; never resets or skips within one process run.
- `timestamp` — ISO-8601 UTC, stamped at emission time.
- `type` discriminates exactly four record shapes: `session.started` (`session_id`, `bundle`, `model`), `runtime.event` (`event`), `turn.completed` (`session_id`, `response`, `duration_ms >= 0`), `error` (`session_id`, `error`, `error_type`, `duration_ms >= 0`).
- Exactly one of `turn.completed` xor `error` closes every stream, and the process's own exit code (0 or 1) always agrees with which one was emitted.

### Resume semantics

`run --resume SESSION_ID` and `serve --resume SESSION_ID` both seed from a stored session's context using the same four deterministic exit codes as top-level `resume` — see `resume`, above.

### `serve` wire protocol

Adds the **input** direction on top of the same normalized-event output `run --output-format jsonl` already has: a bidirectional, one-JSON-object-per-line protocol over stdio.

- **In (stdin):** `submit`, `steer`, `approve`, `decision`, `interrupt`, `effort.get`/`set`/`cycle`, `tag.add`/`remove`/`list`/`sessions`, `context.get` — plus an opt-in control plane: `session.handle`, `lease.acquire`/`heartbeat`/`release`/`takeover`/`status`, `session.pause`/`resume`, `handoff.claim`/`list`, `audit.query`, `history.replay`.
- **Out (stdout):** `boot.progress`, then the byte-identical `session.started` / `runtime.event` / `turn.completed` envelope the `run` JSONL contract uses, plus `approval.required` (the one record `run` can never emit, since a one-shot has no way to answer it), `effort.state`, `tag.updated`/`list`/`sessions`, `context.state` — and, control-plane only, `session.handle`, `lease.state`, `control.conflict`/`audit`/`ack`, `handoff.created`/`claimed`, `history.begin`/`end`.
- The control plane is opt-in and lazily materialized: a client that never sends a control op or attaches `actor`/`lease`/`idem` sees the legacy protocol byte-for-byte, and no control files are written. When it is used: single-writer lease with actor precedence `human > automation > unknown`; every mutating op is attributed and appended to an audit log; writes/control ops may carry an `idem` key so a retried connection replays instead of double-acting.

### SDKs

Python and TypeScript SDKs (`sdk/python/`, `sdk/typescript/`) wrap this same JSONL contract as thin, dependency-light subprocess clients. See their own READMEs in the repository for install steps and APIs — not duplicated here.

## Slash commands

### Built-in commands

In-session `/` commands are powered by a single registry table that drives the palette, the help listing, and dispatch — so nothing can appear in one without the others agreeing.

| Command | Purpose | Group |
|---|---|---|
| `/mode` | cycle or jump posture: chat, plan, brainstorm, build, auto | During |
| `/modes` | list native bundle modes; /mode <name> activates | During |
| `/plan` | read-only planning; hands the plan to build | During |
| `/brainstorm` | no tools, divergent output; /plan to converge | During |
| `/context` | context usage grid + suggestions | During |
| `/config` | live config: show · toggle · set · diff · save | During |
| `/status` | session status: model, mode, messages, cost | During |
| `/model` | list models; /model [provider] <name> switches the live model | During |
| `/effort` | reasoning effort; /effort <none…max> sets it | During |
| `/compact` | compact context; /compact <focus> to steer it | During |
| `/goal` | native autonomous loop; /goal stop clears it | During |
| `/clear` | clear transcript view + context (not persisted history) | During |
| `/tools` | list the mounted tools | During |
| `/agents` | list the delegatable agents | During |
| `/skills` | list available skills | During |
| `/skill` | load a skill by name: /skill <name> | During |
| `/mcp` | MCP servers: list · live add/reload/remove | During |
| `/bundle` | live bundles; /bundle load <name-or-uri> composes additive modules | During |
| `/module` | load additive provider/tool/hook now: /module load ID [SOURCE] | During |
| `/codemode` | code mode · preview the execute() tool catalog | During |
| `/tasks` | agent lanes: one line per subagent (bound to `toggle_lanes`, ctrl+t) | Parallel |
| `/ledger` | session outcome ledger: spend vs yield (bound to `show_ledger`, ctrl+l) | Ship |
| `/export` | write transcript markdown to exports/ | Ship |
| `/copy` | copy last answer to clipboard (OSC 52) | Ship |
| `/diff` | working-tree diff; /diff staged for the cached diff | Ship |
| `/about` | app, core, bundle + session identity | Ship |
| `/rewind` | restore code, conversation, or both before a prompt (bound to `open_rewind`, ctrl+r) | Between |
| `/rename` | name this session for the resume picker | Between |
| `/sessions` | list stored sessions; /sessions <query> filters | Between |
| `/branch` | snapshot this conversation into a new session | Between |
| `/fork` | snapshot into a new session primed to run a directive | Between |
| `/tag` | attach or remove session tags; /tag sessions <tag> filters | Between |
| `/stashes` | list stashed drafts; /unstash restores one | Between |
| `/unstash` | restore a stashed draft: /unstash [n] | Between |
| `/quit` | exit the app (ctrl-d works too) | Between |
| `/permissions` | edit trust slots: boundary, blocks, exceptions | Repair |
| `/allowed-dirs` | list or edit session allowed write directories | Repair |
| `/denied-dirs` | list or edit session denied write directories | Repair |
| `/doctor` | setup checkup; reports, then fixes on confirm | Repair |
| `/improve` | tune config from ledger + denial log | Repair |
| `/theme` | switch theme: slate, graphite, carbon, paper | Repair |
| `/keys` | list every keyboard shortcut and what it does | Repair |

### Skill-derived commands

Beyond this fixed built-in table, one slash command is dynamically registered per discovered skill name (plus one per distinct `shortcut:` alias). This set varies by which skills and bundles are mounted, so it is not a fixed list this reference can enumerate. A built-in name always wins a collision with a skill; among skills, the first one registered wins; every collision is reported, never silently duplicated.

### Palette behavior

Palette group order: **During → Parallel → Ship → Between → Repair**. The palette filters rows by substring of the command name; group headers show only when the filter is exactly `/`. Running a command always echoes it as a user line first.

## Keybindings

The full keymap is a literal data table (`ui/keymap.py`) feeding both the Textual bindings and the on-screen footer hints, so a key advertised on screen is always a key that actually works.

### Full keymap

| Action | Key(s) | Context(s) | On-screen label |
|---|---|---|---|
| `submit` | enter | idle | enter |
| `steer` | enter | running | enter |
| `insert_newline` | ctrl+j, ctrl+enter | all except approval | ctrl+j |
| `history_prev` | up | idle, running | ↑ |
| `history_next` | down | idle, running | ↓ |
| `queue_message` | shift+enter | all except approval | shift+enter |
| `queue_message` (fallback) | alt+enter | all except approval | alt+enter (advertised only when terminal probe says shift+enter can't arrive) |
| `recall_queued` | alt+up | idle, running | alt+↑ |
| `cycle_mode` | shift+tab | all except approval | shift+tab |
| `cycle_permission` | ctrl+p | all except approval | ctrl-p |
| `cycle_effort` | ctrl+b | all except approval | ctrl-b effort |
| `toggle_lanes` | ctrl+t | all except approval | ctrl-t |
| `cycle_tail` | ctrl+o | all except approval | ctrl-o |
| `open_external_editor` | ctrl+e | all except approval | ctrl-e edit |
| `toggle_thinking` | ctrl+g | running | ctrl-g think |
| `show_timeline` | ctrl+g (same chord, idle branch) | idle | ctrl-g timeline |
| `show_ledger` | ctrl+l | all except approval | ctrl-l |
| `show_needs_you` | ctrl+y | all except approval | ctrl-y |
| `open_rewind` | ctrl+r | all except approval | ctrl-r |
| `show_keys` | f1 | all except approval | f1 keys |
| `return_to_answer` | ctrl+f | all except approval | ctrl-f answer |
| `plan_drilldown` | ctrl+n | all except approval | ctrl-n |
| `toggle_plan_overflow` | ctrl+h | all except approval | ctrl-h plan |
| `stash_prompt` | ctrl+s | idle, running | ctrl-s stash |
| `palette_up` / `palette_down` | up / down | palette | ↑↓ |
| `palette_run` | enter | palette | enter |
| `mention_up` / `mention_down` | up / down | mention | ↑↓ |
| `mention_accept` | enter, tab | mention | enter/tab |
| `mention_close` | escape | mention | esc |
| `lane_up` / `lane_down` | up / down | lanes | ↑↓ |
| `focus_lane` | enter | lanes | enter |
| `rewind_prev` / `rewind_next` | left / right | rewind | ‹ › |
| `rewind_scope_prev` / `rewind_scope_next` | up / down | rewind | ↑↓ mode |
| `rewind_fork` | enter | rewind | enter restore |
| `sessions_up` / `sessions_down` | up / down | sessions | ↑↓ select |
| `sessions_activate` | enter | sessions | enter open |
| `sessions_resume` | r | sessions | r resume |
| `themes_up` / `themes_down` | up / down | themes | ↑↓ preview |
| `themes_choose` | enter | themes | enter keep |
| `timeline_prev` | up, left | timeline | ↑↓ scrub |
| `timeline_next` | down, right | timeline | ↑↓ scrub |
| `timeline_keep` | enter | timeline | enter keep |
| `evidence_prev` / `evidence_next` | left / right | evidence | ←/→ |
| `evidence_expand` | enter | evidence | enter |
| `evidence_detail` | d | evidence | d detail |
| `approval_prev` | left, up | approval | arrows |
| `approval_next` | right, down, tab, shift+tab | approval | arrows |
| `approval_confirm` | enter | approval | enter |
| `approval_defer` | ctrl+y | approval | ctrl-y defer |
| `lane_unfocus` | escape | lane_focus | esc |
| `close_palette` | escape | palette | esc |
| `close_rewind` | escape | rewind | esc |
| `close_sessions` | escape | sessions | esc |
| `close_theme_picker` | escape | themes | esc |
| `close_keys` | escape | keys | esc |
| `close_timeline` | escape | timeline | esc |
| `close_lanes` | escape | lanes | esc |
| `close_evidence` | escape | evidence | esc |
| `approval_deny` | escape | approval | esc |
| `interrupt_running` | escape | running | esc |
| `open_palette` | (display-only; `/` is ordinary composer text) | none | / |

"all except approval" means every context except the modal `approval` bar.

### Esc precedence chain

A **table, not emergent if/else logic** — the first entry whose context is active consumes the `Esc` press:

1. `keys` → `close_keys` (the which-key overlay is read-only chrome; it leads the chain)
2. `lane_focus` → `lane_unfocus`
3. `palette` → `close_palette`
4. `rewind` → `close_rewind`
5. `sessions` → `close_sessions`
6. `themes` → `close_theme_picker`
7. `timeline` → `close_timeline`
8. `lanes` → `close_lanes`
9. `running` → `interrupt_running`

Approval-bar `Esc` and evidence-block `Esc` sit outside this chain — the approval bar owns the keyboard while it's open, and evidence `Esc` only fires while that block has focus. A second `Esc` press within 0.75 seconds of an interrupt opens rewind through the existing picker.

### Notes

- `ctrl+g` is one binding dispatched by run-state, not two separate bindings: `toggle_thinking` (show/hide the live thinking box) while a turn is running, `show_timeline` (open the scrubber) while idle.
- `F1` (`show_keys`) toggles the which-key overlay, rendered from this same table. It never takes composer focus — typing still reaches the composer while it's open.
- Composer placeholder (exact string):

```text
Message Amplifier…  ( ↑ history · ctrl+j newline · enter send · / commands )
```

## File locations

App home resolves the same way everywhere it's needed: an explicit argument wins, else `$AMPLIFIER_HOME`, else `~/.amplifier`.

| Location | Path |
|---|---|
| App home | `~/.amplifier` or `$AMPLIFIER_HOME` |
| Global settings | `~/.amplifier/settings.yaml` |
| Project settings | `<project>/.amplifier/settings.yaml` |
| Local (gitignored) settings | `<project>/.amplifier/settings.local.yaml` |
| Keys file | `~/.amplifier/keys.env` (or `$AMPLIFIER_HOME/keys.env`) |
| Project bundles dir | `<project>/.amplifier/bundles` (highest precedence) |
| User (global) bundles dir | `~/.amplifier/bundles` (2nd precedence) |
| Packaged bundles dir | inside the install itself (lowest precedence) |
| Sessions dir | `~/.amplifier/projects/<project-slug>/sessions/<session-id>/` |
| Session transcript | `.../sessions/<id>/transcript.jsonl` |
| Session metadata | `.../sessions/<id>/metadata.json` |
| Session UI-event ledger | `.../sessions/<id>/ui-events.jsonl` (append-only) |
| Legacy event log (read-only) | `.../sessions/<id>/events.jsonl` — owned by foundation's hooks-logging; the app never writes there |
| Rewind-intent transaction file | `.../sessions/<id>/rewind-intent.json` |
| Control-token store | `~/.amplifier/projects/<slug>/sessions/control-authz.json` |
| Cache (downloaded bundle/module sources) | `~/.amplifier/cache` (auto-regenerates) |
| Bundle discovery registry | `~/.amplifier/registry.json` (auto-regenerates) |
| MCP server config | `~/.amplifier/mcp.json` (+ project `./.amplifier/mcp.json`) |
| Custom routing matrices dir | `~/.amplifier/routing` |
| App update-identity cache file | `~/.amplifier/cache/tui_identity.json` |

`reset` (above) only ever clears categories under the resolved app **home** — it never touches a project's own `.amplifier/` directory.

## Install commands

The short public command, shown first everywhere:

```sh
curl -fsSL https://raw.githubusercontent.com/michaeljabbour/amplifier-app-tui/main/scripts/install.sh | bash
amplifier-tui
```

`scripts/install.sh` itself accepts these flags:

| Flag | Purpose |
|---|---|
| `--ref REF` | Branch, tag, or full 40-character commit SHA to install (default `main`). Always resolved to a full commit before installing. |
| `--no-update-shell` | Do not ask `uv tool update-shell` to add the tool bin directory to `PATH`. |
| `-h`, `--help` | Print usage and exit. |

Pass them to a downloaded copy of the script (`sh ./install.sh --ref <sha>`), or after `bash -s --` when piping.

The hardened, review-first variant — a fail-closed shell wrapper, meant for pinning and reviewing an exact commit before installing — lives on the [Setup]({{ '/setup/' | relative_url }}) page. It is also the exact argv `update` and `reset` use internally to repair/reinstall, but it is not the copy shown to a first-time user.
