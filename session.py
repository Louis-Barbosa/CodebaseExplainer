"""In-memory session state so follow-ups don't re-fetch.

Single-process, in-memory store keyed by a session id. Good enough for a local
single-user tool; swap for Redis if this ever needs to scale.
"""


class Session:
    def __init__(self):
        self.owner = None
        self.repo = None
        self.branch = None
        self.file_tree = None          # list[str], cached
        self.files_read = {}           # path -> contents, cached
        self.summary = None
        self.last_mermaid = None
        self.history = []              # [{role, content}] chat turns

    @property
    def repo_name(self):
        if self.owner and self.repo:
            return f"{self.owner}/{self.repo}"
        return None


_sessions = {}


def get(session_id):
    if session_id not in _sessions:
        _sessions[session_id] = Session()
    return _sessions[session_id]


def reset(session_id):
    _sessions[session_id] = Session()
    return _sessions[session_id]