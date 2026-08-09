---
layout: default
title: Quickstart
permalink: /quickstart/
---

This page is the small tour after setup is complete.

## Open the app

```sh
amplifier-tui
```

## Start a session

1. Pick the project directory you want the assistant to work in.
2. Ask for one concrete outcome.
3. Review proposed file changes before approving them.
4. Run the relevant test command from the terminal when the change is ready.

## A good first prompt

```text
Inspect this repository, find the smallest safe fix for the failing test, implement it, and rerun that focused test.
```

Keep the first task narrow. It is easier to trust the loop when the expected result is easy to check.
