---
layout: default
title: Using the TUI
permalink: /using-the-tui/
---

Everything in {{ site.data.product.display_name }} happens on one screen: you type into a composer at the bottom, the work lands in a transcript above it, and a status footer tells you which posture you are in and what it is costing. This page covers the day-to-day loop — sending, steering, approving, rewinding, and finding things again. For every edge case, see the [complete user guide]({{ '/reference/user-guide/' | relative_url }}).

## The screen

Four regions are always present, plus overlay strips that appear on demand.

| Region | Where | What it shows |
|---|---|---|
| Title bar | Top | Session identity and what the app is doing right now |
| Transcript | Middle | Durable history, plus the live streaming tail of the current answer |
| Composer | Bottom | Your draft, with the active mode badge on its left edge |
| Footer | Below the composer | Mode, trust, model, session, cost — and the keys available right now |

### Title bar

The title reads `amplifier — <state> — <bundle> — <session-short>`. The `<state>` fragment is the working indicator: `ready` when nothing is running, `planning` or `brainstorming` in those modes, the current plan step while one is in progress, or `coordinating N agents` while subagents are running. While a turn is running the title is prefixed with a spinner glyph, so a glance at the top row tells you whether the app is busy.

The `<bundle>` fragment is the bundle that actually resolved for this session, fitted to your terminal width — it shrinks or drops on a narrow terminal rather than wrapping.

### Transcript

The transcript is the durable record of the session: your prompts, tool lines, thinking blocks, subagent summaries, and final answers, separated by turn rules. Below it, a mutable streaming tail paints the answer as it arrives and then consolidates into one durable block when the stream ends.

Turn rules are clickable — clicking one opens the rewind picker at that checkpoint.

### Composer

The composer is an auto-growing input with a `[mode]` badge and a `❯` prompt. Its left edge is tinted in the active mode's color, so the posture you are in is visible without reading anything. When it is empty it shows:

```text
Message Amplifier…  ( ↑ history · ctrl+j newline · enter send · / commands )
```

### Footer

The left half of the footer is the persistent status line:

```text
mode <mode> · <trust> · <model> · <session-short> · $<cost>
```

It also carries a green `▲` yield glyph when the last turn shipped something, an orange `· q1` badge when a next-turn message is queued, and a clickable `N decisions waiting · ctrl-y` badge when approvals have been deferred.

