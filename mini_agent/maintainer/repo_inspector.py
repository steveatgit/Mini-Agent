"""Repository scanning and issue context selection helpers."""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path
from typing import Any


SKIP_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".tox",
    ".venv",
    "__pycache__",
    "node_modules",
    "dist",
    "build",
    ".pytest_cache",
}

LANGUAGE_BY_EXT = {
    ".py": "Python",
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".go": "Go",
    ".rs": "Rust",
    ".java": "Java",
    ".kt": "Kotlin",
    ".rb": "Ruby",
    ".php": "PHP",
}

KEY_FILES = {
    "pyproject.toml",
    "setup.py",
    "requirements.txt",
    "package.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    "Cargo.toml",
    "go.mod",
    "README.md",
    "README_CN.md",
}


def ensure_repo(repo_path: Path) -> Path:
    repo = repo_path.expanduser().resolve()
    if not repo.exists() or not repo.is_dir():
        raise ValueError(f"Repository path does not exist or is not a directory: {repo}")
    result = subprocess.run(["git", "-C", str(repo), "rev-parse", "--is-inside-work-tree"], capture_output=True, text=True)
    if result.returncode != 0 or result.stdout.strip() != "true":
        raise ValueError(f"Repository path is not inside a git work tree: {repo}")
    return repo


def git_status(repo_path: Path) -> str:
    return _run_git(repo_path, ["status", "--short"])


def git_diff(repo_path: Path) -> str:
    return _run_git(repo_path, ["diff", "--binary"])


def changed_files(repo_path: Path) -> list[str]:
    status = git_status(repo_path)
    files = []
    for line in status.splitlines():
        item = line[3:].strip()
        if " -> " in item:
            item = item.split(" -> ", 1)[1]
        if item:
            files.append(item)
    return files


def create_patch(repo_path: Path) -> str:
    return _run_git(repo_path, ["diff", "--binary", "--patch"])


def scan_repo(repo_path: Path, max_files: int = 240) -> dict[str, Any]:
    files = list_repo_files(repo_path, max_files=max_files)
    language_counts: dict[str, int] = {}
    key_files = []
    test_files = []

    for file_path in files:
        name = Path(file_path).name
        ext = Path(file_path).suffix
        language = LANGUAGE_BY_EXT.get(ext)
        if language:
            language_counts[language] = language_counts.get(language, 0) + 1
        if name in KEY_FILES:
            key_files.append(file_path)
        if _looks_like_test(file_path):
            test_files.append(file_path)

    return {
        "repo_path": str(repo_path),
        "git_status": git_status(repo_path),
        "languages": language_counts,
        "key_files": key_files[:40],
        "test_files": test_files[:80],
        "files": files,
        "detected_test_command": detect_test_command(repo_path, files),
    }


def list_repo_files(repo_path: Path, max_files: int = 240) -> list[str]:
    result = subprocess.run(["git", "-C", str(repo_path), "ls-files"], capture_output=True, text=True)
    if result.returncode == 0 and result.stdout.strip():
        files = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    else:
        files = []
        for root, dirs, names in os.walk(repo_path):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
            for name in names:
                path = Path(root) / name
                files.append(str(path.relative_to(repo_path)))
    return files[:max_files]


def detect_test_command(repo_path: Path, files: list[str]) -> str | None:
    file_set = set(files)
    if "pyproject.toml" in file_set or "pytest.ini" in file_set or any(path.startswith("tests/") for path in files):
        return "pytest"
    if "package.json" in file_set:
        package_json = repo_path / "package.json"
        try:
            content = package_json.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            content = package_json.read_text(encoding="utf-8", errors="replace")
        if '"test"' in content:
            return "npm test"
    if "Cargo.toml" in file_set:
        return "cargo test"
    if "go.mod" in file_set:
        return "go test ./..."
    return None


