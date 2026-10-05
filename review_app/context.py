"""Codebase and Git context collector."""

import os
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple


IGNORED_DIRECTORIES: Set[str] = {
    ".git",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "node_modules",
    ".venv",
    "venv",
    ".idea",
    ".vscode",
    "dist",
    "build",
    ".eggs",
    ".tox",
}

BINARY_EXTENSIONS: Set[str] = {
    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".svg",
    ".pdf", ".zip", ".tar", ".gz", ".bz2", ".7z",
    ".pyc", ".pyo", ".pyd", ".so", ".dll", ".dylib",
    ".exe", ".bin", ".woff", ".woff2", ".ttf", ".eot"
}


def run_git_command(repo_path: Path, args: List[str]) -> Tuple[int, str]:
    """Execute a git command inside the given repository directory."""
    try:
        res = subprocess.run(
            ["git"] + args,
            cwd=str(repo_path),
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        return res.returncode, res.stdout.strip()
    except Exception as e:
        return 1, f"Error running git command: {e}"


def get_git_context(repo_path: Path, max_commits: int = 50) -> str:
    """Extract git commit history, branch, and status from repository."""
    code, is_git = run_git_command(repo_path, ["rev-parse", "--is-inside-work-tree"])
    if code != 0 or is_git.strip() != "true":
        return "Note: Repository is not a Git repository or Git is not installed."

    lines: List[str] = ["### Git Repository Context"]

    # Branch
    _, branch = run_git_command(repo_path, ["branch", "--show-current"])
    if branch:
        lines.append(f"Current Branch: {branch}")

    # Status
    _, status = run_git_command(repo_path, ["status", "--short"])
    if status:
        lines.append("\nWorking Tree Status:")
        lines.append(status)
    else:
        lines.append("\nWorking Tree Status: clean")

    # Commit History with full author, committer, and commit message
    fmt = "Commit: %H%nAuthor: %an <%ae>%nAuthorDate: %ad%nCommit: %cn <%ce>%nCommitDate: %cd%nSubject: %s%nBody: %b%n"
    code, log_output = run_git_command(
        repo_path,
        ["log", f"-n{max_commits}", f"--format={fmt}"]
    )
    if code == 0 and log_output:
        lines.append(f"\nRecent Git Commits (Up to {max_commits}):\n")
        lines.append(log_output)
    else:
        lines.append("\nRecent Git Commits: (No commits found)")

    return "\n".join(lines)


def get_file_tree(repo_path: Path) -> List[str]:
    """Return a relative file tree of the repository, excluding ignored folders."""
    file_list: List[str] = []
    for root, dirs, files in os.walk(repo_path):
        # Filter directories in-place to avoid descending into ignored folders
        dirs[:] = [d for d in dirs if d not in IGNORED_DIRECTORIES and not d.startswith(".venv")]
        rel_root = Path(root).relative_to(repo_path)
        for f in files:
            rel_path = (rel_root / f).as_posix() if str(rel_root) != "." else f
            file_list.append(rel_path)

    file_list.sort()
    return file_list


def read_text_file(file_path: Path, max_bytes: int = 40_000) -> Optional[str]:
    """Read a text file, handling encoding and size limits."""
    try:
        if file_path.stat().st_size > max_bytes:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read(max_bytes)
            return content + f"\n... [Truncated after {max_bytes} bytes]"
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    except Exception:
        return None


def get_repository_files_content(
    repo_path: Path,
    file_tree: List[str],
    max_total_bytes: int = 300_000,
    max_file_bytes: int = 40_000,
) -> str:
    """
    Read contents of repository files up to total size budget.
    Prioritizes documentation, configuration, and source files.
    """
    # Priority order for file inspection
    priority_patterns = [
        "README", "readme", "SETUP", "setup", "Dockerfile", "docker-compose",
        "requirements", "package.json", "go.mod", "Cargo.toml", ".checklist"
    ]

    def sort_key(path_str: str) -> Tuple[int, str]:
        p = path_str.lower()
        for idx, pattern in enumerate(priority_patterns):
            if pattern.lower() in p:
                return (idx, path_str)
        return (len(priority_patterns), path_str)

    sorted_files = sorted(file_tree, key=sort_key)

    lines: List[str] = ["### Codebase Files Content"]
    total_bytes = 0

    for rel_file in sorted_files:
        ext = Path(rel_file).suffix.lower()
        if ext in BINARY_EXTENSIONS:
            continue

        full_path = repo_path / rel_file
        if not full_path.is_file():
            continue

        content = read_text_file(full_path, max_bytes=max_file_bytes)
        if content is None:
            continue

        file_len = len(content.encode("utf-8", errors="replace"))
        if total_bytes + file_len > max_total_bytes:
            lines.append(f"\n[Additional files omitted to keep context within limits]")
            break

        total_bytes += file_len
        lines.append(f"\n--- File: {rel_file} ---")
        lines.append(content)

    return "\n".join(lines)


def gather_codebase_context(
    repo_path: Path,
    checklist_path: Path,
) -> Dict[str, str]:
    """Gather git context, file tree, file contents, and checklist text."""
    # Read checklist
    with open(checklist_path, "r", encoding="utf-8", errors="replace") as f:
        checklist_content = f.read()

    # Git context
    git_context = get_git_context(repo_path)

    # File tree
    file_tree = get_file_tree(repo_path)
    file_tree_str = "### Repository File Tree\n" + "\n".join(f"- {f}" for f in file_tree)

    # File contents
    files_content = get_repository_files_content(repo_path, file_tree)

    return {
        "checklist": checklist_content,
        "git_context": git_context,
        "file_tree": file_tree_str,
        "files_content": files_content,
    }
