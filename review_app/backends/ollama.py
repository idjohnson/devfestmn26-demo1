"""Ollama backend implementation."""

from typing import Optional
import requests

from review_app.backends.base import BackendError, BaseBackend


class OllamaBackend(BaseBackend):
    """LLM backend using local or remote Ollama server."""

    def __init__(self, ollama_url: str, model: str):
        super().__init__(model=model)
        self.ollama_url = ollama_url.rstrip("/")

    @property
    def name(self) -> str:
        return "Ollama"

    def generate(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """Send generation request to Ollama using /api/chat or /api/generate."""
        chat_url = f"{self.ollama_url}/api/chat"
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "format": "json",
            "options": {
                "temperature": 0.1,
            },
        }

        try:
            resp = requests.post(chat_url, json=payload, timeout=120)
            if resp.status_code == 200:
                data = resp.json()
                message = data.get("message", {})
                content = message.get("content")
                if content:
                    return content
                raise BackendError(f"Ollama chat response missing content: {data}")
            elif resp.status_code == 404:
                # Fall back to /api/generate for older Ollama versions
                return self._generate_fallback(prompt, system_prompt)
            else:
                raise BackendError(
                    f"Ollama returned HTTP status {resp.status_code}: {resp.text}"
                )
        except requests.exceptions.ConnectionError as ce:
            raise BackendError(
                f"Failed to connect to Ollama at '{self.ollama_url}'. "
                "Please verify that Ollama is running and accessible."
            ) from ce
        except requests.exceptions.Timeout as te:
            raise BackendError(
                f"Request to Ollama at '{self.ollama_url}' timed out."
            ) from te
        except BackendError:
            raise
        except Exception as e:
            raise BackendError(f"Ollama generation error: {e}") from e

    def _generate_fallback(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """Fallback to Ollama /api/generate endpoint."""
        url = f"{self.ollama_url}/api/generate"
        combined_prompt = f"System: {system_prompt}\n\nUser: {prompt}" if system_prompt else prompt
        payload = {
            "model": self.model,
            "prompt": combined_prompt,
            "stream": False,
            "format": "json",
            "options": {
                "temperature": 0.1,
            },
        }
        resp = requests.post(url, json=payload, timeout=120)
        if resp.status_code != 200:
            raise BackendError(
                f"Ollama /api/generate error {resp.status_code}: {resp.text}"
            )
        data = resp.json()
        response_text = data.get("response")
        if not response_text:
            raise BackendError(f"Ollama /api/generate missing response text: {data}")
        return response_text
