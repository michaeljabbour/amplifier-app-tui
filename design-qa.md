**Comparison target**

- Source visual truth: `/Users/michaeljabbour/.codex/generated_images/019fe67a-0008-70a2-93c8-52a5e60da49d/exec-1920b0f7-33d3-4161-9594-685c5c032cf0.png`
- Implementation: `http://127.0.0.1:4174/amplifier-app-tui/`
- Implementation screenshot: `/tmp/amplifier-docs-home-final.png`
- Responsive screenshot: `/tmp/amplifier-docs-home-mobile-cdp.png`
- Source pixels: 1487 x 1058. Implementation pixels: 1487 x 1058.
- CSS viewport: 1487 x 1058 at device pixel ratio 1. No density normalization was needed.
- Responsive viewport: 390 x 844 at device pixel ratio 1.
- State: documentation home, default light content canvas, fixed dark status bar and navigation, no overlay open.

**Findings**

- No actionable P0, P1, or P2 differences remain.
- Fonts and typography: the vendored Inter variable font matches the source's compact sans-serif hierarchy. Display, body, monospace, and small navigation text retain the intended weights, line heights, wrapping, and truncation.
- Spacing and layout rhythm: the 294 px sidebar, 806 px content track, 126 px gutter, 170 px table of contents, section dividers, card radii, and vertical rhythm align with the source at the matched viewport.
- Colors and visual tokens: the navy chrome, warm paper canvas, green ready state, amber progress state, blue links, borders, and restrained shadows map cleanly to the source and preserve readable contrast.
- Image quality and asset fidelity: UI icons are locally vendored official Heroicons rather than custom drawings. The two documentation screenshots are exact 1172 x 720 crops of the real Forge terminal view, render sharply at their displayed width, exclude all Forge application chrome, and use descriptive alt text.
- Copy and content: implementation copy keeps the source hierarchy but uses the real `amplifier-tui` command, actual offline-demo behavior, and accurate user paths. These are intentional product-truth substitutions, not design drift.
- Icons and states: icon size, stroke silhouette, optical alignment, selected navigation marker, copy-success state, and mobile menu state are visually consistent with the selected direction.
- Responsiveness and accessibility: the 390 px view has no horizontal overflow (`scrollWidth` equals `innerWidth`), content collapses to one column, the navigation becomes a labeled toggle, and all primary controls retain visible focus and semantic labels.

**Full-view comparison evidence**

- The source and final implementation were opened together in one comparison input at identical 1487 x 1058 dimensions.
- Major-region proportions, alignment, hierarchy, density, colors, typography, and above-the-fold content all preserve the selected direction.
- Focused crop comparison was not needed: at 1487 x 1058 the status bar, navigation, hero, install control, demo card, path grid, and table of contents were all readable at 1:1 scale in the combined input. Each of those regions was still inspected individually in the full-resolution images.

**Comparison history**

- Pass 1: `/tmp/amplifier-direction3-implementation-v2.png` exposed P2 horizontal proportion drift in the content/TOC tracks and P2 vertical drift below the hero. The navigation also showed more links than the source.
- Fixes: constrained the desktop grid to 806 px content + 126 px gutter + 170 px TOC, matched the visible task-first navigation, retained secondary routes in search, aligned the install/demo/path sections, and removed the extra home-deck margin with a direct-child rule.
- Pass 2: `/tmp/amplifier-docs-home-final.png` was compared with the source at the same viewport. The earlier track, navigation, and vertical-rhythm differences were resolved. No new P0/P1/P2 issue was visible.
- Pass 3: user review identified the surrounding Forge header/sidebar/status as a P2 distraction in both documentation captures. Both source images were cropped to the terminal viewport only, without re-rendering or altering terminal text. Post-fix evidence: `/tmp/amplifier-docs-config-crop-qa.png` and `/tmp/amplifier-docs-quickstart-crop-qa.png`; both rendered pages show only the real terminal session and no Forge application interface.
- Pass 4: full-text search was expanded from title-only substring matching to a 566-chunk, 28-route source-synchronized index with ranked section results, contextual excerpts, query-term highlighting, and complete keyboard selection. The new Ask Amplifier dialog reuses that index for grounded local answers, always shows source links, and only invokes a browser-provided on-device language model when it is already available. Microsoft Edge QA at 1440 x 1000 verified one same-origin index request, correct `priority 100` ranking, a direct `keys.env` credential-location answer, dialog layout, and zero runtime exceptions.

**Primary interactions tested**

- `Command-K` focuses documentation search; searching `priority 100` ranks the exact provider-priority section first, with contextual snippets and Arrow-key selection.
- `Ask the docs` opens a keyboard-accessible dialog; asking where provider credentials are stored returns the `~/.amplifier/keys.env` path and cited Configuration, Reference, and Troubleshooting links. Microsoft Edge reported no on-device `LanguageModel`, so the universal local-answer fallback was also verified.
- The install copy control enters its `Copied` success state and writes the complete canonical install command, not the visually abbreviated version.
- The table-of-contents link updates the page to `#install-heading`.
- At 390 x 844, the navigation toggle opens and closes the sidebar and keeps `aria-expanded` synchronized.
- Browser console errors checked: 0.

**Terminal UX and runtime-integrity QA**

- Forge daemon health passed, followed by the real-PTY capability tier: 9 passed and 3 credential-gated cases skipped cleanly.
- Real PTY walkthroughs covered grouped root help, `config` dashboard and maintenance preview, provider-first `init`, default-No `reset`, provider/routing/bundle/notification/directory read surfaces, `update --check-only`, `bundle refresh --check-only`, and both healthy/no-provider `doctor` outcomes. Every mutating walkthrough used an isolated temporary Amplifier home.
- The no-provider doctor path reports one concise finding and `amplifier-tui config` remediation. It emits no hidden Anthropic validation traceback or unrelated degraded-start warning.
- Optional bundle providers are now mounted only when their credential exists. Provider settings merge by identity across scopes, so CLI inspection and runtime composition no longer disagree.
- Implementation delegates receive one automatic execute-only retry when they return prose without a successful mutation. Read-only shell calls and denied writes do not count; a successful file tool or observed Git diff does. A second zero-mutation result is marked incomplete, never successful.
- Max-iteration/token endings remain incomplete even when the upstream loop emits a non-empty progress summary. The transcript omits the Final answer promotion, uses an orange incomplete state, and asks for continuation instead of reporting agents done.
- Two sessions may initialize in the same workspace while one owns the write-checkpoint lease, and plan/brainstorm turns do not acquire that mutation lease. Competing write-capable turns still serialize with an actionable retry/worktree explanation.
- Full release gate: `ruff check`, format check, and `pyright src/` passed; 4,625 offline tests passed with 12 intentional Forge/credential skips. The staged 28-route Jekyll build and internal-link/anchor checker passed; the 566-chunk search index and JavaScript syntax checks passed.

**Open Questions**

- None.

**Implementation Checklist**

- [x] Match the selected desktop visual direction.
- [x] Preserve comprehensive source-synchronized documentation routes.
- [x] Use real local fonts and icon assets.
- [x] Verify desktop and mobile rendering in Microsoft Edge.
- [x] Verify search, copy, table-of-contents, and mobile navigation behavior.
- [x] Check browser console errors and internal links.

**Follow-up Polish**

- No blocking or necessary P3 follow-up remains.

final result: passed
