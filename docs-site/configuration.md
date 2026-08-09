---
layout: default
title: Configuration
permalink: /configuration/
---

Configuration is local to your machine. The setup flow creates or updates the app-owned files it needs.

## Open setup again

```sh
amplifier-tui setup
```

## Check the current state

```sh
amplifier-tui doctor
```

## Practical rule

Let the app write its own configuration when possible. Manual edits are best saved for cases where a diagnostic points to a specific file and value.
