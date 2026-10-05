"""Tests for configuration loading and validation."""

import os
from pathlib import Path
import pytest

from review_app.config import ConfigurationError, load_config


def test_missing_backend_raises_error(monkeypatch, tmp_path):
    """Ensure error is raised when neither Gemini nor Ollama is configured."""
    monkeypatch.delenv("GEMINI_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    monkeypatch.delenv("OLLAMA_URL", raising=False)
    monkeypatch.delenv("OLLAMA_MODEL", raising=False)

    checklist = tmp_path / ".checklist"
    checklist.write_text("1. test rule")

    with pytest.raises(ConfigurationError) as exc_info:
        load_config(cli_repo_path=str(tmp_path), cli_checklist=str(checklist))

    assert "Missing LLM backend configuration" in str(exc_info.value)
    assert "GEMINI_KEY and GEMINI_MODEL" in str(exc_info.value)
    assert "OLLAMA_URL and OLLAMA_MODEL" in str(exc_info.value)


def test_partial_gemini_config_raises_error(monkeypatch, tmp_path):
    """Ensure error is raised when GEMINI_KEY is provided without GEMINI_MODEL."""
    monkeypatch.setenv("GEMINI_KEY", "test-key-123")
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    monkeypatch.delenv("OLLAMA_URL", raising=False)
    monkeypatch.delenv("OLLAMA_MODEL", raising=False)

    checklist = tmp_path / ".checklist"
    checklist.write_text("1. test rule")

    with pytest.raises(ConfigurationError) as exc_info:
        load_config(cli_repo_path=str(tmp_path), cli_checklist=str(checklist))

    assert "GEMINI_KEY was provided, but GEMINI_MODEL is missing" in str(exc_info.value)


def test_partial_ollama_config_raises_error(monkeypatch, tmp_path):
    """Ensure error is raised when OLLAMA_URL is provided without OLLAMA_MODEL."""
    monkeypatch.delenv("GEMINI_KEY", raising=False)
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    monkeypatch.setenv("OLLAMA_URL", "http://localhost:11434")
    monkeypatch.delenv("OLLAMA_MODEL", raising=False)

    checklist = tmp_path / ".checklist"
    checklist.write_text("1. test rule")

    with pytest.raises(ConfigurationError) as exc_info:
        load_config(cli_repo_path=str(tmp_path), cli_checklist=str(checklist))

    assert "OLLAMA_URL was provided, but OLLAMA_MODEL is missing" in str(exc_info.value)


def test_gemini_configured_via_env(monkeypatch, tmp_path):
    """Test Gemini backend selection via environment variables."""
    monkeypatch.setenv("GEMINI_KEY", "fake-gemini-key")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-2.5-flash")
    monkeypatch.delenv("OLLAMA_URL", raising=False)
    monkeypatch.delenv("OLLAMA_MODEL", raising=False)

    checklist = tmp_path / ".checklist"
    checklist.write_text("1. rule 1")

    config = load_config(cli_repo_path=str(tmp_path), cli_checklist=str(checklist))
    assert config.backend_type == "gemini"
    assert config.gemini_key == "fake-gemini-key"
    assert config.gemini_model == "gemini-2.5-flash"


def test_ollama_configured_via_env(monkeypatch, tmp_path):
    """Test Ollama backend selection via environment variables."""
    monkeypatch.delenv("GEMINI_KEY", raising=False)
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    monkeypatch.setenv("OLLAMA_URL", "http://localhost:11434")
    monkeypatch.setenv("OLLAMA_MODEL", "llama3")

    checklist = tmp_path / ".checklist"
    checklist.write_text("1. rule 1")

    config = load_config(cli_repo_path=str(tmp_path), cli_checklist=str(checklist))
    assert config.backend_type == "ollama"
    assert config.ollama_url == "http://localhost:11434"
    assert config.ollama_model == "llama3"


def test_both_configured_explicit_selection(monkeypatch, tmp_path):
    """Test explicit backend override when both backends are provided."""
    monkeypatch.setenv("GEMINI_KEY", "fake-gemini-key")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-2.5-flash")
    monkeypatch.setenv("OLLAMA_URL", "http://localhost:11434")
    monkeypatch.setenv("OLLAMA_MODEL", "llama3")

    checklist = tmp_path / ".checklist"
    checklist.write_text("1. rule 1")

    # Default should prefer gemini
    config_default = load_config(cli_repo_path=str(tmp_path), cli_checklist=str(checklist))
    assert config_default.backend_type == "gemini"

    # Explicit ollama selection
    config_ollama = load_config(
        cli_backend="ollama",
        cli_repo_path=str(tmp_path),
        cli_checklist=str(checklist)
    )
    assert config_ollama.backend_type == "ollama"


def test_missing_checklist_raises_error(monkeypatch, tmp_path):
    """Ensure missing checklist file raises ConfigurationError."""
    monkeypatch.setenv("GEMINI_KEY", "key")
    monkeypatch.setenv("GEMINI_MODEL", "model")

    with pytest.raises(ConfigurationError) as exc_info:
        load_config(cli_repo_path=str(tmp_path), cli_checklist=str(tmp_path / "nonexistent.md"))

    assert "Checklist file not found" in str(exc_info.value)