def triage_issue(issue_text: str, repo_map: dict[str, Any]) -> dict[str, Any]:
    text = issue_text.strip()
    lowered = text.lower()
    issue_type = "bug" if any(word in lowered for word in ("bug", "error", "fail", "失败", "报错")) else "task"
    keywords = _issue_keywords(text)
    suspected = select_context_files(issue_text, repo_map, max_files=8)
    return {
        "type": issue_type,
        "summary": text.splitlines()[0][:180] if text else "",
        "keywords": keywords,
        "suspected_files": suspected,
        "acceptance_criteria": _acceptance_criteria(text),
    }


def select_context_files(issue_text: str, repo_map: dict[str, Any], max_files: int = 8) -> list[str]:
    keywords = set(_issue_keywords(issue_text))
    scored: list[tuple[int, str]] = []
    for file_path in repo_map.get("files", []):
        path_lower = file_path.lower()
        score = 0
        for keyword in keywords:
            if keyword and keyword in path_lower:
                score += 3
        if Path(file_path).name in {"README.md", "pyproject.toml", "package.json"}:
            score += 1
        if _looks_like_test(file_path):
            score += 1
        if score:
            scored.append((score, file_path))
    scored.sort(key=lambda item: (-item[0], item[1]))
    selected = [file_path for _, file_path in scored[:max_files]]
    if not selected:
        selected = list(repo_map.get("key_files", []))[:max_files]
    return selected


def render_repo_map(repo_map: dict[str, Any]) -> str:
    lines = [
        "# Repo Map",
        "",
        f"- repo_path: {repo_map.get('repo_path', '')}",
        f"- detected_test_command: {repo_map.get('detected_test_command') or 'unknown'}",
        "",
        "## Git Status",
        "```text",
        repo_map.get("git_status", "") or "(clean)",
        "```",
        "",
        "## Languages",
    ]
    languages = repo_map.get("languages", {})
    if languages:
        lines.extend(f"- {name}: {count}" for name, count in sorted(languages.items()))
    else:
        lines.append("- unknown")
    lines.extend(["", "## Key Files"])
    key_files = repo_map.get("key_files", [])
    if key_files:
        lines.extend(f"- {path}" for path in key_files)
    else:
        lines.append("- none")
    lines.extend(["", "## Test Files"])
    test_files = repo_map.get("test_files", [])[:40]
    if test_files:
        lines.extend(f"- {path}" for path in test_files)
    else:
        lines.append("- none")
    return "\n".join(lines) + "\n"


def render_selected_context(repo_path: Path, selected_files: list[str], max_chars_per_file: int = 4000) -> str:
    lines = ["# Selected Context", ""]
    for rel_path in selected_files:
        path = (repo_path / rel_path).resolve()
        if not _is_relative_to(path, repo_path):
            continue
        lines.extend([f"## {rel_path}", "```text"])
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            content = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            content = f"[could not read file: {exc}]"
        if len(content) > max_chars_per_file:
            content = content[:max_chars_per_file] + "\n...[truncated]"
        lines.extend([content, "```", ""])
    return "\n".join(lines)


def _run_git(repo_path: Path, args: list[str]) -> str:
    result = subprocess.run(["git", "-C", str(repo_path), *args], capture_output=True, text=True)
    if result.returncode != 0:
        return result.stderr.strip()
    return result.stdout.strip()


def _issue_keywords(issue_text: str) -> list[str]:
    words = re.findall(r"[A-Za-z_][A-Za-z0-9_]{2,}|[\u4e00-\u9fff]{2,}", issue_text.lower())
    stopwords = {"the", "and", "for", "with", "this", "that", "when", "should", "issue", "bug", "error"}
    return list(dict.fromkeys(word for word in words if word not in stopwords))[:20]


def _acceptance_criteria(issue_text: str) -> list[str]:
    criteria = []
    for line in issue_text.splitlines():
        stripped = line.strip(" -\t")
        if any(marker in stripped.lower() for marker in ("expect", "should", "期望", "验收")):
            criteria.append(stripped[:240])
    return criteria[:8]


def _looks_like_test(file_path: str) -> bool:
    path = file_path.lower()
    name = Path(path).name
    return path.startswith("tests/") or name.startswith("test_") or name.endswith(("_test.py", ".test.js", ".spec.js", ".test.ts", ".spec.ts"))


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False
