"""Tests for reviewer logic, JSON parsing, and report generation."""

from pathlib import Path
from unittest.mock import MagicMock
import pytest

from review_app.backends.base import BaseBackend
from review_app.config import AppConfig
from review_app.models import ReviewStatus
from review_app.reviewer import extract_json_from_text, parse_llm_response, run_review


def test_extract_json_from_markdown():
    """Ensure JSON is extracted correctly from markdown fences."""
    text_with_fences = """Here is the review result:
```json
{
  "summary": {
    "total": 1,
    "passed": 1,
    "failed": 0,
    "warnings": 0,
    "status": "PASSED"
  },
  "results": [
    {
      "index": 1,
      "rule": "Rule 1",
      "status": "PASS",
      "evidence": "Matches criteria",
      "remediation": null
    }
  ]
}
```
Done!"""

    data = extract_json_from_text(text_with_fences)
    assert data is not None
    assert data["summary"]["status"] == "PASSED"
    assert len(data["results"]) == 1


def test_parse_llm_response_success(tmp_path):
    """Test parsing well-formed JSON into ReviewReport."""
    config = AppConfig(
        backend_type="gemini",
        repo_path=tmp_path,
        checklist_path=tmp_path / ".checklist",
        gemini_key="key",
        gemini_model="gemini-2.5-flash",
    )

    sample_json = """{
      "summary": {
        "total": 2,
        "passed": 1,
        "failed": 1,
        "warnings": 0,
        "status": "FAILED"
      },
      "results": [
        {
          "index": 1,
          "rule": "Every commit mentions a Vikunja ticket",
          "status": "FAIL",
          "evidence": "Commit bff2d5e ('first') has no #nnn ticket.",
          "remediation": "Amend commit message to include ticket."
        },
        {
          "index": 2,
          "rule": "Every commit has a committer",
          "status": "PASS",
          "evidence": "All commits have valid committer info.",
          "remediation": null
        }
      ]
    }"""

    report = parse_llm_response(
        raw_response=sample_json,
        config=config,
        backend_name="Gemini",
        model_name="gemini-2.5-flash",
    )

    assert report.summary.total == 2
    assert report.summary.passed == 1
    assert report.summary.failed == 1
    assert report.summary.status == "FAILED"
    assert len(report.results) == 2
    assert report.results[0].status == ReviewStatus.FAIL
    assert report.results[1].status == ReviewStatus.PASS


def test_parse_llm_response_malformed(tmp_path):
    """Test graceful fallback when LLM returns non-JSON text."""
    config = AppConfig(
        backend_type="ollama",
        repo_path=tmp_path,
        checklist_path=tmp_path / ".checklist",
        ollama_url="http://localhost:11434",
        ollama_model="llama3",
    )

    raw_text = "I evaluated the checklist and everything looks mostly okay."
    report = parse_llm_response(
        raw_response=raw_text,
        config=config,
        backend_name="Ollama",
        model_name="llama3",
    )

    assert report.summary.status == "FAILED"
    assert report.results[0].status == ReviewStatus.WARN
    assert "could not be parsed as JSON" in report.results[0].evidence


def test_run_review_flow(tmp_path):
    """Test full review execution flow with mock backend."""
    checklist = tmp_path / ".checklist"
    checklist.write_text("1. rule 1\n2. rule 2")

    config = AppConfig(
        backend_type="gemini",
        repo_path=tmp_path,
        checklist_path=checklist,
        gemini_key="key",
        gemini_model="gemini-2.5-flash",
    )

    mock_backend = MagicMock(spec=BaseBackend)
    mock_backend.name = "Gemini"
    mock_backend.model = "gemini-2.5-flash"
    mock_backend.generate.return_value = """{
      "summary": {"total": 2, "passed": 2, "failed": 0, "warnings": 0, "status": "PASSED"},
      "results": [
        {"index": 1, "rule": "rule 1", "status": "PASS", "evidence": "good"},
        {"index": 2, "rule": "rule 2", "status": "PASS", "evidence": "good"}
      ]
    }"""

    report = run_review(config=config, backend=mock_backend)
    assert report.summary.status == "PASSED"
    assert report.summary.passed == 2
    assert report.summary.failed == 0
