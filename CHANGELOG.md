# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Opt-in PII/secret redaction (`Redactor`) applied at record time.
- Latency and token-usage tracking in the diff engine (informational, data-driven — no new flag).
- `assert_trajectory(...).max_total_tokens(n)`.
- A real (Ollama `llama3.2:3b`) recorded example, `examples/f1_agent.py`, alongside the scripted demo agents.
- `--record-mode {none,once,all}` replacing the boolean `--record` flag.
- `@pytest.mark.agent_cassette(path)` marker.
- `--agent-cassette-dir` CLI option / `agent_cassette_dir` ini option.

## [0.1.0] - 2026-08-19

Initial release.

### Added

- Cassette format: append-only JSONL event log (`run_started`/`llm_call`/`tool_call`/`run_finished`).
- `AgentTrace` + `assert_trajectory(...)` fluent trajectory assertions.
- `LangGraphRecorder` / `LangGraphReplayer` — record a real LangGraph agent run, replay it offline with zero API calls.
- `diff_trajectories(...)` + `--agent-diff-baseline` regression detection.
- Chaos engineering: `ChaosScenario` fault library, `inject_tool_chaos`, `assert_resilience(...)`.
- pytest plugin: `agent_cassette` fixture, `agent-trace` CLI (`show`, `diff`).
