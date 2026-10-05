"""Tests for repository and Git context extraction."""

from pathlib import Path
import subprocess

from review_app.context import (
    gather_codebase_context,
    get_file_tree,
    get_git_context,
    get_repository_files_content,
    read_text_file,
)


def test_get_file_tree_ignores_directories(tmp_path):
    """Ensure ignored directories are omitted from the file tree."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("print('hello')")
    (tmp_path / "README.md").write_text("# Test")

    # Ignored directories
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "config").write_text("git config")
    (tmp_path / "__pycache__").mkdir()
    (tmp_path / "__pycache__" / "main.cpython-312.pyc").write_text("cache")
    (tmp_path / ".venv").mkdir()
    (tmp_path / ".venv" / "bin").mkdir()
    (tmp_path / ".venv" / "bin" / "python").write_text("binary")

    tree = get_file_tree(tmp_path)

    assert "README.md" in tree
    assert "src/main.py" in tree
    assert not any(f.startswith(".git") for f in tree)
    assert not any(f.startswith("__pycache__") for f in tree)
    assert not any(f.startswith(".venv") for f in tree)


def test_read_text_file_truncation(tmp_path):
    """Ensure large text files are properly truncated."""
    large_file = tmp_path / "large.txt"
    large_file.write_text("A" * 1000)

    content = read_text_file(large_file, max_bytes=100)
    assert len(content) < 1000
    assert "[Truncated after 100 bytes]" in content


def test_gather_codebase_context(tmp_path):
    """Test full context collection for a repo."""
    checklist = tmp_path / ".checklist"
    checklist.write_text("1. Ensure README exists\n2. Ensure tests exist")

    readme = tmp_path / "README.md"
    readme.write_text("# My Awesome Project")

    ctx = gather_codebase_context(tmp_path, checklist)

    assert "Ensure README exists" in ctx["checklist"]
    assert "README.md" in ctx["file_tree"]
    assert "# My Awesome Project" in ctx["files_content"]
    assert "git_context" in ctx
