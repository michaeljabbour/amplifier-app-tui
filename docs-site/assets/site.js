(function () {
  "use strict";

  const body = document.body;
  const baseurl = body.dataset.baseurl || "";
  const navToggle = document.querySelector(".mobile-nav-toggle");
  const navBackdrop = document.querySelector(".sidebar-backdrop");
  const searchInput = document.querySelector("#docs-search-input");
  const searchResults = document.querySelector("#docs-search-results");
  const article = document.querySelector(".site-content");
  const toc = document.querySelector(".page-toc");
  const tocLinks = document.querySelector("#page-toc-links");
  const askLaunch = document.querySelector("#ask-docs-launch");
  const askDialog = document.querySelector("#ask-docs-dialog");
  const askClose = document.querySelector("#ask-docs-close");
  const askForm = document.querySelector("#ask-docs-form");
  const askInput = document.querySelector("#ask-docs-input");
  const askMessages = document.querySelector("#ask-docs-messages");
  let activeSearchIndex = -1;

  function setNav(open) {
    body.classList.toggle("nav-open", open);
    if (navToggle) navToggle.setAttribute("aria-expanded", String(open));
  }

  navToggle?.addEventListener("click", () => setNav(!body.classList.contains("nav-open")));
  navBackdrop?.addEventListener("click", () => setNav(false));
  document.querySelectorAll(".site-sidebar a").forEach((link) => {
    link.addEventListener("click", () => setNav(false));
  });

  function normalize(value) {
    return String(value || "")
      .normalize("NFKD")
      .replace(/[\u0300-\u036f]/g, "")
      .toLowerCase()
      .replace(/[^a-z0-9_./:-]+/g, " ")
      .replace(/\s+/g, " ")
      .trim();
  }

  const fallbackEntries = [];
  const fallbackSeen = new Set();
  document.querySelectorAll("[data-search-entry]").forEach((link) => {
    const title = link.dataset.searchTitle || link.textContent.trim();
    const description = link.dataset.searchDescription || "";
    const href = link.href;
    const key = `${title}|${href}`;
    if (fallbackSeen.has(key)) return;
    fallbackSeen.add(key);
    fallbackEntries.push({ title, section: "Overview", description, text: description, href });
  });
  let entries = fallbackEntries;
  let searchIndexPromise;

  function loadSearchIndex() {
    if (searchIndexPromise) return searchIndexPromise;
    const path = `${baseurl}/search-index.json`.replace(/\/{2,}/g, "/");
    searchIndexPromise = window
      .fetch(path, { credentials: "same-origin" })
      .then((response) => {
        if (!response.ok) throw new Error(`Search index returned ${response.status}`);
        return response.json();
      })
      .then((index) => {
        if (Array.isArray(index) && index.length) entries = index;
        return entries;
      })
      .catch(() => entries);
    return searchIndexPromise;
  }

  function entryHref(entry) {
    if (entry.href) return entry.href;
    const route = entry.route || "/";
    const fragment = entry.anchor ? `#${entry.anchor}` : "";
    return `${baseurl}${route}${fragment}`;
  }

  function rankEntries(rawQuery, limit = 10) {
    const query = normalize(rawQuery);
    if (!query) return [];
    const stopWords = new Set(["a", "an", "and", "are", "do", "does", "for", "how", "i", "in", "is", "of", "the", "to", "what"]);
    const tokens = [...new Set(query.split(" ").filter((token) => token.length > 1 && !stopWords.has(token)))];
    if (!tokens.length) return [];
    const relatedTerms = {
      credential: ["secret", "key", "keys.env", "api"],
      credentials: ["credential", "secret", "secrets", "key", "keys", "keys.env", "api"],
      save: ["store", "stored", "file", "path", "location", "directory"],
      saved: ["store", "stored", "file", "path", "location", "directory"],
      store: ["save", "saved", "stored", "file", "path", "location", "directory"],
      stored: ["store", "save", "saved", "file", "path", "location", "directory"],
      where: ["file", "path", "location", "directory", "home"],
    };
    const tokenGroups = tokens.map((token) => [token, ...(relatedTerms[token] || [])]);
    const locationIntent = tokens.some((token) => ["save", "saved", "store", "stored", "where"].includes(token));
    const credentialIntent = tokens.some((token) => ["credential", "credentials", "key", "keys", "secret", "secrets"].includes(token));
    const ranked = [];

    entries.forEach((entry) => {
      const title = normalize(entry.title);
      const section = normalize(entry.section);
      const description = normalize(entry.description);
      const text = normalize(entry.text);
      const all = `${title} ${section} ${description} ${text}`;
      const matchedGroups = tokenGroups.filter((group) => group.some((term) => all.includes(term)));
      if (matchedGroups.length < Math.max(1, Math.ceil(tokenGroups.length * 0.6))) return;
      const matched = tokens.filter((token) => all.includes(token));

      let score = matchedGroups.length * 4 + matched.length * 4;
      if (title === query) score += 100;
      if (title.includes(query)) score += 60;
      if (section.includes(query)) score += 44;
      if (description.includes(query)) score += 28;
      if (text.includes(query)) score += 18;
      matched.forEach((token) => {
        if (title.includes(token)) score += 18;
        if (section.includes(token)) score += 13;
        if (description.includes(token)) score += 8;
        if (text.includes(token)) score += 3;
      });
      tokenGroups.forEach((group) => {
        group.slice(1).forEach((term) => {
          if (title.includes(term)) score += 5;
          if (section.includes(term)) score += 4;
          if (description.includes(term)) score += 2;
          if (text.includes(term)) score += 1;
        });
      });
      if (locationIntent) {
        if (section.includes("where") || section.includes("location") || section.includes("path")) score += 22;
        if (/~\/|\.env|settings\.yaml|\bpath\b|\bdirectory\b/.test(text)) score += 18;
        if (credentialIntent && text.includes("keys.env")) score += 70;
      }
      ranked.push({
        entry,
        score,
        tokens,
        answerTokens: [...new Set(tokenGroups.flat())],
        href: entryHref(entry),
      });
    });

    ranked.sort((left, right) => right.score - left.score || left.entry.title.localeCompare(right.entry.title));
    const unique = [];
    const seen = new Set();
    for (const result of ranked) {
      const key = result.href;
      if (seen.has(key)) continue;
      seen.add(key);
      unique.push(result);
      if (unique.length >= limit) break;
    }
    return unique;
  }

  function snippetFor(entry, tokens, length = 220) {
    const source = String(entry.text || entry.description || "").replace(/\s+/g, " ").trim();
    if (source.length <= length) return source;
    const lowered = source.toLowerCase();
    const positions = tokens.flatMap((token) => {
      const found = [];
      let from = 0;
      while (from < lowered.length) {
        const index = lowered.indexOf(token, from);
        if (index < 0) break;
        found.push(index);
        from = index + Math.max(token.length, 1);
      }
      return found;
    });
    const matchAt = positions.reduce(
      (best, position) => {
        const start = Math.max(0, position - Math.floor(length * 0.34));
        const window = lowered.slice(start, start + length);
        const score = tokens.filter((token) => window.includes(token)).length;
        return score > best.score ? { position, score } : best;
      },
      { position: 0, score: 0 },
    ).position;
    let start = Math.max(0, matchAt - Math.floor(length * 0.34));
    let end = Math.min(source.length, start + length);
    if (start > 0) {
      const space = source.indexOf(" ", start);
      if (space >= 0 && space < end) start = space + 1;
    }
    if (end < source.length) {
      const space = source.lastIndexOf(" ", end);
      if (space > start) end = space;
    }
    return `${start ? "…" : ""}${source.slice(start, end)}${end < source.length ? "…" : ""}`;
  }

  function appendHighlighted(parent, value, tokens) {
    const safeTokens = tokens
      .filter(Boolean)
      .map((token) => token.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
    if (!safeTokens.length) {
      parent.textContent = value;
      return;
    }
    const matcher = new RegExp(`(${safeTokens.join("|")})`, "gi");
    String(value)
      .split(matcher)
      .forEach((part) => {
        if (safeTokens.some((token) => part.toLowerCase() === token.toLowerCase())) {
          const mark = document.createElement("mark");
          mark.textContent = part;
          parent.append(mark);
        } else {
          parent.append(document.createTextNode(part));
        }
      });
  }

  function closeSearch() {
    if (!searchInput || !searchResults) return;
    searchResults.hidden = true;
    searchResults.setAttribute("aria-busy", "false");
    searchInput.setAttribute("aria-expanded", "false");
    searchInput.removeAttribute("aria-activedescendant");
    activeSearchIndex = -1;
  }

  function setActiveSearch(index) {
    if (!searchInput || !searchResults) return;
    const options = Array.from(searchResults.querySelectorAll("[role='option']"));
    if (!options.length) return;
    activeSearchIndex = (index + options.length) % options.length;
    options.forEach((option, optionIndex) => {
      const active = optionIndex === activeSearchIndex;
      option.setAttribute("aria-selected", String(active));
      option.classList.toggle("is-selected", active);
      if (active) {
        searchInput.setAttribute("aria-activedescendant", option.id);
        option.scrollIntoView({ block: "nearest" });
      }
    });
  }

  async function renderSearch() {
    if (!searchInput || !searchResults) return;
    const requestedQuery = searchInput.value.trim();
    searchResults.replaceChildren();
    activeSearchIndex = -1;
    if (!requestedQuery) {
      closeSearch();
      return;
    }
    searchResults.hidden = false;
    searchInput.setAttribute("aria-expanded", "true");
    searchResults.setAttribute("aria-busy", "true");
    await loadSearchIndex();
    const query = searchInput.value.trim();
    if (!query) {
      closeSearch();
      return;
    }
    const matches = rankEntries(query, 9);
    if (!matches.length) {
      const empty = document.createElement("p");
      empty.className = "search-empty";
      empty.textContent = "No matching documentation. Try fewer or broader words.";
      searchResults.append(empty);
    } else {
      matches.forEach((result, index) => {
        const link = document.createElement("a");
        link.href = result.href;
        link.id = `docs-search-result-${index}`;
        link.setAttribute("role", "option");
        link.setAttribute("aria-selected", "false");
        link.addEventListener("pointerenter", () => setActiveSearch(index));
        const label = document.createElement("span");
        label.className = "search-result-label";
        const title = document.createElement("strong");
        appendHighlighted(title, result.entry.title, result.tokens);
        const section = document.createElement("small");
        section.textContent = result.entry.section && result.entry.section !== "Overview" ? result.entry.section : "Page overview";
        label.append(title, section);
        const description = document.createElement("span");
        appendHighlighted(description, snippetFor(result.entry, result.tokens), result.tokens);
        link.append(label, description);
        searchResults.append(link);
      });
    }
    searchResults.setAttribute("aria-busy", "false");
  }

  searchInput?.addEventListener("input", () => void renderSearch());
  searchInput?.addEventListener("focus", () => void renderSearch());
  searchInput?.addEventListener("keydown", (event) => {
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      setActiveSearch(activeSearchIndex + (event.key === "ArrowDown" ? 1 : -1));
    } else if (event.key === "Enter" && activeSearchIndex >= 0) {
      const selected = searchResults?.querySelectorAll("[role='option']")[activeSearchIndex];
      if (selected instanceof HTMLAnchorElement) {
        event.preventDefault();
        selected.click();
      }
    }
  });

  function openAskDocs() {
    if (!(askDialog instanceof HTMLDialogElement)) return;
    setNav(false);
    if (typeof askDialog.showModal === "function") askDialog.showModal();
    else askDialog.setAttribute("open", "");
    window.setTimeout(() => askInput?.focus(), 0);
  }

  function closeAskDocs() {
    if (!(askDialog instanceof HTMLDialogElement)) return;
    if (typeof askDialog.close === "function") askDialog.close();
    else askDialog.removeAttribute("open");
  }

  askLaunch?.addEventListener("click", openAskDocs);
  askClose?.addEventListener("click", closeAskDocs);
  askDialog?.addEventListener("click", (event) => {
    if (event.target === askDialog) closeAskDocs();
  });

  function addAskMessage(kind, text, mode, results = []) {
    if (!askMessages) return null;
    const message = document.createElement("div");
    message.className = `ask-docs-message is-${kind}`;
    if (mode) {
      const badge = document.createElement("span");
      badge.className = "ask-docs-answer-mode";
      badge.textContent = mode;
      message.append(badge);
    }
    const paragraph = document.createElement("p");
    paragraph.textContent = text;
    message.append(paragraph);
    if (results.length) {
      const sources = document.createElement("div");
      sources.className = "ask-docs-sources";
      const label = document.createElement("strong");
      label.textContent = "Sources";
      sources.append(label);
      results.forEach((result) => {
        const link = document.createElement("a");
        link.href = result.href;
        link.textContent = result.entry.section && result.entry.section !== "Overview"
          ? `${result.entry.title} · ${result.entry.section}`
          : result.entry.title;
        sources.append(link);
      });
      message.append(sources);
    }
    askMessages.append(message);
    askMessages.scrollTop = askMessages.scrollHeight;
    return message;
  }

  function localDocsAnswer(results) {
    const passages = [];
    const seen = new Set();
    let includedKeysPath = false;
    for (const result of results.slice(0, 3)) {
      const directKeysPath = String(result.entry.text || "").match(
        /Keys file\s*[—:-]\s*.+?keys\.env(?:\s*\([^)]*\))?(?:\.\s|$)/i,
      );
      const passage = directKeysPath
        ? directKeysPath[0].replace(/\.\s*$/, "")
        : snippetFor(result.entry, result.answerTokens || result.tokens, 310).replace(/^…|…$/g, "");
      const key = normalize(passage).slice(0, 120);
      if (!passage || seen.has(key)) continue;
      if (passage.includes("keys.env")) {
        if (includedKeysPath) continue;
        includedKeysPath = true;
      }
      seen.add(key);
      passages.push(`${result.entry.section}: ${passage}`);
    }
    if (!passages.length) return "I couldn't find that in the current documentation. Try a shorter question or use search to browse related terms.";
    return passages.join("\n\n");
  }

  async function onDeviceAnswer(question, results) {
    const languageModel = globalThis.LanguageModel;
    if (!languageModel || typeof languageModel.availability !== "function" || typeof languageModel.create !== "function") return null;
    try {
      const availability = await languageModel.availability();
      if (availability !== "available") return null;
      const context = results
        .slice(0, 4)
        .map((result, index) => `[${index + 1}] ${result.entry.title} — ${result.entry.section}\n${result.entry.text}`)
        .join("\n\n");
      const session = await languageModel.create();
      const answer = await session.prompt(
        "Answer the question using only the documentation excerpts below. " +
          "Be concise, concrete, and honest when the excerpts do not contain the answer. " +
          "Do not invent commands, flags, paths, or behavior.\n\n" +
          `Question: ${question}\n\nDocumentation:\n${context}`,
      );
      if (typeof session.destroy === "function") session.destroy();
      return typeof answer === "string" && answer.trim() ? answer.trim() : null;
    } catch (_) {
      return null;
    }
  }

  async function submitAskDocs(question) {
    if (!askMessages) return;
    addAskMessage("user", question);
    askMessages.setAttribute("aria-busy", "true");
    const loading = addAskMessage("assistant", "Searching the complete documentation…", "Working");
    await loadSearchIndex();
    const results = rankEntries(question, 4);
    const generated = results.length ? await onDeviceAnswer(question, results) : null;
    loading?.remove();
    const mode = generated ? "On-device AI · grounded in docs" : "Local docs answer";
    addAskMessage("assistant", generated || localDocsAnswer(results), mode, results.slice(0, 3));
    askMessages.setAttribute("aria-busy", "false");
  }

  askForm?.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!(askInput instanceof HTMLTextAreaElement)) return;
    const question = askInput.value.trim();
    if (!question) return;
    askInput.value = "";
    await submitAskDocs(question);
    askInput.focus();
  });
  askInput?.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      askForm?.requestSubmit();
    }
  });
  document.querySelectorAll("[data-ask-suggestion]").forEach((button) => {
    button.addEventListener("click", () => {
      if (!(askInput instanceof HTMLTextAreaElement)) return;
      askInput.value = button.dataset.askSuggestion || "";
      askForm?.requestSubmit();
    });
  });

  document.addEventListener("keydown", (event) => {
    const target = event.target;
    const typing = target instanceof HTMLInputElement || target instanceof HTMLTextAreaElement;
    if ((event.key === "/" && !typing) || ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k")) {
      event.preventDefault();
      searchInput?.focus();
      searchInput?.select();
    }
    if (event.key === "Escape" && !askDialog?.open) {
      closeSearch();
      setNav(false);
      searchInput?.blur();
    }
  });

  document.addEventListener("click", (event) => {
    if (!(event.target instanceof Node)) return;
    if (!event.target.closest(".docs-search")) closeSearch();
  });

  document.querySelectorAll("pre").forEach((pre) => {
    const code = pre.querySelector("code");
    if (!code || pre.querySelector(".copy-button")) return;
    const button = document.createElement("button");
    button.type = "button";
    button.className = "copy-button";
    button.setAttribute("aria-label", "Copy code to clipboard");
    const icon = document.createElement("span");
    icon.className = "icon icon-clipboard-document";
    icon.setAttribute("aria-hidden", "true");
    const label = document.createElement("span");
    label.textContent = "Copy";
    button.append(icon, label);
    button.addEventListener("click", async () => {
      try {
        await navigator.clipboard.writeText(pre.dataset.copyText || code.textContent);
        label.textContent = "Copied";
        button.classList.add("is-copied");
        window.setTimeout(() => {
          label.textContent = "Copy";
          button.classList.remove("is-copied");
        }, 1600);
      } catch (_) {
        label.textContent = "Select to copy";
      }
    });
    pre.append(button);
  });

  if (article && toc && tocLinks) {
    const headings = Array.from(article.querySelectorAll("h2:not([data-toc='false']), h3:not([data-toc='false'])"));
    if (!headings.length) {
      toc.hidden = true;
    } else {
      const slugCounts = new Map();
      headings.forEach((heading) => {
        if (!heading.id) {
          const base = heading.textContent
            .trim()
            .toLowerCase()
            .replace(/[^a-z0-9\s-]/g, "")
            .replace(/\s+/g, "-") || "section";
          const count = slugCounts.get(base) || 0;
          slugCounts.set(base, count + 1);
          heading.id = count ? `${base}-${count + 1}` : base;
        }
        const link = document.createElement("a");
        link.href = `#${heading.id}`;
        link.textContent = heading.dataset.tocTitle || heading.textContent;
        if (heading.tagName === "H3") link.className = "toc-depth-3";
        tocLinks.append(link);
      });

      const observer = new IntersectionObserver(
        (items) => {
          const visible = items.find((item) => item.isIntersecting);
          if (!visible) return;
          tocLinks.querySelectorAll("a").forEach((link) => {
            link.classList.toggle("is-current", link.hash === `#${visible.target.id}`);
          });
        },
        { rootMargin: "-18% 0px -70% 0px" },
      );
      headings.forEach((heading) => observer.observe(heading));
    }
  }
})();
