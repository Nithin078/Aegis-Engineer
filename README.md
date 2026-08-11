# Aegis Engineer

**Autonomous software engineering platform with a Repository Intelligence Engine.**

Aegis understands a codebase (structure, imports, calls, dependencies), then uses multi-agent workflows to plan and apply changes, run tests, review for security/performance/regression risk, remember past fixes, and optionally open a GitHub pull request. Agents can also **fetch and scrape public web pages** for external docs. It ships as a local-first CLI with a TUI, HTTP API, and full observability.

| | |
|---|---|
| **Package** | `aegis-engineer` |
| **Version** | 0.1.0 (phased v1) |
| **Python** | 3.12+ |
| **Entry** | `aegis` or `python -m aegis` |
| **License** | MIT |

---

## Table of contents

1. [What Aegis does](#what-aegis-does)
2. [Capabilities](#capabilities)
3. [Requirements](#requirements)
4. [Installation](#installation)
5. [Configuration & API keys](#configuration--api-keys)
6. [Quick start (recommended paths)](#quick-start-recommended-paths)
7. [Command master guide](#command-master-guide)
   - [Getting started & diagnostics](#1-getting-started--diagnostics)
   - [Configuration](#2-configuration)
   - [Interactive chat, fetch & server](#3-interactive-chat-fetch--server)
   - [Sessions](#4-sessions)
   - [Autonomous solve](#5-autonomous-solve)
   - [Repository intelligence](#6-repository-intelligence)
   - [Memory](#7-memory)
   - [Observability](#8-observability)
   - [Quality gate, docs & push](#9-quality-gate-docs--push)
   - [Benchmark](#10-benchmark)
8. [When to use which command](#when-to-use-which-command)
9. [Typical workflows](#typical-workflows)
10. [Local data & reports](#local-data--reports)
11. [Architecture (high level)](#architecture-high-level)
12. [What works vs roadmap](#what-works-vs-roadmap)
13. [Development & verification](#development--verification)
14. [Further reading](#further-reading)

---

## What Aegis does

Unlike a chat box that only sees open files, Aegis builds a **living model of the repo** and runs a **state machine of specialist agents**:

```text
Issue / prompt
    → Classify → Plan (with memory) → Retrieve context (+ docs/intel)
    → Code ⇄ Analyze (ruff) ⇄ Test (pytest)
    → Reviews (security ∥ perf → regression ∥ deps)
    → PR draft → Report + Trace + Memory write
```

You can use it as:

| Mode | Use when |
|------|----------|
| **TUI chat** | Interactive exploration, Q&A, small edits with permission prompts |
| **`aegis run`** | One-shot scripts/CI-style agent tasks |
| **`aegis solve`** | End-to-end issue fixing with tests and reviews |
| **`aegis serve`** | Remote clients / HTTP + SSE integration |
| **`aegis fetch`** | Scrape a public URL to readable text (no LLM) |
| **Intelligence CLI** | “Who calls X?”, impact analysis, hybrid search (no LLM required) |

---

## Capabilities

### Repository Intelligence (Python-first)

- Parse packages with stdlib `ast` + NetworkX  
- Import / alias resolution, call graph with confidence, class inheritance  
- External dependency map (`pyproject` / requirements)  
- Hybrid search: TF-IDF + keywords + graph boost  
- Agent tools: `graph_query`, `codesearch`  

### Multi-agent solve pipeline

- Specialists: classifier, planner, retriever, doc retriever, coder, security, perf, regression, dependency, PR generator  
- Retries on lint/test (and blocking review) failures  
- Isolation: git **worktree** (when repo is git), **file snapshot**, optional **Docker** for tests  

### Memory

- Repo store: `.aegis/memory/`  
- Global store: `~/.config/aegis/memory/`  
- Solved issues, failures, patterns; planning **queries** memory; successful/failed runs **write** memory  

### GitHub

- Fetch public/private issues by URL or `owner/repo#N`  
- Optional push + open PR (`--create-pr`, needs token + rights)  

### Web scraping / fetch

- **`webfetch` agent tool** — pull public HTTP/HTTPS pages into the agent context  
- **`aegis fetch` CLI** — same scrape path without an LLM  
- HTML → readable plain text (strips scripts/styles), optional link extraction  
- JSON / plain-text / raw body modes  
- **SSRF protection:** blocks localhost, private IPs, link-local, and cloud metadata hosts  
- Used by chat, TUI, and solve specialists (classifier, planner, retriever, doc retriever, coder)  

### Quality & docs

- Secrets scan, unit/integration tests, optional lint  
- Living docs coverage (`aegis document`)  
- Safe push gated by quality report  

### Observability

- Per-solve traces: cost, latency, tool timeline, prompt previews, reasoning  
- Stored under `.aegis/traces/`  

### Platform

- OpenAI-compatible providers (Groq, OpenRouter, Ollama) + Anthropic  
- Core tools: `read`, `write`, `edit`, `glob`, `grep`, `bash`, `graph_query`, `codesearch`, **`webfetch`**  
- Trust modes: `interactive` | `yolo` | `readonly` | `ci`  
- Plugin hooks + MCP tool bridge skeleton  
- Docker image + GitHub Actions CI  

---

## Requirements

| Requirement | Notes |
|-------------|--------|
| **Python 3.12+** | Required |
| **OS** | Windows, macOS, Linux |
| **Git** | Recommended (worktrees, push, PR) |
| **API key** | For LLM features (`run` / `solve` / TUI chat). Intelligence-only commands need none |
| **Docker** | Optional; solve/tests fall back to local if daemon is missing |
| **pytest / ruff** | Dev install includes them; used by quality gate and solve stages |

---

## Installation

### 1. Clone and create a virtualenv

```bash
cd AI_Software_Engineer   # or your clone path

python -m venv .venv

# Windows PowerShell
.venv\Scripts\Activate.ps1

# macOS / Linux
# source .venv/bin/activate
```

### 2. Install (editable + dev tools)

```bash
pip install -e ".[dev]"
```

This installs the `aegis` console script and test/lint tools.

### 3. Verify install

```bash
aegis version
aegis doctor
# same as:
python -m aegis doctor
```

All doctor checks should be **OK** (GitHub token and Docker daemon may be informational).

### 4. Optional: Docker image

```bash
docker build -t aegis-engineer .
docker run --rm aegis-engineer doctor
```

---

## Configuration & API keys

### Environment files (easiest)

| Location | Scope |
|----------|--------|
| `~/.config/aegis/.env` | **Global** — works from any project directory (recommended) |
| `./.env` | **Project only** |
| Shell env vars | Always win over files |

**Windows example:**

```powershell
# Create global config dir and copy template
New-Item -ItemType Directory -Force -Path "$env:USERPROFILE\.config\aegis"
Copy-Item .env.example "$env:USERPROFILE\.config\aegis\.env"
# Edit: set OPENAI_API_KEY, OPENAI_BASE_URL, AEGIS_MODEL, …
```

**Template:** [`.env.example`](./.env.example)

#### Free / cheap LLM (Groq)

```env
AEGIS_PROVIDER=openai
AEGIS_MODEL=llama-3.3-70b-versatile
OPENAI_API_KEY=gsk_...
OPENAI_BASE_URL=https://api.groq.com/openai/v1
```

#### Local Ollama

```env
AEGIS_PROVIDER=ollama
AEGIS_MODEL=qwen2.5-coder:7b
OPENAI_API_KEY=ollama
OPENAI_BASE_URL=http://127.0.0.1:11434/v1
```

#### Anthropic

```env
AEGIS_PROVIDER=anthropic
AEGIS_MODEL=claude-sonnet-4-20250514
ANTHROPIC_API_KEY=sk-ant-...
```

#### GitHub (optional)

```env
GITHUB_TOKEN=ghp_...
# or GH_TOKEN=...
```

Needed for private issues and `--create-pr`.

### Config hierarchy

Later layers override earlier ones:

```text
defaults → user ~/.config/aegis/config.json → project .aegis.json / .aegis/config.json → env / .env
```

Use `aegis config path` to see effective paths.

### Trust modes (permissions)

| Mode | Behavior | Typical use |
|------|----------|-------------|
| `interactive` | Prompt on risky tools | TUI |
| `yolo` | Auto-allow “ask” rules | `aegis run`, automation |
| `readonly` | Block write/shell | Safe exploration |
| `ci` | Treat “ask” as deny | Strict CI |

---

## Quick start (recommended paths)

### A. Chat with the repo (needs API key)

```bash
cd /path/to/your/project
aegis tui
# or one-shot:
aegis run "Summarize the architecture of this repo"
```

### B. Fix a local bug end-to-end

```bash
cd /path/to/your/project
aegis intelligence build          # optional but helpful
aegis solve "Fix add() so 2+3==5 in calc/math_ops.py" --dry-run   # plan only
aegis solve "Fix add() so 2+3==5 in calc/math_ops.py"             # apply + test
aegis observe show latest
```

### C. GitHub issue (plan only, no edits)

```bash
aegis solve https://github.com/owner/repo/issues/42 --dry-run -w .
```

### D. Quality gate before push

```bash
aegis test --lint
aegis push
```

### E. No API key needed

```bash
aegis intelligence build
aegis intelligence callers some_function
aegis benchmark run
aegis doctor
```

### F. Scrape a public web page (no API key)

```bash
aegis fetch https://example.com
aegis fetch https://docs.python.org/3/library/ast.html --links -o ast-docs.txt
aegis fetch https://httpbin.org/json --raw --json
```

Agents can do the same via the `webfetch` tool:

```bash
aegis run "Fetch https://example.com and summarize the page in 3 bullets"
```

---

## Command master guide

Global flags (on the root `aegis` app):

| Flag | Meaning |
|------|---------|
| `-v` / `--verbose` | Verbose logging |
| `-V` / `--version` | Print version and exit |
| `-w` / `--workspace` | Default workspace when launching bare `aegis` (TUI) |
| `--help` | Help for any command |

Bare `aegis` with no subcommand **launches the TUI**.

---

### 1. Getting started & diagnostics

#### `aegis version`

**When:** Confirm the installed package and runtime.

```bash
aegis version
aegis version --json
```

| Option | Purpose |
|--------|---------|
| `-j` / `--json` | Machine-readable version info |

#### `aegis doctor`

**When:** After install, before demos, or when something fails (keys, git, docker, imports).

```bash
aegis doctor
aegis doctor --verbose
```

Checks include: Python, package, CLI, config, DB, LLM key presence, Git, Docker, GitHub token, tools, agents, intelligence, observability, plugins.

---

### 2. Configuration

#### `aegis config`

**When:** Set provider/model/server defaults without editing JSON by hand.

```bash
aegis config path                 # where config / DB / .env live
aegis config list                 # effective flat config
aegis config list --json
aegis config set provider.default openai
aegis config set provider.model llama-3.3-70b-versatile
aegis config set server.port 4096
aegis config unset provider.model
```

| Subcommand | When to use |
|------------|-------------|
| `list` | Inspect merged settings |
| `set <key> <value>` | Persist a dotted key (user or project config) |
| `unset <key>` | Remove an override |
| `path` | Debug which files Aegis reads |

---

### 3. Interactive chat, fetch & server

#### `aegis` / `aegis tui`

**When:** Interactive coding assistant in the terminal — explore, ask, edit with permission UI. The TUI agent can call **`webfetch`** for public URLs.

```bash
aegis
aegis tui -w /path/to/project
aegis tui --provider openai --model llama-3.3-70b-versatile
aegis tui --trust-mode yolo
aegis tui --server http://127.0.0.1:4096   # attach to aegis serve
```

| Option | When |
|--------|------|
| `-w` / `--workspace` | Tools run relative to this root |
| `-m` / `--model` | Override model for this session |
| `-p` / `--provider` | Override provider |
| `--trust-mode` | `interactive` (default) / `yolo` / `readonly` / `ci` |
| `--server` | Use HTTP backend instead of in-process agent |

#### `aegis fetch` (web scrape)

**When:** You need the **text of a public web page** without starting an agent — docs, blog posts, public API JSON, issue HTML, etc.

```bash
# HTML page → plain text
aegis fetch https://example.com

# Keep hyperlinks from the page
aegis fetch https://example.com/docs --links -o page.txt

# JSON or non-HTML body
aegis fetch https://httpbin.org/json --raw

# Machine-readable wrapper
aegis fetch https://example.com --json
```

| Option | Purpose |
|--------|---------|
| `url` (required) | `http://` or `https://` only |
| `--max-chars` | Cap extracted text size (default **50000**, max 200000) |
| `--links` | Append `## Links` section from `<a href>` tags |
| `--raw` | Skip HTML→text; return truncated body as-is |
| `-o` / `--output` | Write scraped text to a file |
| `-j` / `--json` | `{ error, title, output, metadata }` |

**Safety / limits**

| Rule | Behavior |
|------|----------|
| Schemes | Only `http` and `https` |
| Local/private hosts | **Blocked** (localhost, `127.0.0.1`, RFC1918, link-local, metadata hosts) |
| Redirects | Followed (max 5); final host re-validated |
| Timeout | Uses tool timeout (CLI ~30s) |
| Size | Text truncated to `--max-chars` |

**Agent tool:** same implementation is registered as **`webfetch`** for `aegis run`, TUI, and solve specialists.

```bash
aegis run "Use webfetch on https://peps.python.org/pep-0008/ and list 5 style rules"
```

> **Note:** This is page fetch + HTML text extraction, not a full browser crawler (no JS rendering, no site-wide spidering). For GitHub **issues/PRs as structured data**, prefer `aegis solve <issue-url>` / the GitHub client rather than scraping `github.com` HTML.

#### `aegis run`

**When:** Non-interactive one-shot task (scripts, automation, “do this and exit”).

```bash
aegis run "List all public functions in src/aegis/tools"
aegis run "Add a docstring to foo.py" -w . --trust-mode yolo
aegis run "..." --session sess_abc123 --json
```

| Option | When |
|--------|------|
| `prompt` (required) | Natural language task |
| `-w` | Workspace for file tools |
| `-m` / `-p` | Model / provider override |
| `--trust-mode` | Defaults toward **yolo** for non-interactive |
| `--max-iterations` | Cap agent loop |
| `--title` | New session title |
| `--session` | Continue an existing session id |
| `-j` / `--json` | Structured final result |

#### `aegis serve`

**When:** Expose REST + SSE for browsers, the TUI `--server` mode, or external clients.

```bash
aegis serve
aegis serve --host 0.0.0.0 --port 4096 -w .
aegis serve --reload          # dev auto-reload
```

Open `http://127.0.0.1:4096/` for the landing page. Useful routes: `/health`, `/session`, `/session/{id}/chat`, `/events`, `/provider`.

| Option | When |
|--------|------|
| `--host` / `--port` | Bind address (defaults from config, often `127.0.0.1:4096`) |
| `-w` | Default tool workspace |
| `--reload` | Local development |

---

### 4. Sessions

#### `aegis session`

**When:** Inspect or export past conversations stored in SQLite.

```bash
aegis session create --title "Auth refactor"
aegis session list
aegis session show sess_xxxxxxxxxxxx
aegis session export sess_xxxxxxxxxxxx -o chat.json
aegis session delete sess_xxxxxxxxxxxx --yes
```

| Subcommand | Purpose |
|------------|---------|
| `create` | Empty session shell |
| `list` | Recent sessions |
| `show` | Messages + metadata |
| `export` | JSON backup |
| `delete` | Remove session + messages |

---

### 5. Autonomous solve

#### `aegis solve`

**When:** You have a bug/feature description (text, file, or GitHub issue) and want the full engineering loop: plan → edit → lint → test → review → PR draft.

```bash
# Local issue text
aegis solve "Fix race in cache invalidation" -w .

# Issue from a markdown file
aegis solve ./issue.md

# Plan only (no file edits)
aegis solve "..." --dry-run

# GitHub issue
aegis solve https://github.com/owner/repo/issues/123 --dry-run
aegis solve owner/repo#123 -w .

# Faster / controlled runs
aegis solve "..." --skip-reviews --no-memory
aegis solve "..." --no-worktree          # edit in place
aegis solve "..." --docker               # prefer Docker for analyze/test
aegis solve "..." --max-retries 5 --json

# Open PR after success (explicit; needs GITHUB_TOKEN + push rights)
aegis solve https://github.com/owner/repo/issues/123 --create-pr --pr-base main
```

| Option | When to use |
|--------|-------------|
| `issue` | Free text, path to `.md`/`.txt`, issue URL, or `owner/repo#N` |
| `-w` | Target repository root |
| `--dry-run` | Classification/plan/retrieve only — safe first pass |
| `--max-retries` | How many code↔test loops before fail (default 3) |
| `-m` / `-p` | Model / provider for this run |
| `--no-worktree` | Skip git worktree isolation |
| `--docker` | Run quality pipeline in Docker when available |
| `--create-pr` | Push branch + open PR after success |
| `--pr-base` | Base branch for PR (default `main`) |
| `--keep-worktree` | Keep temp worktree for inspection (implied by `--create-pr`) |
| `--github-token` | Token override (else env) |
| `--skip-reviews` | Skip security/perf/regression/dependency stages |
| `--no-memory` | Do not read/write memory this run |
| `-j` / `--json` | Machine-readable summary |

**Outputs:**

- Report: `.aegis/reports/solve-latest.md`  
- Trace: `.aegis/traces/` → inspect with `aegis observe show latest`  
- Memory: written on real success/failure (unless `--no-memory` / dry-run success)  

---

### 6. Repository intelligence

#### `aegis intelligence`

**When:** Understand structure **without** (or before) calling an LLM. Best on **Python** repos.

```bash
aegis intelligence build
aegis intelligence build --incremental
aegis intelligence status

aegis intelligence callers format_name
aegis intelligence query "who calls greet"
aegis intelligence impact path/to/module.py
aegis intelligence search "jwt expiration token"
aegis intelligence search "auth" --keyword-only

aegis intelligence graph --type import
aegis intelligence graph --type call
aegis intelligence graph --type class
aegis intelligence graph --type dependency
aegis intelligence deps
```

| Subcommand | When |
|------------|------|
| `build` | First time on a repo, or after large code changes |
| `status` | Check cache / counts under `.aegis/intelligence/` |
| `callers` | “Who calls this symbol?” |
| `query` | Natural-language relationship questions |
| `impact` | Blast radius of changing a file/region |
| `search` | Hybrid symbol search (semantic + keyword + graph) |
| `graph` | Summarize import / call / class / dependency graphs |
| `deps` | External packages and importers |

Most subcommands support `-w` and `-j` / `--json`.

---

### 7. Memory

#### `aegis memory`

**When:** Inspect or curate learned fixes/patterns. Solve already reads/writes memory automatically.

```bash
aegis memory list -w .
aegis memory list --kind solved
aegis memory query "jwt expiration bug"
aegis memory show mem_xxxxxxxxxxxx
aegis memory add -t "Prefer dataclasses" -s "This repo avoids Pydantic models"
aegis memory export -o memory-backup.json
aegis memory import memory-backup.json
aegis memory forget mem_xxxxxxxxxxxx
aegis memory forget --all-repo --yes
```

| Subcommand | When |
|------------|------|
| `list` | Browse entries (repo + global by default) |
| `show` | Full payload for one id |
| `query` | Similarity search before planning manually |
| `add` | Teach a convention / pattern by hand |
| `export` / `import` | Backup or share memory across machines |
| `forget` | Remove bad or sensitive entries (`--yes` for bulk) |

**Kinds:** `solved` · `failure` · `pattern` · `preference` · `global` · `note`

---

### 8. Observability

#### `aegis observe`

**When:** After `solve` (or any traced run) to debug cost, slow phases, tool use, or reasoning.

```bash
aegis observe list
aegis observe latest
aegis observe show latest
aegis observe show trace_abc123def456
aegis observe export latest -o trace.json
aegis observe export latest --md -o trace.md
```

| Subcommand | Purpose |
|------------|---------|
| `list` | Recent traces in `.aegis/traces/` |
| `show` | Cost table, latency, tools, reasoning |
| `export` | Full JSON or markdown summary |
| `latest` | Alias for `show latest` |

---

### 9. Quality gate, docs & push

#### `aegis test`

**When:** Before sharing code or pushing — secrets + tests (+ optional lint/docs).

```bash
aegis test
aegis test --lint
aegis test --docs --docs-min-coverage 0.5
aegis test --extra "pytest tests/custom -q"
aegis test --cases ./my-cases.txt --json
aegis test install-hook          # git pre-push runs aegis test
```

| Option | When |
|--------|------|
| `--lint` | Include ruff/eslint if present |
| `--no-secrets` / `--no-unit` / `--no-integration` | Skip parts of the gate |
| `-e` / `--extra` | Custom shell checks (repeatable) |
| `--cases` | File of extra commands |
| `--docs` | Fail/report on documentation coverage |
| `-o` / `--report` | Custom report path |
| `-j` | JSON summary |

Verdict appears in `.aegis/reports/` as **SAFE TO PUSH** / **NOT SAFE TO PUSH**.

#### `aegis push`

**When:** Push only if the quality gate is green (or you deliberately skip it).

```bash
aegis push
aegis push --lint
aegis push --reuse-report --max-age-minutes 30
aegis push -r origin -b feature/fix
aegis push --skip-test          # dangerous; prints a warning
```

#### `aegis document`

**When:** Keep CLI/API/architecture docs aligned with code; CI drift checks.

```bash
aegis document                  # write proposals under docs/_proposed/
aegis document --apply          # write real docs/CLI.md, API.md, …
aegis document --check --min-coverage 0.5 --fail-on-stale
aegis document --json
```

| Option | When |
|--------|------|
| `--apply` | Commit-ready docs in `docs/` |
| `--check` | CI: non-zero exit on coverage/gap policy |
| `--min-coverage` | Threshold for `--check` |
| `--fail-on-stale` | Fail if docs reference missing symbols |

---

### 10. Benchmark

#### `aegis benchmark`

**When:** Smoke the solve pipeline **without an API key** (mock provider), or list tasks.

```bash
aegis benchmark list
aegis benchmark run
aegis benchmark run -t add_bug --json
```

| Subcommand | Purpose |
|------------|---------|
| `list` | Built-in tasks (currently `add_bug`) |
| `run` | Materialize fixture + mock solve + report under `.aegis/benchmark/` |

---

## When to use which command

| Goal | Command(s) |
|------|------------|
| Install health check | `doctor` |
| Set Groq/OpenAI keys | Edit `~/.config/aegis/.env` + `config list` |
| Chat / explore interactively | `tui` or bare `aegis` |
| One automation task | `run "…"` |
| Scrape a public URL (no LLM) | **`fetch <url>`** |
| Agent reads a public URL | `run` / TUI with **`webfetch` tool** |
| HTTP API for clients | `serve` |
| Full autonomous fix | `solve` (start with `--dry-run`) |
| GitHub issue plan only | `solve <url> --dry-run` |
| Open a PR after fix | `solve … --create-pr` |
| “Who calls this?” | `intelligence callers` / `query` |
| Symbol search | `intelligence search` |
| Change impact | `intelligence impact` |
| Reuse past fixes | automatic in `solve`; inspect with `memory` |
| Debug cost / failures | `observe show latest` |
| Pre-push safety | `test` then `push` |
| Docs drift | `document --check` / `--apply` |
| No-key regression of solve | `benchmark run` |
| Past chats | `session list` / `show` / `export` |

---

## Typical workflows

### Workflow 1 — New machine setup

```bash
pip install -e ".[dev]"
aegis doctor
# configure ~/.config/aegis/.env with API keys
aegis config list
```

### Workflow 2 — Onboard a Python repo

```bash
cd my-project
aegis intelligence build
aegis intelligence status
aegis intelligence search "authentication"
aegis tui
```

### Workflow 2b — Pull external docs into a task

```bash
# Offline scrape first
aegis fetch https://docs.python.org/3/library/asyncio.html -o /tmp/asyncio.txt

# Or let the agent fetch during the task
aegis run "Fetch https://docs.python.org/3/library/asyncio.html and explain TaskGroup for this repo"
```

### Workflow 3 — Bugfix with review trail

```bash
aegis solve "./bugs/issue-42.md" --dry-run
aegis solve "./bugs/issue-42.md"
aegis observe export latest --md -o fix-trace.md
aegis memory list --kind solved
aegis test --lint
aegis push
```

### Workflow 4 — CI-ish local gate

```bash
aegis test --lint --docs --json
aegis document --check --min-coverage 0.4
aegis benchmark run
```

### Workflow 5 — Headless server + TUI client

```bash
# terminal 1
aegis serve -w /path/to/project

# terminal 2
aegis tui --server http://127.0.0.1:4096 -w /path/to/project
```

---

## Local data & reports

All under the **workspace** unless noted:

| Path | Contents |
|------|----------|
| `.aegis/intelligence/` | Graph/index cache |
| `.aegis/memory/entries.jsonl` | Repo memory |
| `.aegis/traces/` | Observability traces (`latest.json`) |
| `.aegis/reports/` | Solve + quality + docs reports |
| `.aegis/benchmark/` | Benchmark fixtures & last report |
| `.aegis/worktrees/` | Temporary solve worktrees |

**User-global:**

| Path | Contents |
|------|----------|
| `~/.config/aegis/config.json` | User config |
| `~/.config/aegis/.env` | Global secrets |
| `~/.config/aegis/aegis.db` | Sessions SQLite (default) |
| `~/.config/aegis/memory/` | Global memory |

---

## Architecture (high level)

```text
CLI (Typer) ──► TUI / run / solve / serve
                      │
              HTTP (Starlette + SSE) optional
                      │
              Manager / workflow FSM
         ┌────────────┼────────────┐
         ▼            ▼            ▼
   Intelligence   Agent specialists   Memory
   (Python AST)   + tool registry     (jsonl)
         │            │
         ▼            ▼
   Execution (local / Docker) · Worktree · Snapshot
                      │
                      ▼
               GitHub API (optional PR)
                      │
                      ▼
               Traces + reports
```

**Stack:** Python 3.12 · Typer · Rich · Textual · Pydantic · SQLModel · Starlette · NetworkX · OpenAI/Anthropic SDKs.

---

## What works vs roadmap

| Area | Status |
|------|--------|
| Installable CLI + doctor | ✅ |
| Config, sessions, tools, permissions | ✅ |
| Providers (OpenAI-compatible + Anthropic + mock) | ✅ |
| TUI + `run` + HTTP/SSE | ✅ |
| **Web scrape (`aegis fetch` / `webfetch` tool)** | ✅ |
| Quality gate + push + living docs | ✅ |
| Python intelligence + hybrid search | ✅ |
| Full solve + reviews + PR draft | ✅ |
| Worktree / snapshot / Docker fallback | ✅ |
| GitHub issue fetch + optional PR | ✅ |
| Memory + observe + benchmark | ✅ |
| Plugin hooks + MCP bridge skeleton | ✅ |
| CI workflow + Dockerfile | ✅ |
| Full browser JS rendering / site crawlers | ⬜ not planned for v1 |
| JS/TS/Go/Rust full graphs | ⬜ [docs/LANGUAGE_MATRIX.md](docs/LANGUAGE_MATRIX.md) |
| SWE-bench leaderboard | ⬜ skeleton only |
| Prometheus / multi-lang LSP | ⬜ post-v1 |

---

## Development & verification

```bash
# Activate venv first
pip install -e ".[dev]"

ruff check src tests
pytest -q
aegis doctor
aegis benchmark run
```

Project layout (abbreviated):

```text
src/aegis/
  cli/             # Typer commands
  agents/          # Loop + specialists
  orchestration/   # Solve FSM
  intelligence/    # Graphs + search
  memory/          # Learnings store
  observability/   # Traces
  plugins/         # Hooks + MCP
  tools/           # read/write/edit/grep/…
  providers/       # LLM backends
  server/ tui/ quality/ docs_engine/ github/ …
tests/unit/
docs/              # Generated + LANGUAGE_MATRIX
PHASES.md          # Implementation roadmap
```

---

## Further reading

| Document | Purpose |
|----------|---------|
| [`PHASES.md`](./PHASES.md) | Phase status, review gates, build history |
| [`CHANGELOG.md`](./CHANGELOG.md) | v1 release notes |
| [`docs/LANGUAGE_MATRIX.md`](./docs/LANGUAGE_MATRIX.md) | Language support honesty |
| [`docs/CLI.md`](./docs/CLI.md) | Auto-generated command inventory |
| [`docs/API.md`](./docs/API.md) | HTTP surface |
| [`docs/ARCHITECTURE.md`](./docs/ARCHITECTURE.md) | Architecture notes |
| [`AI_Software_Engineer_Project_Blueprint.md`](./AI_Software_Engineer_Project_Blueprint.md) | Full product design |
| [`.env.example`](./.env.example) | Env template |

---

## License

MIT — see [`LICENSE`](./LICENSE).
