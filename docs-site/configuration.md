---
layout: default
title: Configuration
permalink: /configuration/
---

{{ site.data.product.display_name }} keeps all of its configuration on your machine — there is no hosted account or cloud settings store. This page maps every file the app reads or writes, explains exactly how it picks a provider when more than one is configured, and lists the environment variables that matter.

For a guided control center, run:

```sh
{{ site.data.product.command }} config
```

The menu starts with a redacted dashboard, keeps the current write scope visible, and gives
one numbered path each for providers, models and routing, bundles, directory access,
notifications, settings paths, and maintenance previews. `{{ site.data.product.command }} config show --json`
is the scriptable read-only snapshot; `{{ site.data.product.command }} config paths --json` lists settings
locations without reading or printing secret values.

<figure class="terminal-shot">
  <img src="{{ '/assets/screenshots/config-control-center.png' | relative_url }}" alt="Forge terminal session showing the Amplifier configuration control center, its redacted status summary, numbered setup areas, and global write target">
  <figcaption>The real configuration control center, captured during Forge terminal QA.</figcaption>
</figure>

## Where configuration lives

Every location below hangs off one root, the **app home**: `~/.amplifier` by default, or wherever `$AMPLIFIER_HOME` points if you set it.

| What | Location |
|---|---|
| App home | `~/.amplifier` (or `$AMPLIFIER_HOME`, if set) |
| Global settings | `~/.amplifier/settings.yaml` |
| Project settings | `<project>/.amplifier/settings.yaml` |
| Local settings (gitignored) | `<project>/.amplifier/settings.local.yaml` |
| Keys file | `~/.amplifier/keys.env` (or `$AMPLIFIER_HOME/keys.env`) |
| Project bundle directory | `<project>/.amplifier/bundles` — checked first |
| Global bundle directory | `~/.amplifier/bundles` — checked second |
| Packaged bundle directory | `<install>/amplifier_app_tui/data/bundles` — the bundles shipped with the install itself, checked last |
| Sessions directory | `~/.amplifier/projects/<project-slug>/sessions/<session-id>/` |
| Cache | `~/.amplifier/cache` |
| Bundle discovery registry | `~/.amplifier/registry.json` |
| MCP server config | `~/.amplifier/mcp.json`, plus a project-local `./.amplifier/mcp.json` |
| Custom routing matrices | `~/.amplifier/routing` |

Most commands that write configuration — `provider add`, `bundle use`, `routing use`, `allowed-dirs add`, and others — accept a **scope** flag that picks which settings file gets the write:

- `--global` → `~/.amplifier/settings.yaml` (the default when no scope flag is given)
- `--project` → `<project>/.amplifier/settings.yaml`
- `--local` → `<project>/.amplifier/settings.local.yaml`, meant to be gitignored

`allowed-dirs list` / `denied-dirs list` accept the same three flags too, but as a **filter** on what to display rather than where to write.

None of the files above are touched by an ordinary `{{ site.data.product.command }} reset` unless you name them explicitly: session history, all three settings files, `mcp.json`, `routing`, locally-added bundles, and `keys.env` are all preserved by default. Only `cache` and the bundle discovery `registry.json` clear automatically. See [Update and reset]({{ '/update-reset/' | relative_url }}) for the full command.

## Providers

A provider is what actually talks to a model API — Anthropic, a self-hosted vLLM endpoint, and so on. You can configure several at once; exactly one of them serves any given turn. The next section explains exactly how that one gets picked.

### Set one up

`{{ site.data.product.command }} init` opens the same numbered control center as `config`, starting
with providers so first setup stays focused. The first time you launch with zero providers, the app
opens a focused provider wizard before the full-screen interface. Passing any `init` flag skips the
control center and uses the direct setup path; outside a terminal, add `--yes` or use `--from-env`
so the command can never hang waiting for input:

| Flag | Help text |
|---|---|
| `--provider`, `-p` | Provider to set up (e.g. anthropic). |
| `--api-key` | API key (non-interactive; else prompted). |
| `--base-url` | Optional provider base-URL override. |
| `--model` | Default model for the provider. |
| `--from-env` | Non-interactive: configure a provider detected from env vars. |
| `--yes`, `-y` | Non-interactive: never prompt (needs --api-key). |

### Manage providers

Run `provider add` with no arguments for an interactive picker and a wizard built from the provider's own declared fields; pass a `PROVIDER_TYPE` (for example `anthropic`) to skip straight to that provider's wizard. It covers the same non-interactive ground as `init`, plus its own `--scope` flag (the same three values as the scope flags above) and an `--instance-id` flag for naming a second instance of the same provider type, so routing matrices can target it specifically. Full flag wording is in [Reference]({{ '/reference/' | relative_url }}).

