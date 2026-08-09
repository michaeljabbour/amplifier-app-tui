---
layout: default
title: Update and reset
permalink: /update-reset/
---

One command for everyday use; three more when something is wrong — and of those three,
`{{ site.data.product.command }} bundle refresh` is the advanced one. Nothing here runs on its own: there is no
background updater, so the installed app only changes when you ask it to.

## Which command do I need?

| Command | What it changes | Reach for it when |
|---|---|---|
| `{{ site.data.product.command }}` | Launches the app. Nothing else, once a provider is configured — a first run with none writes `keys.env` and `settings.yaml`. | Everyday use. |
| `{{ site.data.product.command }} update` | The installed app package itself. | The installed app is behind the latest source commit. |
| `{{ site.data.product.command }} bundle refresh` | The source cache behind mounted bundles and modules. Advanced. | Bundle or module sources are stale. |
| `{{ site.data.product.command }} reset` | Local state under the app home, then repairs the install. | Local state is broken and updating did not help. |

`{{ site.data.product.command }} update` and `{{ site.data.product.command }} bundle refresh` are separate commands with separate
jobs. Top-level `update` does **not** touch bundle or module source caches, and
`{{ site.data.product.command }} bundle refresh` never updates the installed app.

## Check what you have first

```sh
{{ site.data.product.command }} version
```

This prints the installed app identity, then the `core` and `foundation` versions it resolved. For
a git-sourced install the label carries the short commit, which is the real signal — this project
does not bump its version string on every commit.

## `{{ site.data.product.command }} update` — update the app

`{{ site.data.product.command }} update` updates the app itself. It resolves the identity of the package that is
actually installed — read from installed distribution metadata, never from a hardcoded version
string — and then acts on how the app got there.

**Installed as a git tool** (the documented install path). The command compares the installed
commit against `main` in the app repository. If the install is behind, it runs the same source
installer the one-line install uses, pinned to the exact commit it just resolved, and the package
is replaced in place. The terminal shows `Installed`, `Available`, `Installing`, and `Verified`
states; each installer phase streams as it runs. It then re-reads installed metadata and refuses
to claim success if the resulting commit does not match the target. Top-level `update` never runs
the slower module/bundle scan.

**Editable or dev checkout** (`uv sync` or `pip install -e` from a clone). The command deliberately
does *not* run the global source installer, because that would clobber a developer's tool story
instead of repairing it. It prints guidance instead:

```text
Dev checkout: not running the global source installer.
Run: git pull --ff-only && uv sync
```

Run that pair yourself inside the checkout.

The version string can remain `0.1.0` while the source changes. The short commits in the
`Installed → Available → Verified` transition are therefore the authoritative build identities.

If you are standing inside a checkout, an unqualified `{{ site.data.product.command }}` still runs
the executable found on `PATH`; it does not automatically use the checkout. Use
`uv run {{ site.data.product.command }}` to exercise the checkout itself, or update the global
tool and confirm its identity with `{{ site.data.product.command }} version`.

### Update flags

| Flag | What it does |
|---|---|
| `--check-only` | Report app update availability; change nothing. |
| `--force` | Run the source installer even if no update is detected. |

