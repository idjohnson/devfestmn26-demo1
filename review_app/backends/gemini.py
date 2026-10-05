"""Vertex AI / Gemini backend implementation."""

import json
from typing import Optional
import requests

from review_app.backends.base import BackendError, BaseBackend


class GeminiBackend(BaseBackend):
    """LLM backend using Google GenAI SDK / Vertex AI (Gemini)."""

    def __init__(
        self,
        api_key: str,
        model: str,
        vertexai: bool = False,
        project: Optional[str] = None,
        location: Optional[str] = None,
    ):
        super().__init__(model=model)
        self.api_key = api_key
        self.vertexai = vertexai
        self.project = project
        self.location = location

    @property
    def name(self) -> str:
        return "Vertex AI (Gemini)" if self.vertexai else "Gemini"

    def generate(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """Generate response via google-genai SDK with REST fallback."""
        # 1. Try modern google-genai SDK
        try:
            from google import genai
            from google.genai import types

            client_kwargs = {"api_key": self.api_key}
            if self.vertexai:
                client_kwargs["vertexai"] = True
                if self.project:
                    client_kwargs["project"] = self.project
                if self.location:
                    client_kwargs["location"] = self.location

            client = genai.Client(**client_kwargs)

            config = types.GenerateContentConfig(
                temperature=0.1,
                response_mime_type="application/json",
            )
            if system_prompt:
                config.system_instruction = system_prompt

            response = client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=config,
            )
            if response.text:
                return response.text
        except Exception as sdk_err:
            # If vertexai was explicitly set, do not fallback to standard Gemini REST API
            if self.vertexai:
                raise BackendError(f"Vertex AI Gemini request failed: {sdk_err}") from sdk_err
            # Otherwise, try REST API as fallback
            try:
                return self._generate_rest(prompt, system_prompt)
            except Exception as rest_err:
                raise BackendError(
                    f"Gemini API request failed via SDK ({sdk_err}) and REST fallback ({rest_err})"
                ) from rest_err

        raise BackendError("Gemini returned empty response text.")

    def _generate_rest(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """Direct REST fallback to Google Gemini generateContent API."""
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.model}:generateContent?key={self.api_key}"
        )
        payload = {
            "contents": [
                {
                    "parts": [{"text": prompt}]
                }
            ],
            "generationConfig": {
                "temperature": 0.1,
                "responseMimeType": "application/json",
            }
        }
        if system_prompt:
            payload["systemInstruction"] = {
                "parts": [{"text": system_prompt}]
            }

        headers = {"Content-Type": "application/json"}
        resp = requests.post(url, headers=headers, json=payload, timeout=90)

        if resp.status_code != 200:
            raise BackendError(
                f"Gemini REST API error {resp.status_code}: {resp.text}"
            )

        data = resp.json()
        candidates = data.get("candidates", [])
        if not candidates:
            raise BackendError(f"Gemini REST response had no candidates: {data}")

        parts = candidates[0].get("content", {}).get("parts", [])
        if not parts or "text" not in parts[0]:
            raise BackendError(f"Gemini REST response had no text part: {candidates[0]}")

        return parts[0]["text"]
