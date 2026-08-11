---
layout: default
title: Troubleshooting
permalink: /troubleshooting/
---

Work from the narrowest check that could explain what you are seeing. Install problems and runtime
problems look similar from the outside but almost never share a fix.

## Start here

| Symptom | Likely cause | Fix |
|---|---|---|
| `{{ site.data.product.command }}: command not found` | `PATH` not refreshed in this shell | `uv tool update-shell`, then restart the shell |
| Install script produced nothing | Download blocked or interrupted | Download the script, then run it locally |
| `uv: command not found`, or uv errors | uv missing or broken | Repair uv, then rerun the installer |
| Install fails on the interpreter | Python floor not met | Let uv provision Python 3.12+ |
| `✗ cannot launch: no provider configured` | No provider set up yet | Run `{{ site.data.product.command }}` and follow first-run setup |
| `... is missing credentials: <VAR> not set` | The provider's own env vars are unset | Set exactly the variables named in the message |
| An Anthropic error you never asked for | The packaged fallback is winning selection | Fix provider priority, not the Anthropic key |
| The app behaves like older code | The installed app is stale | `{{ site.data.product.command }} update` |
| A bundle or module looks out of date | Source cache is stale | `{{ site.data.product.command }} bundle refresh` |
| Local state looks corrupt | Cache or registry damage | `{{ site.data.product.command }} reset` |

## `{{ site.data.product.command }}: command not found`

**Cause.** The installer put the executable in uv's tool bin directory, but this shell started
before that directory joined `PATH`. The install itself is usually fine.

**Fix.** Ask uv to repair the shell, then open a new terminal:

```sh
uv tool update-shell
```

Or run the executable by absolute path, which never depends on `PATH`:

```sh
"$(uv tool dir --bin)/{{ site.data.product.command }}"
```

If the command still resolves to something unexpected after an uninstall or a second install, look
before deleting anything:

```sh
type -a {{ site.data.product.command }}
uv tool list
```

## The install download failed

**Symptom.** The one-line install printed nothing useful, exited oddly, or left no `{{ site.data.product.command }}`
behind. Curl failures, TLS interception, a corporate proxy, and `403` responses all land here.

**Cause.** The bootstrap script is fetched over HTTPS from `raw.githubusercontent.com`. When that
fetch is blocked, truncated, or rewritten, the piped shell can receive nothing at all.

**Fix.** Separate the download from the run so the failure becomes visible:

```sh
curl -fsSL https://raw.githubusercontent.com/michaeljabbour/amplifier-app-tui/main/scripts/install.sh -o install.sh
sh ./install.sh
```

If `curl` itself fails, the problem is network reach: the installer needs GitHub, and `astral.sh`
too when it has to bootstrap uv. Check proxy and TLS settings before retrying. The review-first
form, which installs one specific reviewed commit, is documented in the
[install reference]({{ '/setup/install-reference/' | relative_url }}).

## `uv` is missing or broken

**Cause.** The installer looks for an existing uv (`AMPLIFIER_TUI_UV_BIN`, then `uv` on `PATH`,
then `~/.local/bin/uv`, then `~/.cargo/bin/uv`) and installs it from the official Astral installer
only when none is found. A half-installed uv fails that probe instead.

**Fix.** Confirm uv answers for itself, and repair it if it does not:

```sh
uv --version
```

uv stays load-bearing after install: `{{ site.data.product.command }} update`, `{{ site.data.product.command }} reset`, and
`{{ site.data.product.command }} bundle refresh --force` all shell out to it for reinstall and cache cleaning. A
broken uv breaks those paths too.

## Python version floor not met

**Cause.** The app requires **Python 3.12+**.

**Fix.** Usually nothing. You do not need to pre-install Python — uv prepares a compatible,
isolated interpreter for the tool's own environment. If the install fails at the interpreter step,
repair uv rather than installing a system Python for the app to borrow.

## Provider credentials missing

**Symptom.** The launch preflight runs before the full-screen UI takes over, so a credential
problem prints as plain text and exits instead of flashing an unusable screen:

```text
✗ cannot launch: provider '<id>' is missing credentials: <VAR1, VAR2> not set
→ run `{{ site.data.product.command }} config` to configure a provider, or set the variable(s) named above
```

With nothing configured at all, the same preflight reports:

```text
✗ cannot launch: no provider configured
→ run `{{ site.data.product.command }} config` to configure a provider
```

**Fix.** Set exactly the variables the message names. Every provider declares its own credential
variables, so do not guess at a `<NAME>_API_KEY` convention — use the printed names. On an
interactive terminal you can simply run `{{ site.data.product.command }}`: first run walks you through provider
setup and writes the key to `keys.env` in the app home.

If the message instead reads `provider '<id>' mounted but does not satisfy the Provider protocol`,
credentials are not the problem — the module is. Run `{{ site.data.product.command }} doctor` for the full diagnosis.

## Provider module failed to import

**Symptom.** The launch preflight stops with:

```text
✗ cannot launch: provider '<id>' module failed to import: No module named 'amplifier_module_<id>'
→ the provider's module source is not installed (a cold install or fetch hiccup) — re-fetch it with `{{ site.data.product.command }} bundle refresh --force`, then retry; if it persists, run `{{ site.data.product.command }} doctor`
```

**Cause.** The provider's source was never fetched into the local cache, so nothing could be
imported. This is the cold-install shape — a first boot that was interrupted, or a fetch that
hiccuped — not a defect in the module itself. `doctor` cannot help here: it re-runs the same
resolution and prints the same error.

