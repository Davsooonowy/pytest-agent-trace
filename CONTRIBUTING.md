# Contributing

Thanks for considering a contribution to `pytest-agent-trace`. This is a young project, so issues and PRs of any size are welcome — from a typo fix to a new framework adapter.

## Reporting a bug

Open an [issue](https://github.com/Davsooonowy/pytest-agent-trace/issues/new). Include:

- What you ran, and what you expected vs. what happened.
- The `pytest-agent-trace` version (`pip show pytest-agent-trace`), Python version, and which extras you installed (`langgraph`, etc.).
- A minimal reproduction if you can — a small agent + cassette that shows the problem is worth far more than a description.

## Proposing a feature

Open an issue first for anything non-trivial (a new adapter, a new assertion method, a change to the cassette format) before writing code — it's a lot cheaper to align on the approach in a comment thread than after a PR is already up.

## Development setup

```bash
git clone https://github.com/Davsooonowy/pytest-agent-trace.git
cd pytest-agent-trace
uv sync --extra langgraph --extra dev
```

Run the checks the CI runs, before you push:

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy src
```

`uv run pytest` runs the full suite except one test that needs a local [Ollama](https://ollama.com) server (`ollama pull llama3.2:3b`) — it's skipped automatically if Ollama isn't reachable, so you don't need it installed to contribute.

## Code style

- `ruff` (lint + format) and `mypy` gate every PR — run them locally first, CI just double-checks.
- Comments explain *why*, not *what* — if a comment just restates the line below it, delete it. Do explain non-obvious behavior (a framework quirk, an empirically-verified event shape, a subtle invariant).
- No unrequested abstractions or speculative flags — see the diff engine's latency/token tracking (`core/diff.py`) for the house style: richness follows from what was actually recorded, not from a new CLI knob, wherever that's possible.
- Match the existing adapter pattern: `core/` never imports a framework-specific object directly. Framework-specific code lives in exactly one file per framework under `adapters/`.

## Pull requests

- One logical change per PR — easier to review, easier to revert if something's wrong.
- Add tests for anything you change. If you're fixing a bug, a regression test that fails without your fix is the clearest way to show the fix is real.
- `uv run pytest`, `ruff check .`, `ruff format --check .`, and `mypy src` should all pass before you open the PR — CI runs the same checks.
- Describe *why* in the PR description, not just what changed — the diff already shows what changed.
