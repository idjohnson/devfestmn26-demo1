"""Command-line interface for Review App."""

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

from review_app.backends.base import BackendError
from review_app.config import ConfigurationError, load_config
from review_app.models import ReviewReport, ReviewStatus
from review_app.reviewer import run_review

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text
    HAS_RICH = True
except ImportError:
    HAS_RICH = False


def format_report_markdown(report: ReviewReport) -> str:
    """Format report as Markdown document."""
    lines = [
        f"# Repository Checklist Review Report",
        f"",
        f"- **Repository:** `{report.repository}`",
        f"- **Checklist:** `{report.checklist_path}`",
        f"- **Backend:** {report.backend} ({report.model})",
        f"- **Date/Time:** {report.timestamp}",
        f"- **Overall Status:** **{report.summary.status}**",
        f"",
        f"## Summary",
        f"",
        f"| Metric | Count |",
        f"| :--- | :--- |",
        f"| Total Rules | {report.summary.total} |",
        f"| Passed | {report.summary.passed} |",
        f"| Failed | {report.summary.failed} |",
        f"| Warnings | {report.summary.warnings} |",
        f"",
        f"## Detailed Results",
        f"",
    ]

    for item in report.results:
        badge = "✅ PASS" if item.status == ReviewStatus.PASS else ("❌ FAIL" if item.status == ReviewStatus.FAIL else "⚠️ WARN")
        lines.append(f"### {item.index}. {item.rule}")
        lines.append(f"**Status:** {badge}\n")
        lines.append(f"**Evidence:**\n{item.evidence}\n")
        if item.remediation:
            lines.append(f"**Remediation:**\n{item.remediation}\n")
        lines.append("---")

    return "\n".join(lines)


def format_report_plain(report: ReviewReport) -> str:
    """Format report as plain text for simple terminal display."""
    lines = [
        "============================================================",
        "              REPOSITORY CHECKLIST REVIEW REPORT            ",
        "============================================================",
        f"Repository:     {report.repository}",
        f"Checklist:      {report.checklist_path}",
        f"Backend:        {report.backend} ({report.model})",
        f"Timestamp:      {report.timestamp}",
        f"Overall Status: {report.summary.status}",
        "------------------------------------------------------------",
        f"Summary: Total: {report.summary.total} | Passed: {report.summary.passed} | Failed: {report.summary.failed} | Warnings: {report.summary.warnings}",
        "============================================================",
    ]

    for item in report.results:
        status_label = f"[{item.status.value}]"
        lines.append(f"\nRule #{item.index}: {item.rule}")
        lines.append(f"Status:      {status_label}")
        lines.append(f"Evidence:    {item.evidence}")
        if item.remediation:
            lines.append(f"Remediation: {item.remediation}")
        lines.append("-" * 60)

    return "\n".join(lines)