The right half is context-sensitive: it advertises exactly the keys that work in whatever surface currently owns the keyboard — `esc interrupt · enter steer · shift+enter queue` while a turn runs, `arrows select · enter confirm · esc deny` under an approval, and so on for each panel ([the full keymap in the Reference]({{ '/reference/' | relative_url }}#full-keymap) lists them all). When the session is idle the right half is deliberately blank: the composer placeholder and `f1` carry those reminders instead, so the footer only ever shows something you can act on right now.

### Overlay strips

Panels — the palette, agent lanes, rewind, sessions, themes, timeline, and the `f1` key overlay — dock as bordered strips **above the composer**. None of them is a modal dialog, and typing keeps reaching your draft while most of them are open.

## Sending and steering

Press `enter` to submit. `ctrl+j` (or `ctrl+enter`) inserts a newline instead of sending, and `↑` / `↓` walk your prompt history.

Once a turn is running, the same `enter` key means something different: it **steers** the turn already in flight instead of starting a new one.

| Key | Idle | While a turn is running |
|---|---|---|
| `enter` | Submit the prompt | Steer the running turn |
| `ctrl+j`, `ctrl+enter` | Newline | Newline |
| `shift+enter` | Queue a message | Queue a message for the next turn |
| `alt+enter` | Queue fallback on terminals where `shift+enter` cannot arrive | Same |
| `alt+↑` | Recall the queued message into the composer | Recall the queued message into the composer |
| `↑` / `↓` | Prompt history | Prompt history |
| `ctrl+s` | Stash the draft | Stash the draft |
| `esc` | (resolved by the Esc chain) | Interrupt the turn |

### Queued steering

There is exactly one steering path, and it is a bounded queue. A steer is consumed **one per step boundary** of the running turn — the app hands it to the model at the next request it makes, not mid-token. That is why steering feels like a course correction rather than an interruption.

Two consequences worth knowing:

- **Leftover steers are discarded at turn end.** If the turn finishes before your steer reaches a step boundary, it is dropped rather than silently promoted into a turn you never chose to send.
- **`shift+enter` queues a whole next-turn message instead.** That one is not a steer: it runs as its own turn when the current one ends. The footer shows `· q1` and a strip appears above the composer reading `▹ queued next: "<text>" · runs when this turn ends · alt+↑ recall to steer`. Press `alt+↑` (or click the strip) to pull the exact text back into an empty composer, where `enter` can steer with it instead.

Recover a stashed draft with `/stashes` and `/unstash`.

## Modes and trust

A mode is a posture: it decides which capabilities run silently and which ones stop to ask you. `shift+tab` cycles modes; `/mode <name>` jumps directly to one; `/modes` lists the modes the active bundle provides.

| Mode | Trust posture |
|---|---|
| `chat` | `ask all · auto read` |
| `plan` | `read-only` |
| `brainstorm` | `no tools` |
| `build` | `auto read,test · ask write,net,spend` |
| `auto` | `auto everything · platform governs` |

The trust string in the footer is the live rule, not a label — it is what the app will actually do with the next tool call. `plan` and `brainstorm` are the two safe postures: `plan` reads but changes nothing and hands its plan to build; `brainstorm` runs no tools at all. `auto`'s exact posture depends on how governance is configured for your install; the footer always shows the one in force.

`auto` means **automatic tool approval**, not an endless agent loop. A normal message still runs one orchestrator turn and then gives control back to you. For autonomous follow-through, use `/goal [turn-cap] <success condition>`; Amplifier will continue taking turns until the condition passes or the cap is reached. `/goal stop` clears it. If a turn reaches its model or iteration limit first, the transcript marks it **incomplete** instead of presenting its progress summary as a final answer.

`ctrl+p` reports the effective trust posture without changing it. To actually edit trust — boundary, blocks, and exceptions — use `/permissions`, and `/allowed-dirs` / `/denied-dirs` for the write directories this session may touch. Trust cannot be changed while an approval is pending: the mode, permission, and effort cycles are all disabled under an open approval bar.

## Approvals

When the active mode says *ask* for a capability a tool wants to use, the turn pauses and an approval bar **replaces the composer**:

```text
Approval required · <what it wants to do>   › Allow once   Allow always   Deny
```

The selected option is prefixed with `› `; `Deny` is red while unselected. The bar owns the keyboard while it is open.

| Key | Action |
|---|---|
| `←` / `↑` | Previous option |
| `→` / `↓` / `tab` / `shift+tab` | Next option |
| `enter` | Confirm the selected option |
| `esc` | Deny |
| `ctrl+y` | Defer — park the decision without answering it |

Clicking an option confirms it directly.

Deferring is the escape hatch when you do not want to decide right now. A deferred decision does not halt the turn; it lands in the needs-you queue, the footer shows an orange `N decisions waiting · ctrl-y` badge, and pressing `ctrl+y` prints the list into the transcript where you can answer it later. Answering a parked decision injects the answer as a next-turn instruction.

## Subagent lanes

When a turn delegates to subagents, the transcript keeps a readable summary per delegation — but the live per-agent detail lives in the lanes panel. Press `ctrl+t` (or run `/tasks`) to open it:

```text
Agent lanes · ↑↓ select · enter focus · ctrl-o tail · esc close
  ◐ <name> · <activity> · <elapsed> · ↓ Nk tokens · $<cost>
```

One aligned line per subagent, with a state glyph: `◐` running, `■` working, `✔` done.

- `↑` / `↓` move the selection, `enter` focuses the highlighted lane.
- **Focusing a lane swaps the transcript to that subagent's own history.** The banner reads `focused: <name> · subagent of <parent> · own context window · results report back to parent · esc back`, and `esc` returns you to the parent transcript.
- `ctrl+o` cycles the live tail: it pins the streaming tail to the next running lane so you can watch one agent's output as it arrives, instead of the root session's. The pinned lane is marked with a `▸` and the tail switches immediately.
- `esc` closes the panel.

## Rewind and checkpoints

Every prompt cuts a checkpoint. `ctrl+r` (or `/rewind`, or clicking a turn rule) opens the restore picker above the composer:

```text
‹ checkpoint · before turn N · <prompt> ›  [code + conversation]  [enter restore]
```

| Key | Action |
|---|---|
| `←` / `→` | Move between checkpoints (clamped at the ends, no wrap) |
| `↑` / `↓` | Choose the restore scope |
| `enter` | Restore |
| `esc` | Close without restoring |

Three scopes are available: **code + conversation**, **conversation only**, and **code only**. A checkpoint restores the state from *before* that prompt — the conversation is trimmed back to the boundary immediately before it, and the code scope restores the file workspace snapshot taken at that point. Each checkpoint carries the original prompt text and the cumulative session spend at the moment it was cut, so the picker tells you both what you are going back to and what you are giving up.

**The double-Esc backtrack.** While a turn is running, `esc` interrupts it. A second `esc` within 0.75 seconds opens the rewind picker straight away — stop, then go back, without reaching for another chord. Only an `esc` that actually targeted a running turn arms the gesture, so closing a panel can never accidentally open rewind.

When checkpoints exist, the otherwise-empty idle footer surfaces `ctrl-r rewind` as a reminder.

## Timeline

While the session is **idle**, `ctrl+g` opens a live-scrubbing timeline strip — a film strip of turns for navigation only:

```text
‹ timeline · turn 2/5 · "add fuzzy recall" ›  [enter keep]  [esc back]
```

`↑`/`←` and `↓`/`→` move the cursor and scrub the transcript live as you go. `enter` keeps the landed scroll position; `esc` returns the transcript to the tail, so a pure look-around moves nothing. Typing while the strip is open still lands in the composer.

The same `ctrl+g` chord means something else **while a turn is running**: there it toggles the thinking box. One chord, two states, never ambiguous — a running turn has a live box worth peeking at; an idle session does not.

## Sessions

Sessions are saved automatically, per project. Everything for one session lives in its own directory:

```text
~/.amplifier/projects/<project-slug>/sessions/<session-id>/
├── transcript.jsonl      # the conversation
├── metadata.json         # name, bundle, counts
├── ui-events.jsonl       # append-only UI event ledger
└── rewind-intent.json    # pending rewind transaction
```

List and reopen them from the shell:

```sh
{{ site.data.product.command }} sessions          # newest first, this project only
{{ site.data.product.command }} sessions --plain  # bare ids, one per line
{{ site.data.product.command }} resume            # numbered picker of recent sessions
{{ site.data.product.command }} resume SESSION_ID # resume a specific one (id or unique prefix)
{{ site.data.product.command }} continue          # resume the newest session, no picker
```

`resume` uses deterministic exit codes so scripts can tell the failures apart: `2` no match, `3` ambiguous prefix, `4` unreadable metadata. See the [Reference]({{ '/reference/' | relative_url }}) page.

From inside the app, `/sessions` opens the picker strip: `↑`/`↓` select, `enter` opens the highlighted session's detail, `r` resumes it through a clean handoff, `esc` closes. `/sessions <query>` filters the list.

Related commands: `/rename` names the current session so it is recognizable in the picker, `/tag` attaches or removes tags, `/branch` snapshots the conversation into a new session, and `/fork` snapshots it into a new session primed to run a directive.

## The command palette

Type `/` in the composer. The `/` is ordinary text — the palette opens on the prefix and live-filters as you keep typing.

- **Filtering** is a substring match on the command name.
- **Group headers** (`During`, `Parallel`, `Ship`, `Between`, `Repair`, in that order) show only when the filter is exactly `/`. Type one more character and the headers collapse into a flat filtered list.
- `↑` / `↓` move the selection, `enter` runs the selected row, clicking runs any row.
- `esc` closes the palette without running anything.
- Running a command always echoes it into the transcript as a user line first, so the record shows what you did.

### Built-in commands

A few worth knowing on day one:

| Command | What it does |
|---|---|
| `/mode` | Cycle or jump posture: chat, plan, brainstorm, build, auto. |
| `/status` | Session status: model, mode, messages, cost. |
| `/context` | Context usage grid plus suggestions. |
| `/tasks` | Agent lanes: one line per subagent (same as `ctrl+t`). |
| `/rewind` | Restore code, conversation, or both before a prompt (same as `ctrl+r`). |
| `/sessions` | List stored sessions; `/sessions <query>` filters. |
| `/keys` | List every keyboard shortcut and what it does. |
| `/quit` | Exit the app (`ctrl-d` works too). |

That is a slice of the registry, not the whole of it. For every built-in command and the palette group it belongs to, see [the full list in the Reference]({{ '/reference/' | relative_url }}#built-in-commands).

### Skill commands

The palette is not limited to that table. Every discovered skill registers its own slash command — plus one per distinct shortcut alias — tagged `skill` in the palette. Which ones you see depends entirely on which bundles and skills are mounted, so there is no fixed list to memorize; run `/skills` to see what this session actually has. A built-in name always wins a collision with a skill; among skills, the first one registered wins — and every collision is reported rather than silently duplicated.

## Keybindings

Every key comes from one table inside the app, which also feeds the footer hints and the `f1` overlay — so what works and what the UI advertises cannot drift apart. The contextual tables above cover each surface as you meet it; for every binding in one place, see [the full keymap in the Reference]({{ '/reference/' | relative_url }}#full-keymap).

### The f1 which-key overlay

`f1` toggles a read-only cheat sheet rendered from that same table. It never takes focus from the composer, so typing keeps reaching your draft while it is open. `esc` or `f1` again dismisses it. `/keys` prints the same reference into the transcript.

### The Esc chain

`esc` is resolved by an ordered table, not by guesswork. The first context in this list that is currently active consumes the press:

1. `keys` → close the which-key overlay
2. `lane_focus` → return from a focused subagent to the parent transcript
3. `palette` → close the palette
4. `rewind` → close the rewind picker
5. `sessions` → close the sessions picker
6. `themes` → close the theme picker (reverting the preview)
7. `timeline` → close the timeline strip
8. `lanes` → close the lanes panel
9. `running` → interrupt the running turn

The read-only overlay leads the chain deliberately: dismissing help should never cost you a stateful action underneath it. The approval bar's `esc` (deny) and the evidence block's `esc` sit outside this chain — those surfaces own the keyboard exclusively while they are open.

## Copying text

`/copy` puts the last answer on your clipboard. It writes via OSC 52 — the terminal's own clipboard escape, which keeps working over SSH — and, where one exists, also through the OS clipboard tool, because some terminals ship with OSC 52 writes disabled.

When you want the whole conversation rather than one answer, `/export` writes the transcript as markdown into `exports/`. That export is human-readable but lossy; for a structured, re-importable artifact use `{{ site.data.product.command }} session export SESSION_ID` from the shell instead.

## Demo mode

`--demo` is a **flag on the app, not a subcommand**:

```sh
{{ site.data.product.command }} --demo
```

It runs a scripted session that is fully offline — no bundle, no network, no credentials. First-run setup and the provider preflight are both skipped entirely. It is the right way to explore the screen, the palette, lanes, rewind, and the keymap before you have configured a provider, or to reproduce a UI question without spending anything.

## Where to go next

- [Configuration]({{ '/configuration/' | relative_url }}) — providers, priority, bundles, routing, and where settings live.
- [Reference]({{ '/reference/' | relative_url }}) — the full CLI surface, file locations, and the headless JSONL contract.
- [Complete user guide]({{ '/reference/user-guide/' | relative_url }}) — every key, command, and edge case this page summarizes.
