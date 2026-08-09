---
layout: default
title: Troubleshooting
permalink: /troubleshooting/
---

Start with the narrowest check that can explain the problem.

## Command not found

Confirm the uv tool executable directory is on your shell path, then reopen the terminal.

```sh
uv tool list
```

## Setup did not finish

Run the doctor command and fix the first reported problem before rerunning setup.

```sh
amplifier-tui doctor
amplifier-tui setup
```

## The app behaves like old code

Upgrade the installed tool and start a fresh terminal session.

```sh
uv tool upgrade amplifier-app-tui
```

## Local state looks broken

If update and setup do not help, reset the app-owned state.

```sh
amplifier-tui reset
```
