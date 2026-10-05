"""Tests for CLI entrypoint and exit codes."""

from unittest.mock import MagicMock, patch
import pytest

from review_app.cli import main
from review_app.models import ReviewReport, ReviewStatus, ReviewSummary, RuleResult


def test_cli_missing_config_returns_exit_2(monkeypatch):
    """CLI should exit with code 2 when backend configuration is missing."""
    monkeypatch.delenv("GEMINI_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    monkeypatch.delenv("OLLAMA_URL", raising=False)
    monkeypatch.delenv("OLLAMA_MODEL", raising=False)

    exit_code = main(["--checklist", ".checklist"])
    assert exit_code == 2


def test_cli_passed_review_returns_exit_0(monkeypatch, tmp_path):
    """CLI should exit with code 0 when all checklist items pass."""
    checklist = tmp_path / ".checklist"
    checklist.write_text("1. All good")

    fake_report = ReviewReport(
        repository=str(tmp_path),
        checklist_path=str(checklist),
        backend="Gemini",
        model="gemini-2.5-flash",
        timestamp="2026-10-05T00:00:00Z",
        summary=ReviewSummary(total=1, passed=1, failed=0, warnings=0, status="PASSED"),
        results=[
            RuleResult(index=1, rule="All good", status=ReviewStatus.PASS, evidence="Verified")
        ],
    )

    with patch("review_app.cli.run_review", return_value=fake_report):
        exit_code = main([
            "--repo", str(tmp_path),
            "--checklist", str(checklist),
            "--gemini-key", "fake-key",
            "--gemini-model", "gemini-2.5-flash",
            "--format", "json",
        ])
        assert exit_code == 0


def test_cli_failed_review_returns_exit_1(monkeypatch, tmp_path):
    """CLI should exit with code 1 when any checklist item fails."""
    checklist = tmp_path / ".checklist"
    checklist.write_text("1. Must pass")

    fake_report = ReviewReport(
        repository=str(tmp_path),
        checklist_path=str(checklist),
        backend="Ollama",
        model="llama3",
        timestamp="2026-10-05T00:00:00Z",
        summary=ReviewSummary(total=1, passed=0, failed=1, warnings=0, status="FAILED"),
        results=[
            RuleResult(
                index=1,
                rule="Must pass",
                status=ReviewStatus.FAIL,
                evidence="Violated rule",
                remediation="Fix it"
            )
        ],
    )

    with patch("review_app.cli.run_review", return_value=fake_report):
        exit_code = main([
            "--repo", str(tmp_path),
            "--checklist", str(checklist),
            "--ollama-url", "http://localhost:11434",
            "--ollama-model", "llama3",
            "--format", "markdown",
        ])
        assert exit_code == 1


def test_cli_no_fail_exit_flag(monkeypatch, tmp_path):
    """CLI with --no-fail-exit should exit with 0 even if rules failed."""
    checklist = tmp_path / ".checklist"
    checklist.write_text("1. Must pass")

    fake_report = ReviewReport(
        repository=str(tmp_path),
        checklist_path=str(checklist),
        backend="Ollama",
        model="llama3",
        timestamp="2026-10-05T00:00:00Z",
        summary=ReviewSummary(total=1, passed=0, failed=1, warnings=0, status="FAILED"),
        results=[
            RuleResult(
                index=1,
                rule="Must pass",
                status=ReviewStatus.FAIL,
                evidence="Violated rule",
            )
        ],
    )

    with patch("review_app.cli.run_review", return_value=fake_report):
        exit_code = main([
            "--repo", str(tmp_path),
            "--checklist", str(checklist),
            "--ollama-url", "http://localhost:11434",
            "--ollama-model", "llama3",
            "--no-fail-exit",
        ])
        assert exit_code == 0
