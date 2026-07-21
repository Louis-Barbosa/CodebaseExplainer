# GitHub Codebase Explainer Agent — Planning

## 1. Concept

An agent with two entry modes:

**Mode A — "Explain this repo":** user gives a GitHub URL. Agent clones/reads
it, produces an architecture diagram (Mermaid) and a written walkthrough.
Follow-ups ("explain the auth flow") re-traverse relevant files and update
the diagram.

**Mode B — "Find me an example of X":** user gives a concept ("show me how
OAuth refresh tokens work", "find a good example of a producer-consumer
queue in Go"). Agent searches GitHub for a real repo that demonstrates the
concept well, picks one, then runs Mode A's explain pipeline on it.

Mode B is really just "Mode A with a search step bolted on the front" — same
core pipeline, which keeps the build simple.


## 2. Architecture

```
User input
   │
   ├── Is it a GitHub URL? ──────────────► Mode A
   │                                          │
   └── Is it a concept/question? ─► [Search Tool]
                                              │
                                    candidate repos (ranked)
                                              │
                                    [Repo Selector] picks best fit
                                              │
                                              ▼
                                          Mode A
                                              │
                  ┌───────────────────────────┴───────────────────────────┐
                  ▼                                                       ▼
          [Repo Reader Tool]                                    [Follow-up Handler]
       (file tree, key files,                                  (re-reads relevant
        READMEs, entry points)                                  files based on new
                  │                                              question, e.g.
                  ▼                                              "explain the auth flow")
        [Diagram + Explanation
            Generator]
                  │
                  ▼
        Mermaid diagram + written
            walkthrough
```

## 3. Tools needed

1. **`search_github(query)`** — GitHub's search API (`/search/repositories` or
   `/search/code`). For Mode B, search by concept keywords + filter by stars/
   recency to avoid picking a dead or toy repo. Return top N candidates with
   name, description, stars, primary language.

2. **`select_best_repo(candidates, concept)`** — give the LLM the candidate
   list and ask it to pick the one that best demonstrates the concept clearly
   (not just most popular — well-documented and focused beats a huge generic
   monorepo). This is itself a small reasoning step, not a hardcoded rule.

3. **`fetch_repo_structure(repo)`** — get the file tree (GitHub API
   `/repos/{owner}/{repo}/git/trees` or shallow `git clone --depth 1`).
   Don't pull every file — pull the tree first, then selectively fetch only
   files that look relevant (README, main entry points, anything matching
   concept keywords).

4. **`fetch_file_contents(repo, path)`** — get the contents of a specific
   file. Used both for the initial pass and for follow-up "explain the X
   flow" requests, which re-fetch just the files relevant to X.

5. **`generate_diagram_and_explanation(context)`** — LLM call that takes the
   fetched file contents/structure and produces:
   - Mermaid diagram (architecture or flow-specific, depending on the request)
   - Written walkthrough (plain language, references actual file names)

## 4. Mermaid generation guidance (put in the system prompt)

Keep diagrams scoped — a full monorepo architecture diagram is overwhelming
and usually wrong on a first pass. Default to:
- **Top-level**: a `graph TD` showing major modules/folders and how they
  depend on each other (inferred from imports, not guessed)
- **Follow-up/flow-specific**: a `sequenceDiagram` or narrower `graph TD`
  showing just the files/functions involved in the requested flow (e.g. auth)

Give the LLM 1-2 short hand-written Mermaid examples in the prompt (same
few-shot principle as before) so syntax stays valid — Mermaid syntax errors
are the most likely failure mode even though there's no execution involved.

## 5. Initial repo triage (avoid context overload)

Don't dump the whole repo into context. A simple, cheap triage step:
1. Fetch file tree only (cheap — just paths)
2. LLM picks ~5-10 "interesting" files based on names/structure (README,
   main.py/index.js, config, anything matching the user's stated interest)
3. Fetch contents of only those files
4. Generate diagram + explanation from that subset

This keeps token usage (and cost) low even on large repos, and mirrors how a
human would actually explore an unfamiliar codebase.

## 6. Follow-up handling

Same session-state pattern as before:

```python
session_state = {
    "repo": None,            # owner/name
    "file_tree": None,       # cached, no need to re-fetch
    "files_read_so_far": {}, # path -> contents, cached
    "last_diagram": None,
}
```

On a follow-up like "explain the auth flow":
1. Check `files_read_so_far` first — may already have what's needed
2. If not, do a targeted triage pass: ask LLM which *additional* files (from
   the cached file tree) are likely relevant to "auth flow"
3. Fetch only those, generate an updated/narrower diagram + explanation

## 7. Suggested file structure

```
repo_explainer/
├── main.py                 # CLI loop, routes Mode A vs Mode B
├── github_client.py        # search_github, fetch_repo_structure, fetch_file_contents
├── triage.py                # picks which files matter (initial + follow-up)
├── explainer.py             # generate_diagram_and_explanation()
├── prompts/
│   ├── system_prompt.txt
│   └── mermaid_examples.py  # few-shot Mermaid examples
├── session.py
└── requirements.txt         # requests (or PyGithub), anthropic
```

## 8. Build order (for the 3-hour session)

1. Mode A only, hardcoded to one known repo first — prove file tree → triage
   → fetch → Mermaid diagram + explanation pipeline works end to end
2. Generalize Mode A to any GitHub URL
3. Add follow-up handling (re-triage on new question)
4. Add Mode B: search_github + select_best_repo, feeding into the same Mode
   A pipeline
5. (Stretch) Simple web UI to render Mermaid inline instead of saving to file

## 9. What to tell Claude Code

> Build a CLI Python agent per repo_explainer_plan.md. Implement Mode A
> first (explain a given GitHub repo URL: fetch tree, triage relevant files,
> generate Mermaid diagram + explanation) and get it fully working on a real
> public repo before adding Mode B (concept search). Use GitHub's REST API,
> not scraping. Cache fetched files in session state so follow-ups don't
> re-fetch. Test with: (1) explain a small real repo, (2) a follow-up asking
> about one specific flow in it, (3) a concept search query like "find a
> clean example of a rate limiter" end to end.