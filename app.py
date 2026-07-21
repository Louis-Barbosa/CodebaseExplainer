"""Flask backend for the GitHub Codebase Explainer agent.

Serves a JSON API consumed by the React/TypeScript frontend.

Routes:
  GET  /api/backends  -> which LLM backends are available + default
  POST /api/explain   -> Mode A (URL) or Mode B (concept): full structured overview
  POST /api/followup  -> chat-style follow-up against the cached repo
  POST /api/reset     -> clear session

Run:  python app.py   (needs the Claude Code CLI or ANTHROPIC_API_KEY)
"""

import traceback

from flask import Flask, jsonify, request
from flask_cors import CORS

import explainer
import github_client as gh
import llm
import session as sess

app = Flask(__name__)
CORS(app)  # allow the Vite dev server (different port) to call the API

SID = "local"  # local single-user tool


def looks_like_repo(text):
    text = text.strip()
    return "github.com" in text or (
        "/" in text and " " not in text and text.count("/") == 1
    )


def _backend(data):
    return (data.get("backend") or llm.DEFAULT_BACKEND).strip()


def _run_overview(owner, repo, topic=None, backend=None):
    """Shared pipeline: fetch tree -> triage -> fetch files -> structured overview."""
    s = sess.get(SID)
    meta = gh.fetch_repo_meta(owner, repo)
    s.owner, s.repo, s.branch = owner, repo, meta["default_branch"]
    s.file_tree = gh.fetch_repo_structure(owner, repo, s.branch)
    s.files_read = {}
    s.history = []

    picked = explainer.triage_files(s.file_tree, topic=topic, backend=backend)
    for path in picked:
        if path not in s.files_read:
            s.files_read[path] = gh.fetch_file_contents(owner, repo, path, s.branch)

    overview = explainer.generate_overview(
        s.repo_name, s.file_tree, s.files_read, topic=topic, backend=backend
    )
    s.summary = overview["summary"]
    s.last_mermaid = overview["mermaid"]
    return {
        "repo": meta,
        "file_count": len(s.file_tree),
        "files_read": list(s.files_read.keys()),
        **overview,
    }


@app.route("/api/backends")
def backends():
    return jsonify({"available": llm.available_backends(), "default": llm.DEFAULT_BACKEND})


@app.route("/api/explain", methods=["POST"])
def explain():
    data = request.get_json(force=True)
    query = (data.get("query") or "").strip()
    backend = _backend(data)
    if not query:
        return jsonify({"error": "Empty query."}), 400
    try:
        if looks_like_repo(query):
            owner, repo = gh.parse_repo_url(query)
            result = _run_overview(owner, repo, backend=backend)
            result["mode"] = "A"
            return jsonify(result)

        # Mode B: concept search -> select -> overview
        candidates = gh.search_github(query)
        if not candidates:
            return jsonify({"error": "No repositories found for that concept."}), 404
        choice = explainer.select_best_repo(candidates, query, backend=backend)
        owner, repo = gh.parse_repo_url(choice["name"])
        result = _run_overview(owner, repo, topic=query, backend=backend)
        result["mode"] = "B"
        result["candidates"] = candidates
        result["selection"] = choice
        result["concept"] = query
        return jsonify(result)
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": f"{type(e).__name__}: {e}"}), 500


@app.route("/api/followup", methods=["POST"])
def followup():
    data = request.get_json(force=True)
    question = (data.get("question") or data.get("topic") or "").strip()
    backend = _backend(data)
    s = sess.get(SID)
    if not s.repo_name:
        return jsonify({"error": "No repo loaded yet. Explain a repo first."}), 400
    if not question:
        return jsonify({"error": "Empty follow-up question."}), 400
    try:
        # Pull in any additional relevant files not already cached.
        extra = explainer.triage_files(
            s.file_tree, topic=question, exclude=set(s.files_read.keys()), backend=backend
        )
        for path in extra:
            if path not in s.files_read:
                s.files_read[path] = gh.fetch_file_contents(
                    s.owner, s.repo, path, s.branch
                )
        result = explainer.answer_followup(
            s.repo_name, s.file_tree, s.files_read, question,
            history=s.history, backend=backend,
        )
        s.history.append({"role": "user", "content": question})
        s.history.append({"role": "assistant", "content": result["answer"][:1200]})
        if result["mermaid"]:
            s.last_mermaid = result["mermaid"]
        result["newly_read"] = extra
        return jsonify(result)
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": f"{type(e).__name__}: {e}"}), 500


@app.route("/api/reset", methods=["POST"])
def reset():
    sess.reset(SID)
    return jsonify({"ok": True})


if __name__ == "__main__":
    app.run(debug=True, port=5000)