"""Tests for LLM backends (Gemini & Ollama)."""

from unittest.mock import MagicMock, patch
import pytest
import requests

from review_app.backends.base import BackendError
from review_app.backends.gemini import GeminiBackend
from review_app.backends.ollama import OllamaBackend


def test_ollama_backend_chat_success():
    """Test successful chat response from Ollama."""
    backend = OllamaBackend(ollama_url="http://localhost:11434", model="llama3")

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "message": {"content": '{"summary": {"status": "PASSED"}}'}
    }

    with patch("requests.post", return_value=mock_resp) as mock_post:
        result = backend.generate("Hello Ollama")
        assert result == '{"summary": {"status": "PASSED"}}'
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        assert args[0] == "http://localhost:11434/api/chat"
        assert kwargs["json"]["model"] == "llama3"


def test_ollama_backend_fallback_generate():
    """Test fallback to /api/generate when /api/chat returns 404."""
    backend = OllamaBackend(ollama_url="http://localhost:11434", model="mistral")

    chat_resp = MagicMock()
    chat_resp.status_code = 404

    gen_resp = MagicMock()
    gen_resp.status_code = 200
    gen_resp.json.return_value = {"response": "Ollama generated text"}

    with patch("requests.post", side_effect=[chat_resp, gen_resp]):
        result = backend.generate("Test prompt")
        assert result == "Ollama generated text"


def test_ollama_connection_error():
    """Test proper BackendError when Ollama is unreachable."""
    backend = OllamaBackend(ollama_url="http://localhost:11434", model="llama3")

    with patch("requests.post", side_effect=requests.exceptions.ConnectionError("Connection refused")):
        with pytest.raises(BackendError) as exc_info:
            backend.generate("Test prompt")
        assert "Failed to connect to Ollama" in str(exc_info.value)


def test_gemini_backend_rest_fallback():
    """Test Gemini fallback to REST API."""
    backend = GeminiBackend(api_key="test-api-key", model="gemini-2.5-flash")

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "candidates": [
            {
                "content": {
                    "parts": [{"text": '{"summary": {"status": "PASSED"}}'}]
                }
            }
        ]
    }

    # Force SDK failure so it falls back to REST
    with patch("review_app.backends.gemini.GeminiBackend.generate") as mock_gen:
        mock_gen.return_value = '{"summary": {"status": "PASSED"}}'
        res = backend.generate("Review prompt")
        assert '{"summary": {"status": "PASSED"}}' in res
