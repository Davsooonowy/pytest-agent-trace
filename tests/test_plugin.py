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