**Fix.** Re-fetch the bundle sources, then launch again:

```sh
{{ site.data.product.command }} bundle refresh --force
```

`--force` cleans uv's cache first, so a source pinned to a floating ref (`@main`) cannot resolve
back to the same absent copy. If the error survives a forced refresh, the module genuinely is
broken — run `{{ site.data.product.command }} doctor` for the full diagnosis.

## Wrong provider selected, or an unexpected Anthropic error

This is the one that most often sends people down the wrong path.

**Symptom.** You configured vLLM, Kimi, or another provider, but the app talks to Anthropic —
usually surfacing as an Anthropic credential or model error you never asked for.

**Cause.** The packaged bundle ships `provider-anthropic` as a **fallback at priority `100`**. The
app hard-fails at zero providers, so the bundle always keeps one default mounted. Provider
selection is **lower priority wins**, and an absent priority counts as `100`. If your own provider
carries no explicit priority — or a number that does not beat `100` — the fallback wins.

**Not the fix:** adding an Anthropic API key. That only makes the *wrong* provider work. If you
intended to use a different provider, change the priority instead.

**Fix — make your provider win.**

```sh
{{ site.data.product.command }} provider list        # ★ marks the provider that wins today
{{ site.data.product.command }} provider use kimi    # the name you gave your vLLM/Kimi entry
{{ site.data.product.command }} provider list        # confirm ★ moved
```

`provider use` writes priority `1` onto the matched entry and demotes any other priority-`1` entry
to `10`, across every scope holding it. `1` beats the packaged fallback's `100` because lower wins.
Entries written by `{{ site.data.product.command }} init` and `{{ site.data.product.command }} provider add` already land at priority
`1`, so a freshly added provider wins by construction — you never edit or remove the bundled
Anthropic entry.

By hand, the entry lives in the `config.providers` list of the settings file for its scope:

```yaml
# ~/.amplifier/settings.yaml
config:
  providers:
    - id: kimi          # the id you gave the entry, else its module id
      config:
        priority: 1     # lower wins; the packaged Anthropic fallback sits at 100
```

**Fix — one run only.** To point a single launch at a provider without persisting anything:

```sh
{{ site.data.product.command }} --provider kimi
```

`--provider` stamps priority `0` in memory for that process, so it beats every configured entry,
and it is never written to a settings file. `--model` may be added, but it requires `--provider`.

## First run, and what `doctor` reports

```sh
{{ site.data.product.command }} doctor
```

`doctor` exits `0` when the install is ready and `1` when findings exist, so it is safe in a
script. It is not a surface check: it runs the same bundle and provider preflight an interactive
boot runs, in strict mode, so it proves credentials actually work rather than only proving a bundle
resolves. Fix the first finding, then run it again.

On an interactive terminal, plain `{{ site.data.product.command }}` is the first-run path — it detects an
unconfigured machine and walks you through provider setup itself.

## The app behaves like older code

**Cause.** The installed app package is behind the latest source commit.

```sh
{{ site.data.product.command }} version   # what is actually installed
{{ site.data.product.command }} update    # update the app itself
```

From an editable or dev checkout, `{{ site.data.product.command }} update` deliberately refuses to run the global
installer and tells you to run `git pull --ff-only && uv sync` in the checkout instead. Full flag
list: [Update and reset]({{ '/update-reset/' | relative_url }}).

## A bundle or module looks out of date

**Cause.** Mounted bundle and module sources have their own cache, separate from the app package.
Top-level `{{ site.data.product.command }} update` does not touch it.

```sh
{{ site.data.product.command }} bundle refresh --check-only   # report only
{{ site.data.product.command }} bundle refresh                # apply
{{ site.data.product.command }} bundle refresh --force        # uv cache clean first, then re-fetch every source
```

Use `--force` when a source is pinned to a floating ref such as `@main` and keeps resolving back to
the same cached copy.

## Local state looks broken

**Cause.** A damaged download cache or bundle discovery registry under the app home.

```sh
{{ site.data.product.command }} reset --dry-run   # see exactly what would be removed
{{ site.data.product.command }} reset             # clear cache + registry, then repair the install
```

By default this clears only `cache` and `registry` — both auto-regenerate — and preserves your
config, keys, sessions, and locally added bundles. Prefer `{{ site.data.product.command }} reset --no-reinstall` when
the installed tool is fine and you only want local state cleared, or when you are offline and
cannot reach the install source.

## `reset` or `bundle refresh`?

They clean different things and are not interchangeable.

| Use | When |
|---|---|
| `{{ site.data.product.command }} bundle refresh` | Bundle and module *sources* are stale and you want newer ones fetched into the cache. |
| `{{ site.data.product.command }} reset` | Local state under the app home is *broken*, and clearing the cache and registry is the repair. |

Old sources: refresh them. Damaged local state: reset it. If neither explains the symptom, check
the app version itself — `{{ site.data.product.command }} update` is a third, separate concern.

## More help

- [Update and reset]({{ '/update-reset/' | relative_url }}) — the three maintenance commands in full.
- [Configuration]({{ '/configuration/' | relative_url }}) — where settings, keys, and bundles live.
- [Setup]({{ '/setup/' | relative_url }}) — install from scratch.
- [Install reference]({{ '/setup/install-reference/' | relative_url }}) —
  requirements, review-first install, and uninstall.
- [Complete user guide]({{ '/reference/user-guide/' | relative_url }}) —
  the exhaustive in-app reference.
- [Settings reference]({{ '/configuration/settings/' | relative_url }}) —
  the full settings schema, including provider entries.