The two that change the decision — [all flags in the Reference]({{ '/reference/' | relative_url }}#update).

```sh
{{ site.data.product.command }} update --check-only     # is anything newer?
{{ site.data.product.command }} update -y               # update, no prompt
{{ site.data.product.command }} update --force -v       # repair a wedged install, show the installer command
```

Applying an update asks first and defaults to **No**. Use `--yes` only for an unattended run you
already intend to change.

`--force` is the one to know: when the check reports you are already current but the install still
misbehaves, `--force` runs the source installer anyway.

What it leaves alone: bundle and module source caches. Those belong to
`{{ site.data.product.command }} bundle refresh`, below.

## `{{ site.data.product.command }} bundle refresh` — refresh bundle and module sources

This is the advanced command, and it is separate on purpose. `{{ site.data.product.command }} bundle refresh`
refreshes the source cache behind every composed bundle: the active bundle, every app overlay
composed onto it (including the routing-matrix overlay when routing is enabled), and the pinned
Anchors include. It also prints advisory rows for the app, core, and foundation packages — advisory
only. It never self-updates the app and never runs the app installer.

| Flag | What it does |
|---|---|
| `--check-only` | Report available updates; change nothing. |
| `--force` | `uv cache clean` first, then re-fetch every source. |

The two that change the decision — [all flags in the Reference]({{ '/reference/' | relative_url }}#bundle).

```sh
{{ site.data.product.command }} bundle refresh --check-only
{{ site.data.product.command }} bundle refresh -y
{{ site.data.product.command }} bundle refresh --force
```

Both the normal and `--force` apply paths preview their work and default to **No**. `--check-only`
never clears the uv cache or records comparison state; cancelling also changes nothing.

Use `--force` when a source is pinned to a floating ref such as `@main`: it cleans the uv cache
first, so those sources genuinely re-fetch instead of resolving back to the same cached copy.
`--verbose` lists every local or non-git source that was skipped, instead of collapsing them into
one summary line.

## `{{ site.data.product.command }} reset` — safe repair

`reset` is a repair command, not a factory wipe. By default it clears only the two
auto-regenerating categories, then repairs the install.

**Cleared by default**

| Category | What it is |
|---|---|
| `cache` | `~/.amplifier/cache` — downloaded bundle and module sources. Regenerates. |
| `registry` | `~/.amplifier/registry.json` — the bundle discovery registry. Regenerates. |

**Preserved by default**

| Category | What it is |
|---|---|
| `config` | `settings.yaml`, `settings.local.yaml`, `mcp.json`, and `routing` in the app home |
| `keys` | `keys.env` — your provider credentials |
| `sessions` | `projects/` — stored session history |
| `bundles` | `bundles/` — bundles you added locally |

Those four are cleared only when you name them explicitly with `--category`. `keys` holds secrets,
so it is never in the default set, and selecting it prints a warning before anything is removed.

`reset` operates only on the resolved app home (`$AMPLIFIER_HOME`, else `~/.amplifier`). It never
touches a project's own `.amplifier/` directory, and it refuses to run against your literal home
directory or any path that does not look like an app home.

### Repair is part of the default

After clearing, `reset` also repairs and reinstalls the tui tool. From an editable or dev checkout
it skips that global reinstall and prints the same `git pull --ff-only && uv sync` guidance. Pass
`--no-reinstall` when you want cleanup only — for example when you are offline, or when the install
itself is fine and you only want the caches gone.

### Reset flags

| Flag | What it does |
|---|---|
| `--category`, `-c NAME` | Category to clear (repeatable or comma-separated). Default: `cache,registry`. |
| `--dry-run` | Preview what would be removed; change nothing. |
| `--list` | List the category taxonomy and exit. |
| `--no-reinstall` | Only clear selected categories; do not repair/reinstall the tui tool. |

The four this page walks through — [all flags in the Reference]({{ '/reference/' | relative_url }}#reset).

Look before you leap:

```sh
{{ site.data.product.command }} reset --list      # the category taxonomy, then exit
{{ site.data.product.command }} reset --dry-run   # what would be removed, and the repair command that would run
```

Then run it:

```sh
{{ site.data.product.command }} reset                       # clear cache + registry, then repair
{{ site.data.product.command }} reset --no-reinstall        # clear only; leave the installed tool alone
{{ site.data.product.command }} reset -c cache -y           # scripted; cache only, no prompt
{{ site.data.product.command }} reset --install-source .    # repair from the clone you are standing in
```

## When to use which

| Situation | Command |
|---|---|
| You just want to work | `{{ site.data.product.command }}` |
| The installed app is stale | `{{ site.data.product.command }} update` |
| Bundle or module sources are stale | `{{ site.data.product.command }} bundle refresh` |
| Local state is broken, or the install is wedged | `{{ site.data.product.command }} reset` |

Work narrow to wide: `{{ site.data.product.command }} update` for a stale app, `{{ site.data.product.command }} bundle refresh` for
stale bundle and module source caches, `{{ site.data.product.command }} reset` last. Reset is the widest of the
three, so reach for it once the narrower two have failed to explain the problem.

## Next

- [Troubleshooting]({{ '/troubleshooting/' | relative_url }}) — symptom-first fixes, including
  provider selection.
- [Configuration]({{ '/configuration/' | relative_url }}) — where settings, keys, and bundles live.
- [Install reference]({{ '/setup/install-reference/' | relative_url }}) —
  exact installer behavior, updating, verification, and uninstall.
