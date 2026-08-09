---
layout: default
title: Quickstart
permalink: /quickstart/
---

Your first session, end to end. If the command is not installed yet, start with [Setup]({{ '/setup/' | relative_url }}).

## 1. Start in the project you want to work on

```sh
cd ~/code/my-project
amplifier-tui
```

Sessions are stored per project directory, so the directory you launch from is the directory your session belongs to.

No provider configured yet? Take the offline tour instead — same interface, scripted answers, no credentials:

```sh
amplifier-tui --demo
```

## 2. Read the screen

Two things matter on the first screen:

- **The transcript** fills most of the window. Your prompts, the model's answers, tool activity, and any pending approval all land here in order.
- **The composer** sits at the bottom. It is where you type, and its placeholder is also its cheat sheet:

```text
Message Amplifier…  ( ↑ history · ctrl+j newline · enter send · / commands )
```

Under the composer, a footer hint line changes with what the app is doing. While a turn is running it reads:

```text
esc interrupt · enter steer · shift+enter queue
```

Press <kbd>F1</kbd> for the full key overlay. It is read-only chrome — typing still reaches the composer while it is open, and <kbd>Esc</kbd> or <kbd>F1</kbd> closes it.

## 3. Send your first prompt

Type a task and press <kbd>Enter</kbd>. Keep the first one narrow enough that you can check the result yourself:

```text
Read this repository and summarize what the entry point does. Do not change any files.
```

| Key | While idle |
|---|---|
| <kbd>Enter</kbd> | Send the prompt. |
| <kbd>Ctrl</kbd>+<kbd>J</kbd> | Insert a newline instead of sending. |
| <kbd>↑</kbd> / <kbd>↓</kbd> | Walk back and forward through prompt history. |
| <kbd>Ctrl</kbd>+<kbd>S</kbd> | Stash the draft you are typing for later. |

## 4. Steer while the turn is running

You do not have to wait for a turn to finish before correcting it.

| Key | While running |
|---|---|
| <kbd>Enter</kbd> | Steer — send a mid-turn correction into the run in progress. |
| <kbd>Shift</kbd>+<kbd>Enter</kbd> | Queue a message to be delivered after the current turn. |
| <kbd>Alt</kbd>+<kbd>↑</kbd> | Recall a queued message back into the composer. |
| <kbd>Ctrl</kbd>+<kbd>G</kbd> | Show or hide the live thinking box. |
| <kbd>Ctrl</kbd>+<kbd>T</kbd> | Open the subagent lanes panel. |

If your terminal cannot deliver <kbd>Shift</kbd>+<kbd>Enter</kbd>, the app detects that and advertises <kbd>Alt</kbd>+<kbd>Enter</kbd> in the footer instead.

## 5. Open the command palette

Type `/` in the composer. The palette opens as you type, and `/` stays ordinary composer text, so keep typing to filter by command name. Its footer reads `↑↓ select · enter run · esc close`. Group headers — During, Parallel, Ship, Between, Repair — appear when the filter is exactly `/`.

A few worth knowing on day one:

| Command | What it does |
|---|---|
| `/status` | Session status: model, mode, messages, cost. |
| `/context` | Context usage grid plus suggestions. |
| `/model` | List models; `/model [provider] <name>` switches the live model. |
| `/tools` | List the mounted tools. |
| `/keys` | List every keyboard shortcut and what it does. |
| `/export` | Write the transcript to markdown under `exports/`. |
| `/rename` | Name this session so it is recognizable in the resume picker. |
| `/quit` | Exit the app. |

Running a command always echoes it into the transcript first, so the record of what you did stays complete.

## 6. Interrupt with Esc

<kbd>Esc</kbd> means "back out of the innermost thing." An open overlay always closes first, in a fixed order — key overlay, focused lane, palette, rewind, sessions, themes, timeline, lanes — and only when none of those are open does <kbd>Esc</kbd> interrupt the running turn.

Press <kbd>Esc</kbd> a second time within three quarters of a second after an interrupt and the rewind picker opens, so you can back out of the change as well as the turn. <kbd>Ctrl</kbd>+<kbd>R</kbd> opens the same picker deliberately.

## 7. Find the session again

Every session is written under your app home, keyed by project:

```text
~/.amplifier/projects/<project-slug>/sessions/<session-id>/
├── transcript.jsonl   # the conversation
├── metadata.json      # name, bundle, counts
└── ui-events.jsonl    # append-only UI event ledger
```

List what is stored for the current project, newest first:

```sh
amplifier-tui sessions
```

Then pick one up again:

```sh
amplifier-tui resume            # numbered picker of recent sessions
amplifier-tui resume 3f9c       # by id, or an unambiguous prefix
amplifier-tui continue          # straight into the newest session
```

`resume` uses deterministic exit codes so scripts can tell failures apart: `2` when nothing matches, `3` when a prefix is ambiguous, `4` when the match is unreadable.

## Next

- [Using the TUI]({{ '/using-the-tui/' | relative_url }}) — modes, approvals, subagent lanes, and rewind in depth.
- [Configuration]({{ '/configuration/' | relative_url }}) — providers, priority, routing, and where settings live.
- [User guide](https://github.com/michaeljabbour/amplifier-app-tui/blob/main/docs/USER-GUIDE.md) — the exhaustive keybinding and command reference in the repository.
