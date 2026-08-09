---
layout: default
title: Update and reset
permalink: /update-reset/
---

Use these commands when the installed app is stale or local state needs a clean restart.

## Update

```sh
uv tool upgrade amplifier-app-tui
```

Then reopen the app:

```sh
amplifier-tui
```

## Reset local app state

Use the app reset command when local configuration or cached state is the problem:

```sh
amplifier-tui reset
```

Resetting should be a deliberate step. If you only need a newer version, update first.
