"""LLM-backed steps: file triage, repo selection, structured explanation.

Every step goes through llm.complete(), which dispatches to the chosen backend
(Claude Code CLI or the Anthropic API). The `backend` argument is threaded
through from the web request so the user can pick per run.

The overview/follow-up steps return STRUCTURED data: a summary, a Mermaid
diagram, and "sections" that each reference real line ranges in real files. We
slice the actual code out of the cached file contents (rather than trusting the
model to reproduce it), so the snippets shown are guaranteed faithful.
"""

import json
import re

import llm
import prompts


# Directories / files that are vendored deps, build output, or binary noise.
_NOISE_DIRS = (
    ".venv/", "venv/", "env/", "node_modules/", "__pycache__/", ".git/",
    "dist/", "build/", ".next/", ".nuxt/", "vendor/", "site-packages/",
    ".tox/", ".mypy_cache/", ".pytest_cache/", "target/", "bin/", "obj/",
    ".idea/", ".vscode/", "coverage/", ".gradle/",
)
_NOISE_EXT = (
    ".pyc", ".pyo", ".so", ".dll", ".dylib", ".class", ".o", ".a",
    ".lock", ".min.js", ".min.css", ".map", ".png", ".jpg", ".jpeg",
    ".gif", ".svg", ".ico", ".pdf", ".zip", ".gz", ".tar", ".woff",
    ".woff2", ".ttf", ".eot", ".mp4", ".mp3", ".wasm",
)


def filter_source_files(paths):
    """Drop vendored deps, build artifacts, and binaries so triage sees real code."""
    keep = []
    for p in paths:
        lower = p.lower()
        if any(seg in lower for seg in _NOISE_DIRS):
            continue
        if lower.endswith(_NOISE_EXT):
            continue
        keep.append(p)
    return keep


def _extract_json(text):
    """Pull the first JSON array/object out of a model response."""
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()
    m = re.search(r"(\{.*\}|\[.*\])", text, re.DOTALL)
    return json.loads(m.group(1) if m else text)


def _numbered(content):
    """Prefix each line with a 1-indexed number for accurate ref ranges."""
    lines = content.splitlines()
    return "\n".join(f"{i}| {ln}" for i, ln in enumerate(lines, 1))


def _slice(content, start, end):
    """Return the real code for an inclusive 1-indexed [start, end] range."""
    lines = content.splitlines()
    start = max(1, int(start))
    end = min(len(lines), int(end))
    if end < start:
        end = start
    return "\n".join(lines[start - 1:end])


def _attach_code(refs, files):
    """Turn model refs ({path,start,end}) into snippets with real code."""
    out = []
    for ref in refs or []:
        path = ref.get("path")
        if path not in files:
            continue
        start = ref.get("start", 1)
        end = ref.get("end", start)
        code = _slice(files[path], start, end)
        if not code.strip():
            continue
        out.append(
            {"path": path, "start": int(start), "end": int(end), "code": code}
        )
    return out


def _files_block(files):
    parts = []
    for path, content in files.items():
        parts.append(f"=== {path} ===\n{_numbered(content[:12000])}\n")
    return "\n".join(parts)


# ---- LLM steps -------------------------------------------------------------

def select_best_repo(candidates, concept, backend=None):
    listing = "\n".join(
        f"- {c['name']} ({c['stars']}★, {c['language']}): {c['description']}"
        for c in candidates
    )
    out = llm.complete(
        system=prompts.SELECT_REPO_SYSTEM,
        user=f"Concept: {concept}\n\nCandidates:\n{listing}",
        max_tokens=300,
        backend=backend,
    )
    return _extract_json(out)


def triage_files(file_tree, topic=None, exclude=None, backend=None):
    """Ask the LLM which files matter. `exclude` skips already-read files."""
    exclude = set(exclude or [])
    available = [p for p in filter_source_files(file_tree) if p not in exclude]
    if not available:
        available = [p for p in file_tree if p not in exclude]
    tree_text = "\n".join(available[:1500])
    topic_line = f"\nTopic of interest: {topic}" if topic else ""
    out = llm.complete(
        system=prompts.TRIAGE_SYSTEM,
        user=f"File tree:\n{tree_text}{topic_line}",
        max_tokens=600,
        backend=backend,
    )
    picked = _extract_json(out)
    valid = set(file_tree)
    return [p for p in picked if p in valid]


def generate_overview(repo_name, file_tree, files, topic=None, backend=None):
    """Return {summary, mermaid, sections:[{title, explanation, snippets}]}."""
    head = [f"Repository: {repo_name}", f"Total files: {len(file_tree)}"]
    if topic:
        head.append(f"The user specifically wants to understand: {topic}")
    user = "\n".join(head) + "\n\nSelected file contents:\n" + _files_block(files)

    raw = llm.complete(
        system=prompts.overview_system(),
        user=user,
        max_tokens=3500,
        backend=backend,
    )
    data = _extract_json(raw)
    sections = []
    for sec in data.get("sections", []):
        sections.append(
            {
                "title": sec.get("title", "Untitled"),
                "explanation": sec.get("explanation", ""),
                "snippets": _attach_code(sec.get("refs"), files),
            }
        )
    return {
        "summary": data.get("summary", ""),
        "mermaid": (data.get("mermaid") or "").strip(),
        "sections": sections,
    }


def answer_followup(repo_name, file_tree, files, question, history=None, backend=None):
    """Return {answer, mermaid, snippets} for a chat-style follow-up."""
    convo = ""
    if history:
        turns = []
        for h in history[-6:]:
            turns.append(f"{h['role'].upper()}: {h['content']}")
        convo = "Prior conversation:\n" + "\n".join(turns) + "\n\n"

    user = (
        f"Repository: {repo_name}\n\n{convo}"
        f"New question: {question}\n\nRelevant file contents:\n"
        + _files_block(files)
    )
    raw = llm.complete(
        system=prompts.followup_system(),
        user=user,
        max_tokens=3000,
        backend=backend,
    )
    data = _extract_json(raw)
    return {
        "answer": data.get("answer", ""),
        "mermaid": (data.get("mermaid") or "").strip(),
        "snippets": _attach_code(data.get("refs"), files),
    }