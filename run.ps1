# One-command launcher: starts the Flask API and the React dev server together.
# Usage:  right-click > Run with PowerShell   (or)   ./run.ps1

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot

# --- Auto-detect the Claude Code CLI (no hardcoded paths / usernames) ---------
function Find-ClaudeBin {
    # 1) Already on PATH?
    $cmd = Get-Command claude -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }

    # 2) Bundled inside the VS Code extension (pick the newest version installed)
    $extGlob = Join-Path $env:USERPROFILE ".vscode\extensions\anthropic.claude-code-*\resources\native-binary\claude.exe"
    $hit = Get-ChildItem $extGlob -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if ($hit) { return $hit.FullName }

    # 3) Common standalone install locations
    $candidates = @(
        (Join-Path $env:USERPROFILE ".claude\local\claude.exe"),
        (Join-Path $env:APPDATA "npm\claude.cmd")
    )
    foreach ($c in $candidates) { if (Test-Path $c) { return $c } }

    return $null
}

$claude = Find-ClaudeBin
if ($claude) {
    $env:CLAUDE_BIN = $claude
    $env:LLM_BACKEND = "claude_cli"
    Write-Host "Found Claude Code CLI: $claude" -ForegroundColor Green
} else {
    Write-Host "Claude Code CLI not found. The 'Claude Code' backend will be disabled." -ForegroundColor Yellow
    Write-Host "Set ANTHROPIC_API_KEY to use the Anthropic API backend instead." -ForegroundColor Yellow
}

# Cheap model by default; change to claude-sonnet-5 / claude-opus-4-8 for higher quality.
$env:CLAUDE_CLI_MODEL = "claude-haiku-4-5"
# $env:GITHUB_TOKEN = "ghp_..."          # optional: raises GitHub rate limit
# $env:ANTHROPIC_API_KEY = "sk-ant-..."  # optional: enables the API backend

# Make sure node is reachable
$nodeDir = "C:\Program Files\nodejs"
if (Test-Path $nodeDir) { $env:Path = "$nodeDir;" + $env:Path }

Write-Host "Starting Flask API on http://localhost:5000 ..." -ForegroundColor Green
$api = Start-Process -FilePath "python" -ArgumentList "app.py" -WorkingDirectory $root -PassThru -WindowStyle Minimized

Write-Host "Starting React dev server on http://localhost:5173 ..." -ForegroundColor Green
$web = Start-Process -FilePath "npm.cmd" -ArgumentList "run", "dev" -WorkingDirectory (Join-Path $root "frontend") -PassThru -WindowStyle Minimized

Start-Sleep -Seconds 4
Start-Process "http://localhost:5173"

Write-Host ""
Write-Host "Open http://localhost:5173  -  press Ctrl+C here to stop both servers." -ForegroundColor Cyan
try {
    Wait-Process -Id $api.Id
} finally {
    Stop-Process -Id $web.Id -ErrorAction SilentlyContinue
    Stop-Process -Id $api.Id -ErrorAction SilentlyContinue
}