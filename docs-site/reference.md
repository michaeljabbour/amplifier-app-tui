---
layout: default
title: Reference
permalink: /reference/
---

A short list of commands worth keeping nearby.

## User commands

```sh
amplifier-tui
amplifier-tui setup
amplifier-tui doctor
amplifier-tui reset
```

## Install and update

```sh
uv tool install amplifier-app-tui
uv tool upgrade amplifier-app-tui
```

## Contributor checks

```sh
uv run pytest -q
uv run ruff check .
uv run pyright src/
```
