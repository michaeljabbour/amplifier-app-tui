---
layout: default
title: Amplifier App TUI
permalink: /
---

Amplifier TUI is a full-screen terminal interface for [Amplifier](https://github.com/microsoft/amplifier). You type a task into a composer and watch the work land in a live transcript. You steer it while the turn is still running and approve the actions it wants to take. You can rewind when it goes the wrong way — all without leaving the keyboard. It installs as its own command, `amplifier-tui`, and reads the same `~/.amplifier/` configuration the wider Amplifier platform uses, so an existing setup carries over.

## The whole support story

Three commands. Everything else on this site is optional depth.

| Command | What it does |
|---|---|
| `amplifier-tui` | Launch the app. The first run walks you through provider setup if nothing is configured yet. |
| `amplifier-tui update` | Update the installed app itself to the current `main` commit. |
| `amplifier-tui reset` | Clear the regenerable cache and registry state, then repair the install. Sessions, settings, and keys are kept. |

## Install

On macOS, Linux, or WSL:

```sh
curl -fsSL https://raw.githubusercontent.com/michaeljabbour/amplifier-app-tui/main/scripts/install.sh | bash
```

Then launch it:

```sh
amplifier-tui
```

The installer fetches `uv` from Astral only if you do not already have it, resolves `main` to one exact commit, installs under that commit's committed lockfile, and prints the path to the verified executable. Requirements, verification, and the review-first install form are on the [Setup]({{ '/setup/' | relative_url }}) page.

## Try it with no credentials

`--demo` is a flag on the app, not a subcommand. It runs a scripted session that is fully offline — no bundle, no network, no API key:

```sh
amplifier-tui --demo
```

Use it to see the real interface before you decide to configure a provider.

## Documentation map

**Getting started**

- [Setup]({{ '/setup/' | relative_url }}) — requirements, install, verification, provider configuration, uninstall.
- [Quickstart]({{ '/quickstart/' | relative_url }}) — your first session: prompt, steer, palette, interrupt, resume.
- [Update and reset]({{ '/update-reset/' | relative_url }}) — keeping the install current and repairing it safely.

**Using the TUI**

- [Using the TUI]({{ '/using-the-tui/' | relative_url }}) — transcript and composer, modes, approvals, subagent lanes, rewind, sessions.

**Configuration**

- [Configuration]({{ '/configuration/' | relative_url }}) — settings scopes, credentials, providers and priority, routing, bundles, write boundaries.

**Reference**

- [Reference]({{ '/reference/' | relative_url }}) — CLI commands, slash commands, keybindings, file locations, headless output contract.

**Troubleshooting**

- [Troubleshooting]({{ '/troubleshooting/' | relative_url }}) — command not found, install failures, missing credentials, wrong provider selected.

**Development**

- [Development]({{ '/development/' | relative_url }}) — clone, run from source, and the local test gates.

## For agents

[`llms.txt`]({{ '/llms.txt' | relative_url }}) is the machine-readable index of this site. Read it first to discover every page before crawling anything else.

## Engineering documentation

Deeper internal documentation lives in the repository, not on this site:

- [README](https://github.com/michaeljabbour/amplifier-app-tui/blob/main/README.md)
- [Install guide](https://github.com/michaeljabbour/amplifier-app-tui/blob/main/docs/INSTALL.md)
- [User guide](https://github.com/michaeljabbour/amplifier-app-tui/blob/main/docs/USER-GUIDE.md)
- [Settings reference](https://github.com/michaeljabbour/amplifier-app-tui/blob/main/docs/SETTINGS.md)
- [Architecture](https://github.com/michaeljabbour/amplifier-app-tui/blob/main/docs/ARCHITECTURE.md)
- [Design spec](https://github.com/michaeljabbour/amplifier-app-tui/blob/main/docs/DESIGN-SPEC.md)

## What this project does not ship

Being explicit saves you a search:

- No PyPI package, Homebrew/WinGet/apt channel, or native binary — the install is a source install of Python under a committed lockfile.
- No signed release artifact. The bootstrap script you download is not signed.
- No background updater. Nothing updates until you run a command yourself.
- No native Windows support. WSL works and reports as Linux.