The rest of provider management is one command each:

| Command | Purpose | Writes to |
|---|---|---|
| `provider list` | Lists configured providers. `★` marks the primary (lowest-priority) provider. | Read-only |
| `provider use NAME` | Sets `NAME` to priority `1`, demoting any other priority-`1` entry to `10`, across every scope holding it. | Every settings scope holding a matching entry |
| `provider remove NAME` | Previews the provider and defaults to **No** before removing its settings entries. Stored credentials are kept. Add `--yes` for automation. | Every settings scope holding a matching entry |
| `provider dashboard` | Shows configured providers, the current primary, and a hint for switching. | Read-only |

A typical first pass looks like this:

```sh
{{ site.data.product.command }} provider add anthropic
{{ site.data.product.command }} provider list
{{ site.data.product.command }} provider use anthropic
```

Whichever command adds a provider, the split is always the same: the API key (or other secret fields) goes into `keys.env` at the app home — written with a file lock and `chmod 600` — while the provider entry itself (module, priority, default model, and so on) goes into `config.providers` in the settings file for the write scope you chose.

If a provider looks configured but the app still won't launch with it, run `{{ site.data.product.command }} doctor` — it reports the exact problem (no provider configured at all, a provider that mounted but doesn't behave like one, or one that's missing its own declared credential variables) instead of a generic failure. See [Troubleshooting]({{ '/troubleshooting/' | relative_url }}).

## Provider priority and the bundled fallback

<div class="callout">
Provider selection is <strong>lower-priority-wins</strong>. The bundled Anthropic fallback ships at priority <code>100</code>; any provider you add starts at priority <code>1</code> and beats it automatically.
</div>

Provider selection is **lower-priority-wins**: at boot, {{ site.data.product.display_name }} sorts every configured provider by its `config.priority` value, ascending, and boots the first one. A provider entry with no `priority` set is treated as priority `100`.

Every install ships with one provider already configured: a bundled Anthropic fallback, `provider-anthropic`, deliberately parked at fallback priority `100` — low enough that the app is never stuck with zero providers, but high enough that it never outranks anything you add yourself. `{{ site.data.product.command }} init` and `provider add` both write a freshly added provider at priority `1` by default, and `provider use NAME` sets any existing provider to priority `1` too, demoting whatever previously held that slot to `10`. Because `1` is lower than the fallback's `100`, your own provider wins the boot automatically — you never have to touch, edit, or remove the bundled Anthropic entry to make that happen.

```yaml
config:
  providers:
    - module: <your-provider-module>   # e.g. a self-hosted vLLM or Kimi provider
      config:
        priority: 1                     # lower number: this wins
    - module: provider-anthropic
      config:
        priority: 100                   # bundled fallback: only used if nothing else qualifies
```

If two entries ever share the same priority, the tie resolves by **list order** — whichever one appears first in the merged list wins. That is exactly why the bundled fallback sits at `100` instead of `1`: if it were tied with a fresh install's first user-added provider, list order alone would decide the winner, and a fallback should never be in a position to win that coin flip.

`--provider` (and `--model`) at launch override all of this, but only for a single run. They move the named provider to the front of the list and stamp its priority to `0` in memory — lower than anything a settings file can express — so the override always wins, even over your own priority-`1` entry. Nothing under `--provider`/`--model` is written to a settings file; the effect lasts for that one invocation of `run`, `serve`, or the interactive launch.

## Models and routing

`routing` controls which model plays which role — for example, a fast model for tool-heavy turns and a stronger one for planning — once a provider is already selected. It layers on top of provider selection; it never changes *which provider* wins, only *which model* that provider uses for a given role.

`routing list` / `use` / `show` / `create` / `manage` cover the matrix lifecycle: `use` (scope options apply) takes effect at the next session start, and `show --detailed` prints the full candidate waterfall per role instead of just the winner. New matrices built with `create` persist under `~/.amplifier/routing`. Full flag-by-flag wording is in [Reference]({{ '/reference/' | relative_url }}).

`--model` only ever appears alongside `--provider` — the top-level launch flags, and the equivalent flags on `run` and `serve`, all reject a `--model` given without `--provider`. When `init` or `provider add` sets a default model for a provider, that model is written onto the provider's own entry (`config.default_model`), and a matching routing-matrix hint is persisted for that provider at the same time, so routing keeps working after you switch which provider is primary. Inside a running session, `/model` lists the available models, and `/model [provider] <name>` switches the live model for that session.

## Bundles

A bundle is the mount plan for a session: which providers, tools, and other modules get composed together when {{ site.data.product.display_name }} starts. `--bundle` (available on the top-level launch, `run`, `serve`, `tool list`, `resume`, and `continue`) points at one for a single invocation; `bundle use` changes the default (scope options apply, the same as providers and routing).

