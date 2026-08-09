# Install Amplifier TUI

Amplifier TUI currently ships from its Git repository. There is no PyPI package,
native binary release, package-manager channel, or background app updater yet. The
existing `v0.1.0` tag predates the current feedback fixes, so the recommended path
today is explicitly a **latest-source install**, not a claim of a stable binary
release.

## System requirements

- 64-bit macOS or Linux on x86_64/amd64 or arm64/aarch64. WSL uses the Linux path.
- Bash, Git, curl, and an internet connection to GitHub and Astral.
- Python 3.12+. You do not need to install it first: `uv` prepares a compatible,
  isolated interpreter for the tool.
- Native Windows and 32-bit systems are not supported by this source installer.

The project has recorded clean-install evidence on macOS. A Linux source-install CI job is
prepared in the current working tree, but it is not published or remotely proven until the
installer changes merge and that job passes. A retained clean-machine release smoke and a
real WSL smoke are still required before those environments are called release-proven. No
minimum OS release or hardware floor has been established, so this guide does not invent one.

## One-line install

On macOS, Linux, or WSL, run:

```sh
curl -fsSL https://raw.githubusercontent.com/michaeljabbour/amplifier-app-tui/main/scripts/install.sh | bash
```

That is the public fast path. It keeps copy/paste setup short while the app's
own `amplifier-tui update` and `amplifier-tui reset` commands keep using the
hardened argv form internally for repair and update execution.

The installer:

1. requires Git and uses the official Astral installer when `uv` is absent;
2. resolves repository `main` once to a full 40-character commit SHA;
3. checks out that commit, requires its committed `uv.lock`, and exports the exact
   runtime dependency versions from that lock;
4. asks `uv` to install that exact application source under the locked constraints,
   never a floating branch or a fresh dependency re-resolution;
5. verifies the installed `amplifier-tui` executable and makes its directory
   discoverable on `PATH`; and
6. prints the exact executable path to run. First launch detects existing
   Amplifier/provider configuration or guides provider setup. It does not require a separate `init` command.

The bootstrap URL above follows `main`, so it is intentionally the **source channel**.
The app source and runtime package versions are pinned after resolution, but the downloaded
bootstrap script is not a signed release artifact. The lock includes hashes for published
artifacts and immutable Git SHAs for source dependencies; the actual Python interpreter and
platform-specific wheel can still differ across supported machines. For a source-reviewed install,
first inspect or download `scripts/install.sh` from a specific repository commit,
then run that local copy with the same commit:

```sh
sh ./scripts/install.sh --ref 0123456789abcdef0123456789abcdef01234567
```

Replace the example SHA with the exact reviewed commit. Supplying a branch or tag is
also supported; the installer resolves it to a commit before installation. Every install
uses the selected commit's own `uv.lock`, so updating dependencies is a deliberate repository
change: update the lock, test it, and install a new application commit.

## Review-first / advanced install

If you need the curl-piped form to fail closed when the download is missing,
blocked, or interrupted, use the hardened wrapper:

```sh
bash -o pipefail -c "curl --proto '=https' --tlsv1.2 -fsSL https://raw.githubusercontent.com/michaeljabbour/amplifier-app-tui/main/scripts/install.sh | bash -s --"
```

The extra flags require HTTPS/TLS 1.2 at curl and make Bash return the curl
failure instead of treating an empty shell as a successful install. This is the
same execution contract the app uses for programmatic update/reset reinstall
flows.

## What changes on the machine

- `uv` is installed through `https://astral.sh/uv/install.sh` only when it is not
  already available.
- The app receives its own `uv tool` environment; it does not overwrite the Python
  environment of the current project. Runtime package versions come from the selected
  source commit's `uv.lock`.
- If the tool executable directory is missing from `PATH`, the installer asks
  `uv tool update-shell` to add it. Use `--no-update-shell` to suppress that edit.
- Amplifier credentials and settings continue to live under `~/.amplifier/`; the
  installer does not create or read an API key.

The script never uses `sudo` and never force-overwrites another package's executable.
It is designed for native macOS and Linux shells, including WSL; the one-line wrapper
requires Bash. The real clean-install smoke in this audit ran on macOS. Linux and WSL
still need a recorded release matrix before those platforms are called proven. Native
Windows requires a separate installer and is not currently supported.

## Updating

There is no background app update. Run `amplifier-tui update` to resolve and
install the then-current `main` commit via the same source-installer contract, including that commit's locked dependencies. To stay
on an audited build, keep using its full commit SHA:

```sh
sh ./scripts/install.sh --ref 0123456789abcdef0123456789abcdef01234567
```

`amplifier-tui update` updates the application package. Advanced users can run
`amplifier-tui bundle refresh` to refresh mounted Amplifier bundle/module caches.

If startup reports `Remote branch <40-character SHA> not found`, the commit may
still be valid: older Amplifier Foundation builds incorrectly passed full commit
hashes to `git clone --branch`. Reinstall the application from a release/source
revision containing the commit-SHA activation fix. Clearing caches or running
`amplifier-tui bundle refresh` does not upgrade that application dependency.

## Verify, demo, and uninstall

```sh
amplifier-tui version       # installed package and Amplifier dependency versions
amplifier-tui doctor        # read-only diagnostics, including real-launch preflight
amplifier-tui --demo        # offline tour, no provider credentials
uv tool uninstall amplifier-app-tui
```

If the command is not found in a newly installed shell, restart that shell or run
`uv tool update-shell` and use the exact executable path printed by the installer.

The uninstall command removes only the app and its isolated tool environment. It
intentionally preserves `uv`, the shell PATH line managed by `uv`, and shared Amplifier
state under `~/.amplifier/` — provider keys, settings, caches, and session history may also
be used by the full `amplifier` CLI. Removing that directory is a separate destructive
data decision, not part of app uninstall.

If `amplifier-tui` still resolves after uninstall, check for a second installation or a
shell alias before deleting anything:

```sh
type -a amplifier-tui
uv tool list
```
