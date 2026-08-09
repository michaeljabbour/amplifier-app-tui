---
layout: default
title: Development
permalink: /development/
---

These notes are for contributors working from a repository checkout.

## Install development dependencies

```sh
uv sync
```

## Run focused tests

```sh
uv run pytest -q tests/test_docs_site_contract.py
```

## Run the default local gate

```sh
uv run ruff check .
uv run pyright src/
uv run pytest -q
```

Keep documentation changes static. The Pages workflow builds the site with GitHub's Jekyll action, so this repository does not need a local docs framework dependency.
