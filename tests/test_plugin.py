from pathlib import Path

CASSETTE = (Path(__file__).parent.parent / "examples" / "weather_query.cassette.jsonl").resolve()


def test_agent_cassette_fixture_is_registered(pytester):
    pytester.makepyfile(
        f"""
        def test_matches(agent_cassette):
            trace = agent_cassette.load(r"{CASSETTE}")
            assert trace.final_output == "W Warszawie jest 18 stopni"
            agent_cassette.assert_matches("W Warszawie jest 18 stopni")
        """
    )
    result = pytester.runpytest()
    result.assert_outcomes(passed=1)


def test_agent_cassette_assert_matches_fails_on_mismatch(pytester):
    pytester.makepyfile(
        f"""
        def test_mismatch(agent_cassette):
            agent_cassette.load(r"{CASSETTE}")
            agent_cassette.assert_matches("cos innego")
        """
    )
    result = pytester.runpytest()
    result.assert_outcomes(failed=1)


def test_record_and_diff_flags_are_registered(pytester):
    pytester.makepyfile(
        """
        def test_flags(agent_cassette):
            assert agent_cassette.record is True
            assert agent_cassette.diff_baseline is True
        """
    )
    result = pytester.runpytest("--record", "--agent-diff-baseline")
    result.assert_outcomes(passed=1)


def _write_diverged_cassette(pytester) -> Path:
    diverged = pytester.path / "diverged.cassette.jsonl"
    diverged.write_text(
        "\n".join(
            [
                '{"seq": 1, "type": "run_started", "run_id": "r1", "input": {"query": "x"}}',
                '{"seq": 2, "type": "llm_call", "run_id": "r1", "response": "thinking"}',
                '{"seq": 3, "type": "tool_call", "run_id": "r1", "tool": "get_weather", '
                '"args": {"city": "Krakow"}}',
                '{"seq": 4, "type": "llm_call", "run_id": "r1", "response": "18 w Krakowie"}',
                '{"seq": 5, "type": "run_finished", "run_id": "r1", "final_output": "18 stopni"}',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return diverged


def test_diff_against_baseline_reports_but_does_not_fail_without_flag(pytester):
    diverged = _write_diverged_cassette(pytester)
    pytester.makepyfile(
        f"""
        def test_diff(agent_cassette):
            agent_cassette.load(r"{diverged}")
            diff = agent_cassette.diff_against_baseline(r"{CASSETTE}")
            assert diff.is_significant
        """
    )
    result = pytester.runpytest()
    result.assert_outcomes(passed=1)


def test_diff_against_baseline_fails_with_flag_on_significant_change(pytester):
    diverged = _write_diverged_cassette(pytester)
    pytester.makepyfile(
        f"""
        def test_diff(agent_cassette):
            agent_cassette.load(r"{diverged}")
            agent_cassette.diff_against_baseline(r"{CASSETTE}")
        """
    )
    result = pytester.runpytest("--agent-diff-baseline")
    result.assert_outcomes(failed=1)
    result.stdout.fnmatch_lines(["*args changed*"])