def print_rich_report(report: ReviewReport) -> None:
    """Display the review report using Rich formatting."""
    console = Console()

    # Header Panel
    overall_color = "green" if report.summary.status == "PASSED" else "red"
    summary_text = (
        f"[bold]Repository:[/bold] {report.repository}\n"
        f"[bold]Checklist:[/bold]  {report.checklist_path}\n"
        f"[bold]Backend:[/bold]    {report.backend} ([cyan]{report.model}[/cyan])\n"
        f"[bold]Status:[/bold]     [{overall_color} bold]{report.summary.status}[/{overall_color} bold]"
    )
    console.print(Panel(summary_text, title="🔍 Codebase Checklist Review", border_style=overall_color))

    # Detailed Table
    table = Table(title="Rule Evaluation Details", show_lines=True)
    table.add_column("#", style="dim", width=4)
    table.add_column("Rule", style="bold", min_width=25)
    table.add_column("Status", justify="center", width=10)
    table.add_column("Findings & Evidence", min_width=35)
    table.add_column("Remediation", min_width=25)

    for r in report.results:
        if r.status == ReviewStatus.PASS:
            status_text = Text("PASS", style="bold green")
        elif r.status == ReviewStatus.FAIL:
            status_text = Text("FAIL", style="bold red")
        else:
            status_text = Text(r.status.value, style="bold yellow")

        table.add_row(
            str(r.index),
            r.rule,
            status_text,
            r.evidence,
            r.remediation or "[dim]N/A[/dim]",
        )

    console.print(table)

    # Footer metrics
    console.print(
        f"\n[bold]Summary:[/bold] "
        f"[green]{report.summary.passed} Passed[/green] | "
        f"[red]{report.summary.failed} Failed[/red] | "
        f"[yellow]{report.summary.warnings} Warnings[/yellow] | "
        f"[bold]{report.summary.total} Total Rules[/bold]\n"
    )


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Review a codebase and git history against a markdown checklist using Gemini or Ollama."
    )
    parser.add_argument(
        "--repo", "-r",
        dest="repo_path",
        help="Path to repository to review (or REPO_PATH env var, default: .)",
    )
    parser.add_argument(
        "--checklist", "-c",
        dest="checklist",
        help="Path to checklist file (or REPO_CHECKLIST env var, default: .checklist)",
    )
    parser.add_argument(
        "--backend",
        choices=["gemini", "ollama"],
        help="Explicitly choose backend (gemini or ollama)",
    )
    parser.add_argument(
        "--gemini-key",
        help="Gemini API Key (or GEMINI_KEY / GEMINI_API_KEY env var)",
    )
    parser.add_argument(
        "--gemini-model",
        help="Gemini Model (or GEMINI_MODEL env var, e.g. gemini-2.5-flash)",
    )
    parser.add_argument(
        "--ollama-url",
        help="Ollama URL (or OLLAMA_URL env var, e.g. http://localhost:11434)",
    )
    parser.add_argument(
        "--ollama-model",
        help="Ollama Model (or OLLAMA_MODEL env var, e.g. llama3)",
    )
    parser.add_argument(
        "--format", "-f",
        choices=["terminal", "plain", "markdown", "json"],
        default="terminal",
        help="Output format (default: terminal)",
    )
    parser.add_argument(
        "--output", "-o",
        help="Save report to specified file path",
    )
    parser.add_argument(
        "--no-fail-exit",
        action="store_true",
        help="Exit with 0 even if checklist rules failed",
    )

    args = parser.parse_args(argv)

    try:
        config = load_config(
            cli_backend=args.backend,
            cli_repo_path=args.repo_path,
            cli_checklist=args.checklist,
            cli_gemini_key=args.gemini_key,
            cli_gemini_model=args.gemini_model,
            cli_ollama_url=args.ollama_url,
            cli_ollama_model=args.ollama_model,
        )
    except ConfigurationError as ce:
        sys.stderr.write(f"\n[ERROR] Configuration failure:\n{ce}\n\n")
        return 2

    # Execute Review
    try:
        report = run_review(config)
    except BackendError as be:
        sys.stderr.write(f"\n[ERROR] LLM Backend failed:\n{be}\n\n")
        return 2
    except Exception as e:
        sys.stderr.write(f"\n[ERROR] Unexpected error during review:\n{e}\n\n")
        return 2

    # Render output
    if args.format == "json":
        output_str = report.model_dump_json(indent=2)
        print(output_str)
    elif args.format == "markdown":
        output_str = format_report_markdown(report)
        print(output_str)
    elif args.format == "plain" or not HAS_RICH:
        output_str = format_report_plain(report)
        print(output_str)
    else:
        # Default rich terminal display
        print_rich_report(report)
        output_str = format_report_markdown(report)

    # Save to file if requested
    if args.output:
        try:
            out_path = Path(args.output).resolve()
            out_path.parent.mkdir(parents=True, exist_ok=True)
            if args.output.endswith(".json"):
                content = report.model_dump_json(indent=2)
            elif args.output.endswith(".txt"):
                content = format_report_plain(report)
            else:
                content = format_report_markdown(report)
            out_path.write_text(content, encoding="utf-8")
            print(f"[INFO] Report written to: {out_path}")
        except Exception as e:
            sys.stderr.write(f"[WARN] Failed to write report to {args.output}: {e}\n")

    # Exit code determination
    if report.summary.status != "PASSED" and not args.no_fail_exit:
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
