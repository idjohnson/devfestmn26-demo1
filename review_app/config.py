"""Configuration management for Review App."""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


class ConfigurationError(Exception):
    """Raised when configuration or environment variables are invalid or missing."""
    pass


@dataclass
class AppConfig:
    """Application configuration parameters."""
    backend_type: str  # "gemini" or "ollama"
    repo_path: Path
    checklist_path: Path

    # Gemini configuration
    gemini_key: Optional[str] = None
    gemini_model: Optional[str] = None
    vertexai: bool = False
    project: Optional[str] = None
    location: Optional[str] = None

    # Ollama configuration
    ollama_url: Optional[str] = None
    ollama_model: Optional[str] = None


def load_config(
    cli_backend: Optional[str] = None,
    cli_repo_path: Optional[str] = None,
    cli_checklist: Optional[str] = None,
    cli_gemini_key: Optional[str] = None,
    cli_gemini_model: Optional[str] = None,
    cli_ollama_url: Optional[str] = None,
    cli_ollama_model: Optional[str] = None,
    validate_checklist: bool = True,
) -> AppConfig:
    """
    Load configuration from environment variables and CLI overrides.

    Validates that either Gemini (GEMINI_KEY + GEMINI_MODEL) or
    Ollama (OLLAMA_URL + OLLAMA_MODEL) is properly configured.
    """
    # 1. Resolve Codebase / Repo Path
    repo_raw = (
        cli_repo_path
        or os.environ.get("REPO_PATH")
        or "."
    )
    repo_path = Path(repo_raw).resolve()
    if not repo_path.exists():
        raise ConfigurationError(f"Repository directory does not exist: {repo_path}")

    # 2. Resolve Checklist Path
    checklist_raw = (
        cli_checklist
        or os.environ.get("REPO_CHECKLIST")
    )
    if checklist_raw:
        checklist_path = Path(checklist_raw).resolve()
    else:
        # Check repo_path/.checklist first, then cwd/.checklist
        local_repo_checklist = repo_path / ".checklist"
        cwd_checklist = Path.cwd() / ".checklist"
        if local_repo_checklist.exists():
            checklist_path = local_repo_checklist.resolve()
        elif cwd_checklist.exists():
            checklist_path = cwd_checklist.resolve()
        else:
            checklist_path = local_repo_checklist.resolve()

    if validate_checklist and not checklist_path.is_file():
        raise ConfigurationError(
            f"Checklist file not found at '{checklist_path}'.\n"
            "Please create a '.checklist' file or set the path using the "
            "'REPO_CHECKLIST' environment variable or '--checklist' option."
        )

    # 3. Resolve Gemini credentials
    gemini_key = (
        cli_gemini_key
        or os.environ.get("GEMINI_KEY")
        or os.environ.get("GEMINI_API_KEY")
    )
    gemini_model = (
        cli_gemini_model
        or os.environ.get("GEMINI_MODEL")
    )
    vertexai = os.environ.get("VERTEXAI", "").lower() in ("1", "true", "yes")
    project = os.environ.get("GOOGLE_CLOUD_PROJECT") or os.environ.get("PROJECT_ID")
    location = os.environ.get("GOOGLE_CLOUD_LOCATION") or os.environ.get("LOCATION")

    # 4. Resolve Ollama configuration
    ollama_url = (
        cli_ollama_url
        or os.environ.get("OLLAMA_URL")
    )
    ollama_model = (
        cli_ollama_model
        or os.environ.get("OLLAMA_MODEL")
    )

    has_gemini = bool(gemini_key and gemini_model)
    has_ollama = bool(ollama_url and ollama_model)

    # 5. Determine Backend
    backend = (cli_backend or os.environ.get("BACKEND") or "").lower()

    if backend == "gemini":
        if not has_gemini:
            missing = []
            if not gemini_key:
                missing.append("GEMINI_KEY")
            if not gemini_model:
                missing.append("GEMINI_MODEL")
            raise ConfigurationError(
                f"Gemini backend selected, but missing required variable(s): {', '.join(missing)}."
            )
        backend_type = "gemini"
    elif backend == "ollama":
        if not has_ollama:
            missing = []
            if not ollama_url:
                missing.append("OLLAMA_URL")
            if not ollama_model:
                missing.append("OLLAMA_MODEL")
            raise ConfigurationError(
                f"Ollama backend selected, but missing required variable(s): {', '.join(missing)}."
            )
        backend_type = "ollama"
    else:
        # Automatic detection
        if has_gemini and has_ollama:
            # Both configured; default to Gemini
            backend_type = "gemini"
        elif has_gemini:
            backend_type = "gemini"
        elif has_ollama:
            backend_type = "ollama"
        else:
            # Neither is fully configured
            details = []
            if gemini_key and not gemini_model:
                details.append("GEMINI_KEY was provided, but GEMINI_MODEL is missing.")
            elif gemini_model and not gemini_key:
                details.append("GEMINI_MODEL was provided, but GEMINI_KEY is missing.")

            if ollama_url and not ollama_model:
                details.append("OLLAMA_URL was provided, but OLLAMA_MODEL is missing.")
            elif ollama_model and not ollama_url:
                details.append("OLLAMA_MODEL was provided, but OLLAMA_URL is missing.")

            error_msg = (
                "Missing LLM backend configuration.\n"
                "You must provide either:\n"
                "  1. Vertex AI / Gemini: GEMINI_KEY and GEMINI_MODEL\n"
                "  2. Ollama:             OLLAMA_URL and OLLAMA_MODEL\n"
            )
            if details:
                error_msg += "\nDetected partial configuration:\n  " + "\n  ".join(details)

            raise ConfigurationError(error_msg)

    return AppConfig(
        backend_type=backend_type,
        repo_path=repo_path,
        checklist_path=checklist_path,
        gemini_key=gemini_key,
        gemini_model=gemini_model,
        vertexai=vertexai,
        project=project,
        location=location,
        ollama_url=ollama_url,
        ollama_model=ollama_model,
    )
