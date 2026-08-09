---
layout: default
title: Amplifier App TUI
description: Install the terminal workspace, try the offline demo, and choose the fastest path into the documentation.
permalink: /
hide_title: true
---

<div class="home-eyebrow"><span class="icon icon-command-line" aria-hidden="true"></span><span>{{ site.data.product.brand_name | downcase }}</span></div>

<h1 class="home-title">{{ site.data.product.brand_name }}</h1>

<p class="home-deck">A terminal workspace for work that thinks back.</p>

<div class="home-value-grid">
  <div class="home-value">
    <span class="icon icon-check-circle value-icon value-icon-green" aria-hidden="true"></span>
    <div><strong>Work with context</strong><p>Project-aware sessions resume where you left off, with durable history and the right local context.</p></div>
  </div>
  <div class="home-value">
    <span class="icon icon-arrow-trending-up value-icon value-icon-amber" aria-hidden="true"></span>
    <div><strong>Ship with confidence</strong><p>Steer live work, approve consequential actions, and keep every change traceable.</p></div>
  </div>
</div>

<section class="home-section install-section" aria-labelledby="install-heading" markdown="1">
  <h2 id="install-heading" data-toc-title="Install">Install in one command</h2>
  <p class="section-kicker">macOS, Linux, or WSL.</p>

  <pre class="install-command" data-copy-text="curl -fsSL https://raw.githubusercontent.com/{{ site.data.product.repository }}/main/scripts/install.sh | bash"><code aria-label="curl -fsSL https://raw.githubusercontent.com/{{ site.data.product.repository }}/main/scripts/install.sh pipe bash">curl -fsSL <span aria-hidden="true">…</span> | bash</code></pre>

  <p class="launch-line">Then launch it: <code>{{ site.data.product.command }}</code></p>
</section>

<section class="demo-panel" aria-labelledby="demo-heading">
  <div class="demo-intro"><h2 id="demo-heading">Try the demo</h2><p>See {{ site.data.product.brand_name }} plan and work in a real interface—offline and without credentials.</p><a href="{{ '/quickstart/#try-the-offline-demo-first' | relative_url }}">Open demo guide <span aria-hidden="true">→</span></a></div>
  <div class="demo-terminal" aria-label="Example terminal status"><span class="terminal-prompt">›</span><code>{{ site.data.product.command }} --demo</code><span class="terminal-summary">Session history is durable; the work stays reviewable.</span><strong>Plan 3/3</strong><span class="terminal-status"></span></div>
</section>

<section class="home-section paths-section" aria-labelledby="paths-heading">
  <h2 id="paths-heading">Start with a path</h2>
  <p class="section-kicker">Choose the route that matches what you want to do.</p>
  <div class="path-grid">
    <a class="path-link path-green" href="{{ '/setup/' | relative_url }}"><span class="icon icon-arrow-right" aria-hidden="true"></span><span><strong>Start here</strong><small>Install, launch, and take your first step.</small></span></a>
    <a class="path-link path-blue" href="{{ '/reference/' | relative_url }}"><span class="icon icon-book-open" aria-hidden="true"></span><span><strong>Reference</strong><small>Commands, flags, shortcuts, and configuration.</small></span></a>
    <a class="path-link path-cyan" href="{{ '/using-the-tui/' | relative_url }}"><span class="icon icon-command-line" aria-hidden="true"></span><span><strong>Work in the TUI</strong><small>Drive work, steer plans, and approve actions.</small></span></a>
    <a class="path-link path-teal" href="{{ '/engineering/' | relative_url }}"><span class="icon icon-cube" aria-hidden="true"></span><span><strong>Understand the system</strong><small>Architecture, data model, protocols, and decisions.</small></span></a>
    <a class="path-link path-indigo" href="{{ '/configuration/' | relative_url }}"><span class="icon icon-cog-6-tooth" aria-hidden="true"></span><span><strong>Configure</strong><small>Providers, models, routing, bundles, and permissions.</small></span></a>
    <a class="path-link path-violet" href="{{ '/development/' | relative_url }}"><span class="icon icon-user-group" aria-hidden="true"></span><span><strong>Contribute</strong><small>Build with us. Improve code, contracts, or docs.</small></span></a>
    <a class="path-link path-amber" href="{{ '/update-reset/' | relative_url }}"><span class="icon icon-arrow-path" aria-hidden="true"></span><span><strong>Maintain</strong><small>Update, reset, and troubleshoot safely.</small></span></a>
  </div>
</section>

<section class="home-section library-section" aria-labelledby="library-heading">
  <h2 id="library-heading">Everything, on this site</h2>
  <p>Deep dives for engineers and contributors: <a href="{{ '/development/architecture/' | relative_url }}">architecture</a>, <a href="{{ '/development/design-contract/' | relative_url }}">design contract</a>, and <a href="{{ '/development/guide/' | relative_url }}">development guide</a>.</p>
  <p>Search reads every section, not just page titles. <strong>Ask the docs</strong> turns those same local results into a cited answer; when the browser already provides an on-device language model, it can polish that answer without putting a hosted API key in this static site.</p>
</section>

<section class="home-section support-section" aria-labelledby="support-heading">
  <h2 id="support-heading" data-toc="false">Three commands cover the support story</h2>
  <p class="section-kicker">Launch, update, and repair. Everything else is optional depth.</p>
  <table>
    <thead><tr><th>Command</th><th>What it does</th></tr></thead>
    <tbody>
      <tr><td><code>{{ site.data.product.command }}</code></td><td>Launch the app or enter guided first-run configuration.</td></tr>
      <tr><td><code>{{ site.data.product.command }} update</code></td><td>Check and update the installed application itself.</td></tr>
      <tr><td><code>{{ site.data.product.command }} reset</code></td><td>Preview and repair regenerable state while preserving sessions, settings, and keys.</td></tr>
    </tbody>
  </table>
</section>

<details class="scope-details" markdown="1">
  <summary>Distribution boundaries</summary>
  <ul>
    <li>The current channel is a source install under a committed lockfile; it is not a PyPI, Homebrew, WinGet, or native-binary release.</li>
    <li>There is no background updater. The app changes only when you run an explicit command.</li>
    <li>macOS, Linux, and WSL are supported. Native Windows is not.</li>
  </ul>
</details>
