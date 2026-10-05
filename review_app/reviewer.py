"""Checklist reviewer and LLM evaluation engine."""

from datetime import datetime, timezone
import json
import re
from typing import Any, Dict, List, Optional

from review_app.backends.base import BaseBackend
from review_app.backends.gemini import GeminiBackend
from review_app.backends.ollama import OllamaBackend
from review_app.config import AppConfig
from review_app.context import gather_codebase_context
from review_app.models import ReviewReport, ReviewStatus, ReviewSummary, RuleResult


SYSTEM_PROMPT = """You are an automated code and repository quality auditor.
Your job is to strictly evaluate a checklist of rules against a provided codebase, which includes Git history, commit messages, committers, file tree, and file contents.

EVALUATION GUIDELINES:
1. Examine every single rule listed in the checklist.
2. For each rule, search the git history (commit hashes, authors, committers, subjects, bodies) and file contents.
3. Determine the status:
   - "PASS": The rule is completely satisfied by the repository and commits.
   - "FAIL": The rule is violated or not satisfied.
   - "WARN": The rule could not be definitively verified with the given context, or minor concerns exist.
4. Provide concrete evidence for your finding. Cite specific commit SHAs, file names, or missing patterns.
5. If status is "FAIL" or "WARN", provide clear remediation steps.
6. The overall summary status must be "PASSED" if all rules are PASS or WARN, and "FAILED" if any rule is FAIL.

OUTPUT FORMAT:
You MUST respond with valid JSON ONLY (no markdown fences, no conversational text before or after):
{
  "summary": {
    "total": <int>,
    "passed": <int>,
    "failed": <int>,
    "warnings": <int>,
    "status": "PASSED" | "FAILED"
  },
  "results": [
    {
      "index": 1,
      "rule": "<text of rule 1>",
      "status": "PASS" | "FAIL" | "WARN",
      "evidence": "<specific evidence from commits/files>",
      "remediation": "<steps to fix if failed, otherwise null>"
    }
  ]
}
"""


def build_user_prompt(context: Dict[str, str]) -> str:
    """Combine checklist and repository context into the review prompt."""
    return f"""Please review the following repository against this checklist.

## CHECKLIST TO EVALUATE
{context['checklist']}

============================================================
## REPOSITORY CONTEXT
============================================================

{context['git_context']}

============================================================

{context['file_tree']}

============================================================

{context['files_content']}

============================================================
Evaluate every checklist item now and return the JSON report according to instructions.
"""


def extract_json_from_text(text: str) -> Optional[Dict[str, Any]]:
    """Extract JSON object from string, handling code block fences if present."""
    text = text.strip()

    # Try direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try extracting inside ```json ... ``` or ``` ... ```
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if match:
        try:
            return json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            pass

    # Try finding outer { ... }
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            pass

    return None


def create_backend(config: AppConfig) -> BaseBackend:
    """Instantiate the configured backend."""
    if config.backend_type == "gemini":
        if not config.gemini_key or not config.gemini_model:
            raise ValueError("GEMINI_KEY and GEMINI_MODEL are required for Gemini backend.")
        return GeminiBackend(
            api_key=config.gemini_key,
            model=config.gemini_model,
            vertexai=config.vertexai,
            project=config.project,
            location=config.location,
        )
    elif config.backend_type == "ollama":
        if not config.ollama_url or not config.ollama_model:
            raise ValueError("OLLAMA_URL and OLLAMA_MODEL are required for Ollama backend.")
        return OllamaBackend(
            ollama_url=config.ollama_url,
            model=config.ollama_model,
        )
    else:
        raise ValueError(f"Unknown backend type: {config.backend_type}")


def parse_llm_response(
    raw_response: str,
    config: AppConfig,
    backend_name: str,
    model_name: str,
) -> ReviewReport:
    """Parse raw LLM response into a validated ReviewReport."""
    parsed_json = extract_json_from_text(raw_response)
    timestamp = datetime.now(timezone.utc).isoformat()

    if parsed_json and "results" in parsed_json:
        results: List[RuleResult] = []
        for idx, item in enumerate(parsed_json.get("results", []), start=1):
            status_str = str(item.get("status", "WARN")).upper()
            try:
                status = ReviewStatus(status_str)
            except ValueError:
                status = ReviewStatus.WARN

            results.append(
                RuleResult(
                    index=item.get("index", idx),
                    rule=item.get("rule", f"Rule #{idx}"),
                    status=status,
                    evidence=item.get("evidence", "No evidence provided."),
                    remediation=item.get("remediation"),
                )
            )

        passed = sum(1 for r in results if r.status == ReviewStatus.PASS)
        failed = sum(1 for r in results if r.status == ReviewStatus.FAIL)
        warnings = sum(1 for r in results if r.status == ReviewStatus.WARN)
        total = len(results)

        summary_data = parsed_json.get("summary", {})
        overall_status = summary_data.get(
            "status",
            "PASSED" if failed == 0 else "FAILED"
        )
        if failed > 0:
            overall_status = "FAILED"

        summary = ReviewSummary(
            total=total,
            passed=passed,
            failed=failed,
            warnings=warnings,
            status=overall_status,
        )

        return ReviewReport(
            repository=str(config.repo_path),
            checklist_path=str(config.checklist_path),
            backend=backend_name,
            model=model_name,
            timestamp=timestamp,
            summary=summary,
            results=results,
            raw_response=raw_response,
        )

    # Fallback if LLM output could not be parsed as structured JSON
    return ReviewReport(
        repository=str(config.repo_path),
        checklist_path=str(config.checklist_path),
        backend=backend_name,
        model=model_name,
        timestamp=timestamp,
        summary=ReviewSummary(
            total=1,
            passed=0,
            failed=1,
            warnings=0,
            status="FAILED",
        ),
        results=[
            RuleResult(
                index=1,
                rule="Checklist Evaluation",
                status=ReviewStatus.WARN,
                evidence=f"Model output could not be parsed as JSON. Raw response:\n{raw_response}",
                remediation="Check model prompt compatibility or backend parameters.",
            )
        ],
        raw_response=raw_response,
    )


def run_review(config: AppConfig, backend: Optional[BaseBackend] = None) -> ReviewReport:
    """Execute the full review process against the repository."""
    if backend is None:
        backend = create_backend(config)

    context = gather_codebase_context(
        repo_path=config.repo_path,
        checklist_path=config.checklist_path,
    )

    prompt = build_user_prompt(context)
    raw_response = backend.generate(prompt=prompt, system_prompt=SYSTEM_PROMPT)

    return parse_llm_response(
        raw_response=raw_response,
        config=config,
        backend_name=backend.name,
        model_name=backend.model,
    )
