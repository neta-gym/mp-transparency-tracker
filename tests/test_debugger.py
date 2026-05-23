"""Tests for the DebuggerAgent and its data structures."""

from __future__ import annotations

import asyncio
import pytest

from tracker.debugger import CheckStatus, CheckResult, SuiteResult, DebuggerAgent


# ---------------------------------------------------------------------------
# CheckResult tests
# ---------------------------------------------------------------------------

class TestCheckResult:
    def test_pass_result(self):
        r = CheckResult(name="test", status=CheckStatus.PASS, message="ok")
        assert r.name == "test"
        assert r.status == CheckStatus.PASS
        assert r.message == "ok"

    def test_fail_result(self):
        r = CheckResult(name="fail_test", status=CheckStatus.FAIL, message="bad")
        assert r.status == CheckStatus.FAIL

    def test_defaults(self):
        r = CheckResult(name="x", status=CheckStatus.WARN)
        assert r.message == ""
        assert r.details == ""
        assert r.duration_ms == 0.0


# ---------------------------------------------------------------------------
# SuiteResult tests
# ---------------------------------------------------------------------------

class TestSuiteResult:
    def test_empty_suite(self):
        s = SuiteResult(suite_name="empty")
        assert s.passed == 0
        assert s.failed == 0
        assert s.warned == 0
        assert s.skipped == 0

    def test_counting_properties(self):
        s = SuiteResult(suite_name="mixed", checks=[
            CheckResult("a", CheckStatus.PASS),
            CheckResult("b", CheckStatus.PASS),
            CheckResult("c", CheckStatus.FAIL),
            CheckResult("d", CheckStatus.WARN),
            CheckResult("e", CheckStatus.SKIP),
            CheckResult("f", CheckStatus.PASS),
        ])
        assert s.passed == 3
        assert s.failed == 1
        assert s.warned == 1
        assert s.skipped == 1

    def test_all_pass(self):
        s = SuiteResult(suite_name="good", checks=[
            CheckResult("a", CheckStatus.PASS),
            CheckResult("b", CheckStatus.PASS),
        ])
        assert s.passed == 2
        assert s.failed == 0

    def test_all_fail(self):
        s = SuiteResult(suite_name="bad", checks=[
            CheckResult("a", CheckStatus.FAIL),
            CheckResult("b", CheckStatus.FAIL),
        ])
        assert s.passed == 0
        assert s.failed == 2


# ---------------------------------------------------------------------------
# DebuggerAgent suite tests
# ---------------------------------------------------------------------------

class TestScoringInvariants:
    """Test that check_scoring_invariants passes with no failures."""

    def test_scoring_suite_passes(self):
        agent = DebuggerAgent(data_dir="data", db_path="data/tracker.db")
        result = asyncio.run(agent.check_scoring_invariants())
        assert result.suite_name == "Scoring Algorithm Invariants"
        assert result.failed == 0, (
            f"Scoring invariant failures: "
            + ", ".join(c.name + ": " + c.message for c in result.checks if c.status == CheckStatus.FAIL)
        )


class TestEnvironmentSuite:
    """Test that check_environment includes expected checks."""

    def test_environment_includes_expected_checks(self):
        agent = DebuggerAgent(data_dir="data", db_path="data/tracker.db")
        result = asyncio.run(agent.check_environment())
        check_names = [c.name for c in result.checks]

        assert "Score weights sum to 1.0" in check_names
        assert "Data directory exists" in check_names
        assert "Database file exists" in check_names
        assert "Python >= 3.10" in check_names
        assert ".env file exists" in check_names

        # Dependency checks
        assert any("Import" in n for n in check_names)

    def test_python_version_passes(self):
        agent = DebuggerAgent(data_dir="data", db_path="data/tracker.db")
        result = asyncio.run(agent.check_environment())
        py_check = next(c for c in result.checks if c.name == "Python >= 3.10")
        assert py_check.status == CheckStatus.PASS

    def test_weights_pass(self):
        agent = DebuggerAgent(data_dir="data", db_path="data/tracker.db")
        result = asyncio.run(agent.check_environment())
        w_check = next(c for c in result.checks if c.name == "Score weights sum to 1.0")
        assert w_check.status == CheckStatus.PASS


class TestModelRoundTrip:
    """Test that check_model_roundtrip passes with no failures."""

    def test_model_roundtrip_passes(self):
        agent = DebuggerAgent(data_dir="data", db_path="data/tracker.db")
        result = asyncio.run(agent.check_model_roundtrip())
        assert result.suite_name == "Pydantic Model Round-Trip"
        assert result.failed == 0, (
            f"Model round-trip failures: "
            + ", ".join(c.name + ": " + c.message for c in result.checks if c.status == CheckStatus.FAIL)
        )

    def test_roundtrip_includes_computed_fields(self):
        agent = DebuggerAgent(data_dir="data", db_path="data/tracker.db")
        result = asyncio.run(agent.check_model_roundtrip())
        check_names = [c.name for c in result.checks]
        assert "ResearchFindings computed fields" in check_names


class TestCheckStatus:
    def test_enum_values(self):
        assert CheckStatus.PASS.value == "PASS"
        assert CheckStatus.FAIL.value == "FAIL"
        assert CheckStatus.WARN.value == "WARN"
        assert CheckStatus.SKIP.value == "SKIP"
