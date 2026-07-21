mermaid.initialize({
  startOnLoad: false,
  securityLevel: "loose",
  theme: "base",
  themeVariables: {
    primaryColor: "#eafff5",
    primaryBorderColor: "#42f5a1",
    primaryTextColor: "#0b5f3c",
    lineColor: "#18a86b",
    secondaryColor: "#f1ecdb",
    tertiaryColor: "#fdfcf5",
    fontFamily: "Segoe UI, sans-serif",
  },
});

const $ = (id) => document.getElementById(id);
let diagramCounter = 0;

function show(el) { el.classList.remove("hidden"); }
function hide(el) { el.classList.add("hidden"); }

function setStatus(msg) {
  if (msg) { $("status").textContent = msg; show($("status")); }
  else { hide($("status")); }
}

function setError(msg) {
  if (msg) { $("error").textContent = msg; show($("error")); }
  else { hide($("error")); }
}

async function renderMermaid(code) {
  const container = $("diagram");
  container.innerHTML = "";
  if (!code) { container.innerHTML = "<em>No diagram produced.</em>"; return; }
  try {
    const id = "m" + (++diagramCounter);
    const { svg } = await mermaid.render(id, code);
    container.innerHTML = svg;
  } catch (e) {
    container.innerHTML =
      "<em>Diagram failed to render. Raw source below.</em>";
    $("mermaid-src-wrap").open = true;
  }
}

function renderResult(data) {
  // Banner
  const repo = data.repo || {};
  const name = repo.full_name || "repo";
  let banner = `<strong><a href="${repo.url || "#"}" target="_blank">${name}</a></strong>`;
  if (data.mode === "B") banner += `<span class="badge">found via concept search</span>`;
  if (repo.description) banner += `<div style="color:var(--muted);margin-top:4px">${repo.description}</div>`;
  if (repo.stars !== undefined) banner += `<div style="color:var(--muted);font-size:13px;margin-top:4px">★ ${repo.stars} · ${repo.language || ""}</div>`;
  if (data.selection && data.selection.reason)
    banner += `<div style="margin-top:6px;font-size:13px"><em>Why this repo:</em> ${data.selection.reason}</div>`;
  $("repo-banner").innerHTML = banner;

  // Mermaid
  $("mermaid-src").textContent = data.mermaid || "";
  renderMermaid(data.mermaid);

  // Walkthrough (markdown)
  $("walkthrough").innerHTML = marked.parse(data.walkthrough || "");

  // Files
  const files = data.files_read || [];
  $("files-summary").textContent = `Files read (${files.length})`;
  $("files-read").innerHTML = files
    .map((f) => `<li>${f}${(data.newly_read || []).includes(f) ? " <span style='color:var(--accent)'>(new)</span>" : ""}</li>`)
    .join("");

  show($("results"));
}

const BACKEND_LABELS = {
  claude_cli: "Claude Code (no API key)",
  anthropic: "Anthropic API key",
};

async function loadBackends() {
  try {
    const resp = await fetch("/api/backends");
    const { available, default: def } = await resp.json();
    const sel = $("backend");
    sel.innerHTML = "";
    for (const key of ["claude_cli", "anthropic"]) {
      const opt = document.createElement("option");
      opt.value = key;
      opt.textContent =
        BACKEND_LABELS[key] + (available[key] ? "" : " — not available");
      opt.disabled = !available[key];
      if (key === def && available[key]) opt.selected = true;
      sel.appendChild(opt);
    }
    // If the default isn't available, pick the first available one.
    if (sel.selectedOptions[0] && sel.selectedOptions[0].disabled) {
      const firstOk = [...sel.options].find((o) => !o.disabled);
      if (firstOk) firstOk.selected = true;
    }
    updateBackendNote(available);
    sel.addEventListener("change", () => updateBackendNote(available));
  } catch (e) {
    $("backend-note").textContent = "(could not load backends)";
  }
}

function updateBackendNote(available) {
  const key = $("backend").value;
  const note = $("backend-note");
  if (!available[key]) {
    note.textContent =
      key === "anthropic"
        ? "Set ANTHROPIC_API_KEY to enable this."
        : "Install the Claude Code CLI to enable this.";
    note.style.color = "var(--error)";
  } else {
    note.textContent = "";
  }
}

async function post(url, body) {
  const resp = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await resp.json();
  if (!resp.ok) throw new Error(data.error || "Request failed");
  return data;
}

loadBackends();

$("explain-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const query = $("query").value.trim();
  if (!query) return;
  setError(""); $("go").disabled = true;
  setStatus("Working… fetching tree, triaging files, generating diagram (can take ~20s)");
  try {
    const data = await post("/api/explain", { query, backend: $("backend").value });
    renderResult(data);
  } catch (err) {
    setError(err.message);
  } finally {
    setStatus(""); $("go").disabled = false;
  }
});

$("followup-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const topic = $("followup").value.trim();
  if (!topic) return;
  setError("");
  setStatus(`Re-exploring for: ${topic}`);
  try {
    const data = await post("/api/followup", { topic, backend: $("backend").value });
    renderResult(data);
    $("followup").value = "";
  } catch (err) {
    setError(err.message);
  } finally {
    setStatus("");
  }
});