`bundle list` / `current` / `use` / `clear` / `show` cover discovery and activation; `bundle add URI` registers a new bundle after validating that it loads (`--name`/`-n` for the registry name, `--app` to also compose it onto every session, `--warm` to pre-install its modules immediately). `bundle remove` drops a registered bundle and `bundle update` checks it for a newer version; `bundle warm NAME` pre-installs an already-registered bundle's modules outside the normal boot burst. Full flag-by-flag wording is in [Reference]({{ '/reference/' | relative_url }}).

Bundle names are resolved against the three directories from the table at the top of this page, in order: the project's bundle directory first, then the global one, then the bundles packaged with the install itself. A name registered in a higher-precedence directory wins.

`{{ site.data.product.command }} bundle refresh` is a separate, advanced command. It refreshes the **source caches** for every mounted bundle and module — what got downloaded, not your configuration — plus advisory update rows for the app itself. It is not the app-update command; that's `{{ site.data.product.command }} update` (see [Update and reset]({{ '/update-reset/' | relative_url }})).

## Settings file

Global, project, and local settings are plain YAML files that share the same shape. Every command on this page only ever adds or edits entries under a top-level `config:` key — the file format itself never changes:

```yaml
config:
  providers:
    - module: provider-anthropic     # identity: module (or id / instance_id, if set)
      config:
        priority: 100                 # lower number wins; absent means 100
        default_model: <model-id>     # set automatically when init/provider add picks a model
```

| Key | Meaning |
|---|---|
| `config.providers` | The list of configured providers. Merged with the active bundle's own provider entries by identity (`id`/`instance_id` if set, else `module`). |
| `config.providers[].module` | Which provider module this entry configures, e.g. `provider-anthropic`. |
| `config.providers[].config.priority` | Selection priority for this entry. Lower wins; absent means `100`. |
| `config.providers[].config.default_model` | The default model for this provider entry. |
| `sources.modules` | Per-module source overrides. `{{ site.data.product.command }} source show MODULE_ID` prints the full resolution chain for one module: environment variable, then workspace, then this key, then the effective result. |

For the complete schema — every key, every provider field, merge rule, environment variable,
and validation quirk — see the [settings reference]({{ '/configuration/settings/' | relative_url }}).

## Directory permissions

`allowed-dirs` and `denied-dirs` govern which directories the AI may write to, beyond the ordinary project-relative writes it already does. Both groups share the same three subcommands:

| Command | What it does |
|---|---|
| `allowed-dirs add PATH` / `denied-dirs add PATH` | Adds a directory. Scope options apply (`--local`, `--project`, or `--global`; default `global`). |
| `allowed-dirs list` / `denied-dirs list` | Lists entries. Accepts the same three flags, but as a filter on what to show. |
| `allowed-dirs remove PATH` / `denied-dirs remove PATH` | Removes a directory. Scope options apply. |

Inside a running session, `/allowed-dirs` and `/denied-dirs` list or edit the same directories without leaving the TUI.

## Environment variables

{{ site.data.product.display_name }} reads very few environment variables directly; almost everything else lives in a file under the app home.

| Variable | Effect |
|---|---|
| `AMPLIFIER_HOME` | Overrides the app home (default `~/.amplifier`). Every path in the table at the top of this page moves under it. |
| A provider's own credential variable, e.g. `ANTHROPIC_API_KEY` | Only matters when **no** provider is configured yet: a non-interactive launch will then try to auto-configure a provider from a detected credential variable like this one, instead of failing outright. |

Each provider declares its own required credential variable(s) — there's no single `<PROVIDER>_API_KEY` naming convention across all of them. And if a provider is already configured and the *wrong* one keeps winning, the fix is its priority (above), not another environment variable.

## Choose the right configuration surface

- There is no `setup` subcommand. First-run configuration happens automatically: the first time you run bare `{{ site.data.product.command }}`, it walks an interactive terminal through provider setup before anything else (the *first-run gate*). You can reopen the same console any time with `{{ site.data.product.command }} init`.
- Use top-level `{{ site.data.product.command }} config` for durable setup across providers, routing, bundles,
  directories, notifications, and maintenance. Use `{{ site.data.product.command }} init` when you only need
  provider-and-routing onboarding. Use the in-session `/config` command for the currently
  mounted live session; it is intentionally a different, temporary surface.

## See also

- [Update and reset]({{ '/update-reset/' | relative_url }}) — the difference between updating the app and refreshing bundle/module caches.
- [Reference]({{ '/reference/' | relative_url }}) — the full command list in one place.
- [Troubleshooting]({{ '/troubleshooting/' | relative_url }}) — provider credential and selection problems.
