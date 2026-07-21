"""LLM backend abstraction.

Two interchangeable backends so you can run this either way:

  - "claude_cli"  -> shells out to the `claude` Claude Code CLI. Uses your
                     existing Claude Code login/subscription. No API key needed.
  - "anthropic"   -> uses the Anthropic Python SDK (needs ANTHROPIC_API_KEY).

The default backend is picked by the LLM_BACKEND env var, falling back to
"claude_cli". Each request from the UI can also override the backend.
"""

import json
import os
import shutil
import subprocess

DEFAULT_BACKEND = os.environ.get("LLM_BACKEND", "claude_cli")

# Path to the `claude` executable. Falls back to whatever is on PATH.
# Set CLAUDE_BIN to point at a bundled binary (e.g. the VS Code extension's).
CLAUDE_BIN = os.environ.get("CLAUDE_BIN") or "claude"

# Model defaults per backend (overridable via env).
ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5")
CLI_MODEL = os.environ.get("CLAUDE_CLI_MODEL", "")  # "" = CLI's configured default

_anthropic_client = None


def available_backends():
    """Return which backends are usable in this environment."""
    return {
        "claude_cli": _claude_path() is not None,
        "anthropic": bool(os.environ.get("ANTHROPIC_API_KEY")),
    }


def _claude_path():
    """Resolve the claude executable: explicit CLAUDE_BIN, else PATH lookup."""
    if CLAUDE_BIN != "claude" and os.path.isfile(CLAUDE_BIN):
        return CLAUDE_BIN
    return shutil.which(CLAUDE_BIN)


def complete(system, user, max_tokens=2000, backend=None):
    """Run one completion. Returns the model's text output as a string."""
    backend = backend or DEFAULT_BACKEND
    if backend == "anthropic":
        return _complete_anthropic(system, user, max_tokens)
    if backend == "claude_cli":
        return _complete_claude_cli(system, user)
    raise ValueError(f"Unknown LLM backend: {backend!r}")


def _complete_anthropic(system, user, max_tokens):
    global _anthropic_client
    if _anthropic_client is None:
        from anthropic import Anthropic

        _anthropic_client = Anthropic()  # reads ANTHROPIC_API_KEY
    resp = _anthropic_client.messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return "".join(b.text for b in resp.content if b.type == "text")


def _complete_claude_cli(system, user):
    exe = _claude_path()
    if exe is None:
        raise RuntimeError(
            "The `claude` CLI was not found. Set CLAUDE_BIN to its path or "
            "switch the backend to 'anthropic'."
        )
    cmd = [
        exe,
        "-p",                       # headless / print mode
        "--output-format", "json",  # structured, easy to parse
        # Replace (not append) the default agent persona so the model behaves as
        # a plain completion engine and actually follows our instructions.
        "--system-prompt", system,
        # Drop per-machine context (cwd/env/git) we don't need — cheaper & cleaner.
        "--exclude-dynamic-system-prompt-sections",
        # CRITICAL: disable all built-in tools. Otherwise the agent uses its
        # filesystem tools to read the local working directory and explains THAT
        # instead of the repo contents we pass in the prompt.
        "--tools", "",
    ]
    if CLI_MODEL:
        cmd += ["--model", CLI_MODEL]

    proc = subprocess.run(
        cmd,
        input=user,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=300,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"claude CLI failed (exit {proc.returncode}): "
            f"{(proc.stderr or proc.stdout or '').strip()[:500]}"
        )
    out = proc.stdout.strip()
    # --output-format json wraps the reply in an envelope; pull out .result.
    try:
        data = json.loads(out)
        if isinstance(data, dict) and "result" in data:
            return data["result"]
    except json.JSONDecodeError:
        pass
    return out  # fall back to raw text