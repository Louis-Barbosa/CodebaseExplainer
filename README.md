# Codebase Explainer

A web agent that explains GitHub repositories: paste a repo URL and get back
an architecture diagram, a written walkthrough, and a chat box for follow-up
questions — all grounded in the actual code, not a guess at it.

> **Status: in progress.** The backend's core logic (GitHub access, LLM calls,
> triage, structured explanations, session caching) is built and usable from
> Python directly. The Flask API layer (`app.py`) and the React frontend do
> not exist yet — see [What's left](#whats-left) below. `run.ps1` and the
> "Run" instructions describe the intended final setup, not something you can
> run today.

## Concept

Two entry modes that share one pipeline:

- **Mode A — Explain a repo:** give a GitHub URL (or `owner/repo`). It fetches
  the file tree, triages the files most worth reading, and generates a
  Mermaid architecture diagram plus a written walkthrough.
- **Mode B — Find an example of a concept:** give a concept instead (e.g.
  *"a clean example of a rate limiter"*). It searches GitHub, has the LLM
  pick the best-fitting repo, then runs Mode A on it.

Follow-up questions (e.g. *"explain the auth flow"*) re-use the cached file
tree, fetch only whatever additional files the question needs, and produce a
narrower, focused diagram instead of re-explaining the whole repo.

Full design notes and rationale live in [`planning.md`](./planning.md).

## What's built so far

| File | Role | Status |
|------|------|--------|
| `github_client.py` | GitHub REST calls: search repos, fetch file tree, fetch file contents | Done |
| `llm.py` | LLM backend abstraction — Claude Code CLI or the Anthropic API, picked via env var or per-request | Done |
| `prompts.py` | System prompts + few-shot Mermaid examples for triage, repo selection, overview, and follow-ups | Done |
| `explainer.py` | The LLM-backed steps: file triage, repo selection, structured overview/follow-up generation, and slicing real code for snippets (never trusting the model to reproduce code verbatim) | Done |
| `session.py` | In-memory per-session cache: file tree, files already read, chat history | Done |
| `requirements.txt` | Backend Python dependencies | Done |
| `run.ps1` | One-command launcher for the API + frontend dev servers, with Claude CLI auto-detection | Written, but depends on files below that don't exist yet |

## What's left

- **`app.py`** — the Flask API that wires the above modules into HTTP routes
  (`/explain`, `/search`, `/followup`, etc.). This is what `run.ps1` actually
  starts — right now there's nothing for it to run.
- **`frontend/`** — the React + TypeScript + Tailwind (Vite) UI: summary view,
  Mermaid diagram rendering, code deep-dive with snippets, and the chat-style
  follow-up box. None of this exists yet.
- **`triage.py`** — `planning.md` originally called for triage to be its own
  module; in the current code it's implemented as `triage_files()` inside
  `explainer.py` instead. Worth deciding whether to split it out or keep it
  merged as the project grows.
- End-to-end testing per the build order in `planning.md` §8: a real repo
  explained start to finish, a follow-up question against it, and a Mode B
  concept search.

## Backend design notes

**Two swappable LLM backends**, chosen via the `LLM_BACKEND` env var (or
per-request once the API exists):
- `claude_cli` (default) — shells out to the `claude` Claude Code CLI, using
  your existing Claude Code login. No API key needed.
- `anthropic` — uses the Anthropic Python SDK directly; needs
  `ANTHROPIC_API_KEY`.

**Keeping large repos cheap to explore:** only the file *tree* (paths) is
fetched first. The LLM picks ~5–10 files worth reading from that tree, and
only those get fetched and passed into the explanation step — mirroring how
a person would actually skim an unfamiliar codebase instead of reading
everything.

**Explanations are structured, not free text.** `generate_overview()` and
`answer_followup()` both return JSON with a summary/answer, an optional
Mermaid diagram, and "sections" whose code references (`{path, start, end}`)
get sliced directly from the real fetched file contents — so any code shown
to the user is guaranteed to be the actual code, not something the model
reconstructed from memory.

## Setup (backend only, for now)

```bash
pip install -r requirements.txt
```

A GitHub token is recommended — it raises the API rate limit from 60 to
5,000 requests/hour:

```powershell
$env:GITHUB_TOKEN="ghp_..."
```

If using the Claude Code backend (default), just make sure the `claude` CLI
is installed and logged in. To use the Anthropic API backend instead:

```powershell
$env:ANTHROPIC_API_KEY="sk-ant-..."
$env:LLM_BACKEND="anthropic"
```

## Intended run instructions (not yet functional)

Once `app.py` and `frontend/` exist, the intended workflow is:

```powershell
./run.ps1
```

which auto-detects the Claude CLI, starts the Flask API on `:5000`, starts
the React dev server on `:5173`, and opens the browser automatically. See
`run.ps1` for the manual two-terminal alternative it wraps.

## Files

| File | Role |
|------|------|
| `planning.md` | Design doc: architecture, tools, build order |
| `github_client.py` | GitHub REST calls (search, tree, file contents) |
| `llm.py` | Backend abstraction: Claude Code CLI or Anthropic API |
| `explainer.py` | LLM steps: triage, structured overview + chat answers, snippet slicing |
| `prompts.py` | System prompts + few-shot Mermaid examples |
| `session.py` | In-memory cache of tree, files, and chat history |
| `requirements.txt` | Backend dependencies |
| `run.ps1` | One-command launcher (needs `app.py` + `frontend/` to actually work) |