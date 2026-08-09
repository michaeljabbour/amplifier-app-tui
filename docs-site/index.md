---
layout: default
title: Amplifier App TUI
permalink: /
---

Amplifier App TUI is a full-screen terminal interface for working with Amplifier without leaving the keyboard.

<div class="callout">
Start with <a href="{{ '/setup/' | relative_url }}">Setup</a>, then take the <a href="{{ '/quickstart/' | relative_url }}">quickstart</a> path once the command is available.
</div>

## What is here

- [Setup]({{ '/setup/' | relative_url }}): install the command and run first-time checks.
- [Quickstart]({{ '/quickstart/' | relative_url }}): open the TUI and orient yourself.
- [Update and reset]({{ '/update-reset/' | relative_url }}): refresh the app or return to a clean local state.
- [Using the TUI]({{ '/using-the-tui/' | relative_url }}): understand the main screen areas and keyboard flow.
- [Configuration]({{ '/configuration/' | relative_url }}): see where local settings live.
- [Reference]({{ '/reference/' | relative_url }}): keep common commands close by.
- [Troubleshooting]({{ '/troubleshooting/' | relative_url }}): fix the usual setup and runtime problems.
- [Development]({{ '/development/' | relative_url }}): run the local test loop for contributors.

## Fast path

```sh
uv tool install amplifier-app-tui
amplifier-tui setup
amplifier-tui
```

The docs shell is intentionally static: no scripts, no external fonts, and no local documentation build dependency.
