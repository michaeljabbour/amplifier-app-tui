# Runtime consolidation conformance — 2026-10-28

**The TUI already uses the shared runtime.** `kernel/__init__.py` and `model/__init__.py` replace the compatibility packages' search paths with the installed runtime directories, excluding local fallback. Local kernel/model bodies are inert migration copies; differing files are not competing active implementations.

`tests/test_runtime_contract_retirement.py` adds five focused checks across the actual owner/client boundary. They preserve separate stream/durable events, tool-call IDs and cancellation; exercise invalid/stale approval denial in the real broker; replay the actual disposable session store without modifying it; and resolve all runtime-owned module paths and exercise event behavior after leaving only kernel/model compatibility shims in a disposable client copy. The last check runs against the locked runtime and, when explicitly available, a candidate source checkout. Other client files and product metadata stay intact.

The full locked-runtime offline baseline passed **4954 tests**, with **13 skipped** and **12 Forge cases deselected**. The new focused file passed **5 tests** separately. The required real-PTY Forge tier passed **9**, with **3 paid-provider cases skipped** under explicit real-lane-off configuration. Ruff check/format and source Pyright passed. A Python 3.13 transport-finalizer warning remained visible.

The published runtime pin is unchanged. The candidate source check does not install it globally or claim full downstream compatibility. The canonical runtime also passed its own full suite and exports a generated data-channel schema from its existing models. Ticket-bearing control messages, leases, approval enforcement and durable history boundaries remain runtime-owned.

No inert file was actually removed, no unrelated checkout or running user session was changed, and no repository was retired. The disposable import/event proof is a readiness check, not authorization to delete code or a substitute for a consumer/package migration audit.
