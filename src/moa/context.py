"""Project context detection and injection for MoA queries.

Auto-detects project type, reads key files, and builds a context summary
that gets prepended to queries for richer, project-aware responses.
"""

import os
from pathlib import Path
from typing import Optional, List, Tuple

# ── Project type markers ───────────────────────────────────────────────────────

PROJECT_MARKERS = {
    "python": ["pyproject.toml", "setup.py", "setup.cfg", "requirements.txt", "Pipfile"],
    "node": ["package.json", "tsconfig.json"],
    "rust": ["Cargo.toml"],
    "go": ["go.mod"],
    "ruby": ["Gemfile"],
    "java": ["pom.xml", "build.gradle", "build.gradle.kts"],
    "dotnet": ["*.csproj", "*.sln"],
    "swift": ["Package.swift", "*.xcodeproj"],
}

# Files to always read if they exist (in priority order)
KEY_FILES = [
    "README.md",
    "README.rst",
    "README",
    "pyproject.toml",
    "package.json",
    "Cargo.toml",
    "go.mod",
    "docker-compose.yml",
    "Dockerfile",
    ".env.example",
]

# Files relevant to specific directories
DIR_KEY_FILES = [
    "__init__.py",
    "index.ts",
    "index.js",
    "mod.rs",
    "main.go",
]

# Max bytes to read from any single file
MAX_FILE_BYTES = 4_000

# Max total context characters
MAX_CONTEXT_CHARS = 12_000


def detect_project_type(root: Path) -> str:
    """Detect the project type from marker files."""
    for ptype, markers in PROJECT_MARKERS.items():
        for marker in markers:
            if "*" in marker:
                # Glob pattern
                if list(root.glob(marker)):
                    return ptype
            elif (root / marker).exists():
                return ptype
    return "unknown"


def get_directory_tree(root: Path, max_depth: int = 3, max_items: int = 80) -> str:
    """Build a directory tree string, respecting depth and item limits."""
    lines = []
    count = 0

    # Common dirs/files to always skip
    skip = {
        ".git", "__pycache__", "node_modules", ".venv", "venv", ".env",
        ".mypy_cache", ".pytest_cache", ".ruff_cache", "dist", "build",
        ".next", ".nuxt", "target", ".tox", "egg-info", ".eggs",
        ".idea", ".vscode", ".DS_Store",
    }

    def _walk(path: Path, prefix: str, depth: int):
        nonlocal count
        if depth > max_depth or count >= max_items:
            return

        try:
            entries = sorted(path.iterdir(), key=lambda e: (not e.is_dir(), e.name.lower()))
        except PermissionError:
            return

        dirs = [e for e in entries if e.is_dir() and e.name not in skip and not e.name.startswith(".")]
        files = [e for e in entries if e.is_file() and e.name not in skip]

        for d in dirs:
            if count >= max_items:
                lines.append(f"{prefix}... (truncated)")
                return
            lines.append(f"{prefix}{d.name}/")
            count += 1
            _walk(d, prefix + "  ", depth + 1)

        for f in files:
            if count >= max_items:
                lines.append(f"{prefix}... (truncated)")
                return
            size = f.stat().st_size
            if size < 1024:
                size_str = f"{size}B"
            elif size < 1024 * 1024:
                size_str = f"{size // 1024}KB"
            else:
                size_str = f"{size // (1024*1024)}MB"
            lines.append(f"{prefix}{f.name} ({size_str})")
            count += 1

    _walk(root, "", 0)
    return "\n".join(lines)


def read_file_safe(path: Path, max_bytes: int = MAX_FILE_BYTES) -> Optional[str]:
    """Read a file safely, truncating at max_bytes."""
    try:
        content = path.read_text(encoding="utf-8", errors="replace")
        if len(content) > max_bytes:
            return content[:max_bytes] + f"\n... (truncated at {max_bytes} bytes)"
        return content
    except (PermissionError, OSError, UnicodeDecodeError):
        return None


def read_key_files(root: Path) -> List[Tuple[str, str]]:
    """Read key project files, returning (filename, content) pairs."""
    found = []
    total_chars = 0

    for name in KEY_FILES:
        path = root / name
        if path.exists() and path.is_file():
            content = read_file_safe(path)
            if content and total_chars + len(content) < MAX_CONTEXT_CHARS:
                found.append((name, content))
                total_chars += len(content)

    return found


def read_dir_context(target: Path) -> List[Tuple[str, str]]:
    """Read key files from a specific directory."""
    found = []
    total_chars = 0

    # Read all .py / .ts / .js / .rs / .go files in the target dir (not recursive)
    code_extensions = {".py", ".ts", ".js", ".rs", ".go", ".java", ".rb", ".swift"}

    try:
        files = sorted(target.iterdir(), key=lambda f: f.name)
    except PermissionError:
        return found

    for f in files:
        if f.is_file() and f.suffix in code_extensions:
            content = read_file_safe(f)
            if content and total_chars + len(content) < MAX_CONTEXT_CHARS:
                rel = f.relative_to(target.parent) if target.parent != target else f.name
                found.append((str(rel), content))
                total_chars += len(content)

    return found


def build_context(path: str = ".") -> str:
    """Build a project context summary for injection into MoA queries.

    Args:
        path: Path to project root or specific directory/file

    Returns:
        Formatted context string ready to prepend to a query
    """
    target = Path(path).resolve()

    if not target.exists():
        return f"[Context: path '{path}' not found]"

    # ── Single file ────────────────────────────────────────────────────────
    if target.is_file():
        content = read_file_safe(target, max_bytes=MAX_CONTEXT_CHARS)
        if not content:
            return f"[Context: could not read '{target.name}']"
        return (
            f"[PROJECT CONTEXT]\n"
            f"File: {target.name}\n"
            f"```\n{content}\n```\n"
            f"[/PROJECT CONTEXT]\n"
        )

    # ── Directory ──────────────────────────────────────────────────────────
    # Find project root (walk up to find marker files)
    project_root = target
    for parent in [target] + list(target.parents):
        for markers in PROJECT_MARKERS.values():
            for marker in markers:
                if "*" not in marker and (parent / marker).exists():
                    project_root = parent
                    break

    project_type = detect_project_type(project_root)
    project_name = project_root.name

    parts = [
        f"[PROJECT CONTEXT]",
        f"Project: {project_name}",
        f"Type: {project_type}",
        f"Root: {project_root}",
        "",
        "Directory structure:",
        "```",
        get_directory_tree(project_root),
        "```",
    ]

    # Read key files from project root
    key_files = read_key_files(project_root)

    # If target is a subdirectory, also read files from there
    if target != project_root and target.is_dir():
        dir_files = read_dir_context(target)
        if dir_files:
            parts.append(f"\nTarget directory: {target.relative_to(project_root)}/")
        key_files.extend(dir_files)

    # Append file contents
    for name, content in key_files:
        parts.extend([
            f"\n--- {name} ---",
            f"```",
            content,
            f"```",
        ])

    parts.append("[/PROJECT CONTEXT]\n")

    result = "\n".join(parts)

    # Final truncation safety
    if len(result) > MAX_CONTEXT_CHARS:
        result = result[:MAX_CONTEXT_CHARS] + "\n... (context truncated)\n[/PROJECT CONTEXT]\n"

    return result
