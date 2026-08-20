"""Check or bump the app-owned optional routing/provider source pins.

The routing overlay and provider setup catalog are optional at runtime, but
the app writes or composes their URIs when a user selects them.  They are
therefore pinned to full commits just like default-bundle dependencies.

Usage:
    uv run python scripts/bump_optional_source_refs.py
    uv run python scripts/bump_optional_source_refs.py --write

The default is read-only: compare every pin with its upstream ``main`` tip.
``--write`` resolves every tip first, rewrites both source files only after
all lookups succeed, and never commits.  Review the diff and run the printed
focused gate before publishing the app release that carries the bump.
"""

from __future__ import annotations

import argparse
import inspect
import subprocess
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from amplifier_app_tui.kernel import config as _config_module  # noqa: E402
from amplifier_app_tui.kernel import setup as _setup_module  # noqa: E402

ROUTING_MATRIX_BUNDLE_URI = _config_module.ROUTING_MATRIX_BUNDLE_URI
PROVIDER_SOURCES = _setup_module.PROVIDER_SOURCES


def _declaring_file(module: ModuleType) -> Path:
    """The file a pin was actually READ from -- never a path we assumed.

    ``amplifier_app_tui.kernel`` is a ``__path__`` shim: it rewrites its search
    path to the installed ``amplifier-runtime`` distribution, so these imports
    resolve to site-packages, NOT to the identically-named files in this repo.
    This script previously read the value through the shim and wrote the repo
    copy, which meant ``--write`` rewrote a file nothing reads: the next
    ``--check`` re-read the runtime, saw the old pin, and reported drift again.
    Forever -- and ``upstream-drift.yml`` opens a tracking issue on that check
    which its own printed remediation could never close.
    """
    return Path(inspect.getfile(module)).resolve()


APP_SOURCE_ROOT = REPO_ROOT / "src"


def _assert_app_owned(pins: tuple[SourcePin, ...]) -> None:
    """Refuse to rewrite a pin this repo no longer declares.

    Note the test is ``REPO_ROOT / "src"``, not ``REPO_ROOT``: the virtualenv
    lives *inside* the checkout, so a site-packages path is happily
    ``relative_to`` the repo root and that check would pass for exactly the
    files it needs to reject.
    """
    foreign = [pin for pin in pins if not pin.source_file.is_relative_to(APP_SOURCE_ROOT)]
    if not foreign:
        return
    names = ", ".join(sorted({pin.name for pin in foreign}))
    where = foreign[0].source_file
    raise RuntimeError(
        f"these pins are no longer declared by this repo: {names}\n"
        f"  they now live in the amplifier-runtime distribution ({where}),\n"
        f"  which is installed at a fixed commit -- writing there would be\n"
        f"  discarded by the next `uv sync`, and writing the identically-named\n"
        f"  file under src/ would rewrite a module the __path__ shim never loads.\n"
        f"  Bump them in amplifier-runtime, then bump this repo's runtime pin."
    )


@dataclass(frozen=True, slots=True)
class SourcePin:
    name: str
    uri: str
    source_file: Path


def current_pins() -> tuple[SourcePin, ...]:
    """The app-owned optional sources and the files that declare them."""
    pins = [
        SourcePin(
            "routing-matrix",
            ROUTING_MATRIX_BUNDLE_URI,
            _declaring_file(_config_module),
        )
    ]
    setup_path = _declaring_file(_setup_module)
    pins.extend(SourcePin(name, uri, setup_path) for name, uri in PROVIDER_SOURCES.items())
    return tuple(pins)


def source_url_and_ref(uri: str) -> tuple[str, str]:
    """Return the clone URL and full commit from one pinned git URI."""
    value = uri.removeprefix("git+")
    base, separator, tail = value.rpartition("@")
    ref = tail.partition("#")[0]
    if not separator or len(ref) != 40 or any(char not in "0123456789abcdef" for char in ref):
        raise ValueError(f"source is not pinned to a full lowercase SHA: {uri}")
    return base, ref


def remote_main(url: str, *, timeout: float = 15.0) -> str:
    """Resolve *url*'s main tip, failing closed on network/shape errors."""
    result = subprocess.run(
        ["git", "ls-remote", url, "refs/heads/main"],
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    fields = result.stdout.split()
    if result.returncode != 0 or len(fields) < 2 or fields[1] != "refs/heads/main":
        detail = result.stderr.strip() or "main ref not returned"
        raise RuntimeError(f"could not resolve {url}: {detail}")
    sha = fields[0]
    if len(sha) != 40 or any(char not in "0123456789abcdef" for char in sha):
        raise RuntimeError(f"unexpected main SHA for {url}: {sha!r}")
    return sha


def rewritten_files(pins: tuple[SourcePin, ...], resolved: dict[str, str]) -> dict[Path, str]:
    """Return validated rewritten file contents without touching disk."""
    by_file: dict[Path, list[SourcePin]] = defaultdict(list)
    for pin in pins:
        by_file[pin.source_file].append(pin)

    rewritten: dict[Path, str] = {}
    for path, file_pins in by_file.items():
        text = path.read_text(encoding="utf-8")
        for pin in file_pins:
            _url, current = source_url_and_ref(pin.uri)
            target = resolved[pin.name]
            if current == target:
                continue
            if text.count(current) != 1:
                display_path = (
                    path.relative_to(REPO_ROOT) if path.is_relative_to(REPO_ROOT) else path
                )
                raise RuntimeError(
                    f"expected exactly one {pin.name} pin {current} in {display_path}"
                )
            text = text.replace(current, target, 1)
        rewritten[path] = text
    return rewritten


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--write", action="store_true", help="rewrite stale pins after checking all"
    )
    args = parser.parse_args(argv)

    pins = current_pins()
    resolved: dict[str, str] = {}
    stale: list[str] = []
    try:
        for pin in pins:
            url, current = source_url_and_ref(pin.uri)
            remote = remote_main(url)
            resolved[pin.name] = remote
            marker = "current" if current == remote else "behind"
            print(f"{pin.name:36} {current[:8]} -> {remote[:8]}  {marker}")
            if current != remote:
                stale.append(pin.name)
    except (OSError, RuntimeError, subprocess.SubprocessError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1

    if not stale:
        print("all optional source pins are current")
        return 0
    if not args.write:
        print(f"{len(stale)} stale pin(s); re-run with --write after reviewing upstream")
        return 2

    try:
        _assert_app_owned(pins)
        updates = rewritten_files(pins, resolved)
        for path, text in updates.items():
            path.write_text(text, encoding="utf-8")
    except (OSError, RuntimeError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1

    print(f"updated {len(stale)} pin(s) across {len(updates)} files")
    print("run `uv run pytest -q tests/test_no_floating_dependencies.py` and review the diff")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
