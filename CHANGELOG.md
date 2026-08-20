# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0](https://github.com/Davsooonowy/pytest-agent-trace/compare/pytest-agent-trace-v0.1.0...pytest-agent-trace-v0.2.0) (2026-08-20)


### Features

* --record-mode (none/once/all) ([704edd9](https://github.com/Davsooonowy/pytest-agent-trace/commit/704edd9ee5bf4bb7e72b2c0bc94af026a09aeeb6))
* [@pytest](https://github.com/pytest).mark.agent_cassette marker ([b70d413](https://github.com/Davsooonowy/pytest-agent-trace/commit/b70d413f92eeadfa5b99d773f8fa75bbd646e27a))
* add --record-mode (none/once/all), replacing the boolean --record flag ([3e2dc35](https://github.com/Davsooonowy/pytest-agent-trace/commit/3e2dc35fe8e518d109ad7ab18b7a519c0c0dad9c))
* add [@pytest](https://github.com/pytest).mark.agent_cassette marker ([cc8a8a3](https://github.com/Davsooonowy/pytest-agent-trace/commit/cc8a8a3179f5766d9f211b08319ed02d406fc9a3))
* add a real (not fake) Ollama + F1 example, replacing the "just trust me" gap ([3fe9646](https://github.com/Davsooonowy/pytest-agent-trace/commit/3fe964613dd8bae55ecd9521bf5bb06b14819869))
* add chaos engineering (fault injection + resilience assertions) ([f7780a4](https://github.com/Davsooonowy/pytest-agent-trace/commit/f7780a471dd49fb3048e9596657a00b379058fc6))
* add configurable cassette base directory ([878af47](https://github.com/Davsooonowy/pytest-agent-trace/commit/878af47ff10586024d1fb92c504e8db01b5857c3))
* add core trajectory event log, cassette I/O, fluent assertions and pytest plugin ([25123e9](https://github.com/Davsooonowy/pytest-agent-trace/commit/25123e952e6a990c0ba81677b2b258938179c4fc))
* add LangGraph recorder adapter, demo agent, and CrewAI stub ([262e812](https://github.com/Davsooonowy/pytest-agent-trace/commit/262e81216e420df35c42379a1e06bb5c7402742f))
* add LangGraph replay engine (offline, deterministic, zero API cost) ([cddfdf0](https://github.com/Davsooonowy/pytest-agent-trace/commit/cddfdf0ec29380282906ebd3ba6e923a556dd03c))
* add latency and token-usage tracking to the diff engine ([bf562db](https://github.com/Davsooonowy/pytest-agent-trace/commit/bf562dbe331d20eb3c8fcac20e25c2cb690e6005))
* add opt-in PII/secret redaction for recorded cassettes ([d3d864c](https://github.com/Davsooonowy/pytest-agent-trace/commit/d3d864c83b1b5196cde968ac7124f9eb6f57dc28))
* add trajectory diff engine and wire --agent-diff-baseline ([006e892](https://github.com/Davsooonowy/pytest-agent-trace/commit/006e89281cfcd8b2c3c3db13878dda12e9956be2))
* configurable cassette base directory ([7f366dd](https://github.com/Davsooonowy/pytest-agent-trace/commit/7f366dde2a05ca694c74699b97fefe32b2f0a96e))
* latency + token-usage tracking in the diff engine ([2af89ce](https://github.com/Davsooonowy/pytest-agent-trace/commit/2af89ce610401bc799758e55bc3e1d8942a0107a))
* opt-in PII/secret redaction for recorded cassettes ([3bfa8a1](https://github.com/Davsooonowy/pytest-agent-trace/commit/3bfa8a18177c606ac682a92cb9b9a11b0fc8e640))
* real Ollama + F1 example (replaces the fake-model gap in README) ([68651d4](https://github.com/Davsooonowy/pytest-agent-trace/commit/68651d4a4a140b3cfc0d1d87ae552f3e52a8c3eb))
* wire --record to actually run LangGraphRecorder ([bccfe03](https://github.com/Davsooonowy/pytest-agent-trace/commit/bccfe03ee160dcc52717eb5b3835ad2e1a6f862c))


### Bug Fixes

* add project.urls, exclude .idea from build artifacts ([8076d66](https://github.com/Davsooonowy/pytest-agent-trace/commit/8076d66b6773ea4845765e73a8fd33ab16aba34a))
* PyPI packaging fixes (project.urls, exclude .idea) ([05233fb](https://github.com/Davsooonowy/pytest-agent-trace/commit/05233fb6dd2d0f883594e2543935d92e668b8a2f))


### Documentation

* drop the pip-extra explainer, target audience already knows ([7c826fc](https://github.com/Davsooonowy/pytest-agent-trace/commit/7c826fcc5592d4b63a05d7cfd79f912ec7dca837))
* lead README with the real Ollama+F1 example ([a6e0e25](https://github.com/Davsooonowy/pytest-agent-trace/commit/a6e0e254de55208cf506e18542850165998de88a))
* lead the README with the real Ollama+F1 example, drop the fake one ([ea17b45](https://github.com/Davsooonowy/pytest-agent-trace/commit/ea17b453b1cbc2520294a717fde487f3da0e6699))
* proper OSS README + LICENSE ([47f9d35](https://github.com/Davsooonowy/pytest-agent-trace/commit/47f9d3598f2a7fedd1d8fb841c9bb290b58130b3))
* rewrite README as a proper OSS project page ([8244d66](https://github.com/Davsooonowy/pytest-agent-trace/commit/8244d66f69469ccfa0b188b9cf7c4a18f31c8370))

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
