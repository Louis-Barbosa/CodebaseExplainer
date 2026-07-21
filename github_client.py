"""Thin wrapper over GitHub's REST API.

All calls use the public REST API (no scraping). If a GITHUB_TOKEN env var is
present it is sent as a bearer token, which raises the rate limit from 60 to
5000 requests/hour and is strongly recommended.
"""

import base64
import os
import re

import requests

API = "https://api.github.com"


def _headers():
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def parse_repo_url(url_or_slug):
    """Accept a full GitHub URL or an 'owner/repo' slug. Return (owner, repo)."""
    text = url_or_slug.strip()
    # Full URL form
    m = re.search(r"github\.com[/:]([^/]+)/([^/#?]+)", text)
    if m:
        owner, repo = m.group(1), m.group(2)
    else:
        # owner/repo slug
        m = re.match(r"^([^/\s]+)/([^/\s]+)$", text)
        if not m:
            raise ValueError(f"Could not parse a GitHub repo from: {url_or_slug!r}")
        owner, repo = m.group(1), m.group(2)
    repo = repo.removesuffix(".git")
    return owner, repo


def search_github(query, per_page=8):
    """Search repositories by concept keywords, ranked by GitHub's relevance.

    Returns a list of dicts: name, description, stars, language, url.
    """
    params = {
        "q": query,
        "sort": "stars",
        "order": "desc",
        "per_page": per_page,
    }
    resp = requests.get(
        f"{API}/search/repositories", headers=_headers(), params=params, timeout=30
    )
    resp.raise_for_status()
    items = resp.json().get("items", [])
    return [
        {
            "name": it["full_name"],
            "description": it.get("description") or "",
            "stars": it.get("stargazers_count", 0),
            "language": it.get("language") or "unknown",
            "url": it["html_url"],
        }
        for it in items
    ]


def fetch_repo_meta(owner, repo):
    resp = requests.get(f"{API}/repos/{owner}/{repo}", headers=_headers(), timeout=30)
    resp.raise_for_status()
    data = resp.json()
    return {
        "full_name": data["full_name"],
        "description": data.get("description") or "",
        "stars": data.get("stargazers_count", 0),
        "language": data.get("language") or "unknown",
        "default_branch": data.get("default_branch", "main"),
        "url": data["html_url"],
    }


def fetch_repo_structure(owner, repo, branch=None):
    """Return a flat list of file paths in the repo (recursive tree, cheap)."""
    if branch is None:
        branch = fetch_repo_meta(owner, repo)["default_branch"]
    resp = requests.get(
        f"{API}/repos/{owner}/{repo}/git/trees/{branch}",
        headers=_headers(),
        params={"recursive": "1"},
        timeout=30,
    )
    resp.raise_for_status()
    tree = resp.json().get("tree", [])
    return [node["path"] for node in tree if node["type"] == "blob"]


def fetch_file_contents(owner, repo, path, branch=None):
    """Fetch a single file's decoded text contents (returns '' on binary/large)."""
    params = {}
    if branch:
        params["ref"] = branch
    resp = requests.get(
        f"{API}/repos/{owner}/{repo}/contents/{path}",
        headers=_headers(),
        params=params,
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    if isinstance(data, list):
        return ""  # directory
    if data.get("encoding") == "base64" and data.get("content"):
        try:
            return base64.b64decode(data["content"]).decode("utf-8", errors="replace")
        except Exception:
            return ""
    return ""