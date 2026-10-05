"""Base interface for LLM backends."""

from abc import ABC, abstractmethod
from typing import Optional


class BackendError(Exception):
    """Raised when an LLM backend API call fails."""
    pass


class BaseBackend(ABC):
    """Abstract Base Class for LLM providers."""

    def __init__(self, model: str):
        self.model = model

    @property
    @abstractmethod
    def name(self) -> str:
        """Name of the backend provider."""
        pass

    @abstractmethod
    def generate(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """
        Generate text response from the model.

        :param prompt: The user prompt containing checklist and codebase context.
        :param system_prompt: Optional instructions defining the model's persona and output format.
        :return: Generated text response from the LLM.
        """
        pass
