"""Data models for review results and reports."""

from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


class ReviewStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    WARN = "WARN"
    SKIP = "SKIP"


class RuleResult(BaseModel):
    """Result of evaluating a single checklist rule."""
    index: int = Field(description="1-based index of the rule")
    rule: str = Field(description="The checklist rule text")
    status: ReviewStatus = Field(description="PASS, FAIL, WARN, or SKIP")
    evidence: str = Field(description="Evidence and explanation for the evaluation")
    remediation: Optional[str] = Field(
        default=None,
        description="Suggested action or fix if the rule failed"
    )


class ReviewSummary(BaseModel):
    """Aggregate summary of the review."""
    total: int = 0
    passed: int = 0
    failed: int = 0
    warnings: int = 0
    skipped: int = 0
    status: str = "FAILED"  # "PASSED" or "FAILED"


class ReviewReport(BaseModel):
    """Complete review report."""
    repository: str
    checklist_path: str
    backend: str
    model: str
    timestamp: str
    summary: ReviewSummary
    results: List[RuleResult]
    raw_response: Optional[str] = None
