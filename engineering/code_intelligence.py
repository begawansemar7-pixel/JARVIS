"""Lightweight repository intelligence for the JARVIS SWE agent."""
from __future__ import annotations

import ast
import re
from dataclasses import dataclass, asdict
from pathlib import Path

DEFAULT_EXCLUDES = {
    ".git", ".venv", "venv", "node_modules", "__pycache__", ".pytest_cache",
    "dist", "build", ".idea", ".vscode", "coverage", "target"
}
TEXT_SUFFIXES = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".java", ".go", ".rs", ".c", ".cpp",
    ".h", ".hpp", ".cs", ".rb", ".php", ".swift", ".kt", ".kts", ".md", ".json",
    ".yaml", ".yml", ".toml", ".ini", ".cfg", ".txt", ".sql", ".sh"
}

@dataclass
class FileInfo:
    path: str
    kind: str
    size: int
    symbols: list[str]
    imports: list[str]


def _safe_relative(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def _python_structure(text: str) -> tuple[list[str], list[str]]:
    symbols: list[str] = []
    imports: list[str] = []
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return symbols, imports
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            symbols.append(node.name)
        elif isinstance(node, ast.Import):
            imports.extend(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.append(node.module)
    return sorted(set(symbols)), sorted(set(imports))


def _generic_structure(text: str) -> tuple[list[str], list[str]]:
    symbols = re.findall(r"\b(?:function|class|def|fn|func|struct|interface)\s+([A-Za-z_$][\w$]*)", text)
    imports = re.findall(r"(?:import|from|require\()\s+[\"']?([@A-Za-z0-9_./:-]+)", text)
    return sorted(set(symbols)), sorted(set(imports))


def scan_repository(root: str | Path, max_files: int = 2500) -> list[FileInfo]:
    """Return a bounded structural inventory without executing repository code."""
    base = Path(root).expanduser().resolve()
    if not base.exists() or not base.is_dir():
        raise ValueError(f"Repository root does not exist: {base}")
    result: list[FileInfo] = []
    for path in base.rglob("*"):
        if len(result) >= max_files:
            break
        if not path.is_file() or any(part in DEFAULT_EXCLUDES for part in path.parts):
            continue
        try:
            rel = _safe_relative(base, path)
            size = path.stat().st_size
        except OSError:
            continue
        suffix = path.suffix.lower()
        if suffix not in TEXT_SUFFIXES:
            continue
        symbols: list[str] = []
        imports: list[str] = []
        if size <= 512_000:
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
                if suffix == ".py":
                    symbols, imports = _python_structure(text)
                else:
                    symbols, imports = _generic_structure(text)
            except OSError:
                pass
        kind = "test" if ("test" in path.name.lower() or "/tests/" in f"/{rel}") else "source"
        result.append(FileInfo(rel, kind, size, symbols, imports))
    return sorted(result, key=lambda x: x.path)


def rank_context(inventory: list[FileInfo], task: str, limit: int = 12) -> list[dict]:
    """Rank likely relevant files using deterministic lexical/structural signals."""
    terms = {t.lower() for t in re.findall(r"[A-Za-z0-9_]{3,}", task)}
    scored: list[tuple[float, FileInfo, list[str]]] = []
    for item in inventory:
        hay = " ".join([item.path, *item.symbols, *item.imports]).lower()
        score = 0.0
        reasons: list[str] = []
        for term in terms:
            if term in item.path.lower():
                score += 3.0
                reasons.append("path match")
            if any(term == s.lower() or term in s.lower() for s in item.symbols):
                score += 2.5
                reasons.append("symbol match")
            if term in hay and term not in item.path.lower():
                score += 0.75
        if item.kind == "test" and score:
            score += 0.5
            reasons.append("test file")
        if score:
            scored.append((score, item, sorted(set(reasons))))
    scored.sort(key=lambda x: (-x[0], x[1].path))
    return [{"path": x.path, "kind": x.kind, "score": round(x[0], 3), "reasons": x[2], "symbols": x[1].symbols, "imports": x[1].imports} for x in scored[:limit]]


def render_context(root: str | Path, task: str, limit: int = 8, max_chars_per_file: int = 6000) -> str:
    base = Path(root).expanduser().resolve()
    inventory = scan_repository(base)
    ranked = rank_context(inventory, task, limit=limit)
    chunks = [f"Repository: {base}", f"Task: {task}", "Relevant files:"]
    for item in ranked:
        chunks.append(f"\n--- {item['path']} | score={item['score']} | symbols={', '.join(item['symbols'][:12])} ---")
        try:
            text = (base / item["path"]).read_text(encoding="utf-8", errors="replace")
            chunks.append(text[:max_chars_per_file])
        except OSError as exc:
            chunks.append(f"[read failed: {exc}]")
    return "\n".join(chunks)


def inventory_json(root: str | Path) -> list[dict]:
    return [asdict(x) for x in scan_repository(root)]
