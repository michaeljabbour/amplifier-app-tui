---
layout: default
title: Setup
permalink: /setup/
---

This page takes a clean machine to a working terminal UI, then shows how to keep it working.

## System requirements

| Requirement | Detail |
|---|---|
| Operating system | macOS, Linux, or WSL |
| Architecture | 64-bit x86_64/amd64 or arm64/aarch64 |
| Python | 3.12 or newer, provisioned by `uv` |
| `uv` | Optional — installed if missing |
| Other tools | `git`, `curl` |
| Network | Outbound access to GitHub and Astral |
| Credentials | Real sessions only; `--demo` needs none |

The installer checks the operating system and nothing else: `uname -s` must report macOS or Linux, so native Windows is out — use WSL, which takes the Linux path. Architecture is never checked; 64-bit x86_64 and arm64 are simply what this project builds and tests on. You do not install Python or `uv` yourself — the installer fetches `uv` from the official Astral installer when it is missing, and `uv` provisions the interpreter.

## Install

```sh
curl -fsSL https://raw.githubusercontent.com/michaeljabbour/amplifier-app-tui/main/scripts/install.sh | bash
```

The installer requires `git`, brings in `uv` when it is missing, resolves `main` once to a full 40-character commit, checks out that commit, installs the app under that commit's committed `uv.lock`, verifies the executable, makes its directory discoverable on `PATH`, and prints the exact path to run.

This is a source channel, not a signed release. The commit and the locked dependency versions are pinned after resolution; the bootstrap script you download is not a signed artifact. If that matters to you, use the [review-first install](#advanced-review-first-install) below.

If the shell cannot find the command afterward, restart the shell or run `uv tool update-shell`.

## Verify your installation

Print what actually got installed:

```sh
amplifier-tui version
```

It reports `amplifier-tui` plus the `core` and `foundation` versions it resolved. The app label includes the short commit for a git-sourced install — this project does not bump the version on every commit, so the commit is the signal that tells two builds apart.

Then run the checkup:

```sh
amplifier-tui doctor
```

`doctor` is read-only and its exit code is the contract: **0 means ready, 1 means it found something**. It runs the same bundle and provider preflight a real launch runs, in strict mode, so a clean result means credentials actually resolve — not merely that a bundle file parses.

To see what a launch would resolve without launching anything:

```sh
amplifier-tui --dry-run
```

That prints a "Would Launch" summary — bundle, provider, model, routing — and changes nothing.

## First run

Move into the project you want to work in, then start the app:

```sh
cd ~/code/my-project
amplifier-tui
```

Sessions are stored per project directory, so where you start matters.

There is no separate setup command. On an interactive terminal with no provider configured, the first launch walks you through provider setup itself. In a non-interactive shell it tries to configure a provider from environment variables and, failing that, exits 1 with instructions rather than opening a screen it cannot drive.

If the launch preflight fails, the app prints `✗ cannot launch: <error>` and a `→ <remediation>` line to stderr and exits 1 **before** taking over the terminal, so you never land in a broken full-screen app.

## Run it with no credentials

```sh
amplifier-tui --demo
```

`--demo` is a flag on the app, not a subcommand. It runs a scripted session with no bundle, no network, and no credentials — the first-run gate and the provider preflight are both skipped. It is the right way to look around before you configure anything.

## Configure a provider

To review or change providers later, run:

```sh
amplifier-tui init
```

With no flags this opens the setup console: it shows the configured providers and the active routing resolution, then loops on `[p]` manage providers, `[r]` manage routing, `[w]` change write scope, `[d]` done. Passing any flag skips the console and takes the non-interactive path instead — the flags are listed in the [Reference]({{ '/reference/' | relative_url }}#init).

Secrets are written to `~/.amplifier/keys.env` with `600` permissions. The provider entry itself goes into a settings file — `~/.amplifier/settings.yaml` by default. New entries are written at priority `1`, and lower priority wins, so a provider you configure beats the bundled fallback without you editing anything. See [Configuration]({{ '/configuration/' | relative_url }}) for the full priority model.

## Keeping it healthy

| Command | What it does |
|---|---|
| `amplifier-tui update` | Updates the installed app itself to the current `main` commit, using the same source-installer contract. `--check-only` reports without changing anything. |
| `amplifier-tui reset` | Clears the regenerable cache and registry state, then repairs the install. Sessions, settings, local bundles, and `keys.env` are preserved unless you name them explicitly. |

Nothing updates on its own. There is no background updater, so the installed build stays exactly where you left it until you run one of these.

Two useful variants: `amplifier-tui reset --dry-run` previews what would be removed and changes nothing, and `amplifier-tui reset --no-reinstall` cleans up without repairing the install. Mounted bundle and module source caches are a separate, advanced concern handled by `amplifier-tui bundle refresh` — see [Update and reset]({{ '/update-reset/' | relative_url }}).

## Advanced: review-first install

If you want the piped install to fail closed when the download is missing, blocked, or interrupted, use the hardened wrapper. This is also the exact form the app uses internally for update and repair:

```sh
bash -o pipefail -c "curl --proto '=https' --tlsv1.2 -fsSL https://raw.githubusercontent.com/michaeljabbour/amplifier-app-tui/main/scripts/install.sh | bash -s --"
```

To read the script before running it, download it, inspect it, and run the local copy against a specific commit:

```sh
curl --proto '=https' --tlsv1.2 -fsSL https://raw.githubusercontent.com/michaeljabbour/amplifier-app-tui/main/scripts/install.sh -o install.sh
less install.sh
sh ./install.sh --ref 0123456789abcdef0123456789abcdef01234567
```

Replace the example with the commit you reviewed. Every install uses the selected commit's own `uv.lock`, so a dependency change is always a deliberate repository change. The installer's own flags are listed in the [Reference]({{ '/reference/' | relative_url }}#install-commands).

## Uninstall

```sh
uv tool uninstall amplifier-app-tui
```

There is no uninstall subcommand on the app — removal is a `uv tool` operation. It removes only the app's isolated tool environment and its executable. It deliberately leaves `~/.amplifier/` alone: your keys, settings, sessions, and caches survive, because the full `amplifier` platform CLI may share them. Removing that directory is a separate, destructive decision.

If `amplifier-tui` still resolves after uninstalling, look for a second install or a shell alias before deleting anything else:

```sh
type -a amplifier-tui
uv tool list
```

## Next

- [Quickstart]({{ '/quickstart/' | relative_url }}) — your first session, end to end.
- [Troubleshooting]({{ '/troubleshooting/' | relative_url }}) — when install or launch does not go to plan.
- [Install guide](https://github.com/michaeljabbour/amplifier-app-tui/blob/main/docs/INSTALL.md) — the repository's deeper install reference.
