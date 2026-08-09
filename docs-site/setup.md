---
layout: default
title: Setup
permalink: /setup/
---

Use setup when you want the shortest path from a clean machine to a working terminal UI.

## Install

Install the app command with uv:

```sh
uv tool install amplifier-app-tui
```

If the command already exists, upgrade it instead:

```sh
uv tool upgrade amplifier-app-tui
```

## First run

Run the setup flow once so the app can check local prerequisites and write its user configuration:

```sh
amplifier-tui setup
```

Then open the TUI:

```sh
amplifier-tui
```

## After setup

Go to the [quickstart](../quickstart/) for the shortest tour of the screen, keys, and everyday commands.
