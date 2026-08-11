# Aegis Engineer — Phased Build Plan

> Full product design lives in [`AI_Software_Engineer_Project_Blueprint.md`](./AI_Software_Engineer_Project_Blueprint.md).  
> This file is the **implementation roadmap**: small milestones, review after each phase before continuing.

---

## Goal

Build **Aegis Engineer** as a production-grade autonomous software engineering platform with a **Repository Intelligence Engine**, multi-agent pipeline, tools, memory, GitHub integration, and observability — **in reviewable phases**, not all at once.

### Working agreement

- One phase (or block) at a time.
- After each milestone: **you review** before the next phase starts.
- Prefer vertical slices that stay runnable over incomplete wide scaffolds.
- Stack baseline: Python 3.12+, Typer, Starlette, SQLite, Tree-sitter (later), etc.
- Early phases are **local-first** (no Docker / Qdrant / multi-language until foundations are solid).

---

## Architecture (target)

```text
CLI (Typer) → HTTP Server (Starlette + SSE) → Manager Agent
                    ├── Repository Intelligence Engine
                    ├── Agent Pipeline (13 agents)
                    ├── Memory System
                    ├── Tools + Permissions
                    └── Docker Sandbox → GitHub API
```

Client/server split (OpenCode-style): TUI is one client; `aegis run` / SDK / web can be others.

---

## Status overview

| Phase | Name | Status |
|-------|------|--------|
| **0** | Project foundation | ✅ Done |
| **1** | Config + storage | ✅ Done |
| **2** | Tools + permissions | ✅ Done |
| **3** | Provider + agent loop | ✅ Done |
| **4** | HTTP server + SSE | ✅ Done |
| **5** | Minimal TUI | ✅ Done |
| **5.5** | Quality gate (`aegis test` / push) | ✅ Done |
| **5.6** | Living docs (`aegis document`) | ✅ Done |
| **6** | Intelligence core (Python) | ✅ Done |
| **7** | Intelligence advanced | ✅ Done |
| **8** | Orchestration v1 | ✅ Done |
| **9** | Execution + GitHub | ✅ Done |
| **10** | Full agent suite + memory | ✅ Done |
| **11** | Observability + polish | ✅ Done |

---

## Phase map (demo outcomes)

| Phase | Outcome you can demo |
|-------|----------------------|
| **0** | Installable package, `aegis version` / `doctor` |
| **1** | Hierarchical config, SQLite sessions |
| **2** | Core file tools with allow/deny/ask |
| **3** | `aegis run` streams tokens + tool calls |
| **4** | REST + SSE API (`aegis serve`) |
| **5** | Textual TUI talks to server |
| **6** | AST + import + call graphs, intelligence CLI |
| **7** | Impact analysis, embeddings, `graph_query` |
| **8** | Classify → plan → retrieve → code → analyze → test |
| **9** | Sandbox/tests + clone/issue/PR path |
| **10** | Full reviews + memory learn-from-fixes |
| **11** | Traces, cost, packaging, doctor complete |

---

# Completed phases

## Phase 0 — Project foundation ✅

**Why first:** Nothing else is trustworthy without a real package layout, tests, and lint.

### Blocks

#### 0.1 — Scaffold
- `src/aegis/…`, `tests/`, `pyproject.toml` (Hatchling)
- Package name `aegis-engineer`, entry `aegis = aegis.cli.main:app`
- Minimal deps; README with install-from-source

#### 0.2 — CLI skeleton
- `aegis version` (text + `--json`)
- `aegis doctor` (environment checks)
- Global flags: `--verbose`, `--version`

### Review gate 0
- [x] `pip install -e ".[dev]"` works  
- [x] `aegis version` works  
- [x] `pytest` green  
- [x] `ruff check` clean  

---

## Phase 1 — Config + SQLite storage ✅

### Blocks

#### 1.1 — Configuration
- Pydantic schema (`config/schema.py`, `defaults.py`, `loader.py`)
- Hierarchy: defaults → user `~/.config/aegis/config.json` → project `.aegis.json` / `.aegis/config.json` → env
- `aegis config list | set | unset | path`

#### 1.2 — Database
- SQLite via SQLModel; `sessions`, `messages`, `schema_meta`
- Auto-migrate on open

#### 1.3 — Session CRUD
- `SessionManager` + CLI: `create`, `list`, `show`, `delete`, `export`

### Also added later (config UX)
- Project + **global** `.env` loading (`python-dotenv`)
- Global keys: `~\.config\aegis\.env` (works from any project directory)
- Project keys: `./.env`

### Review gate 1
- [x] Config round-trip; project overrides user  
- [x] DB migrates on empty path  
- [x] Session CRUD unit + CLI tests  

---

## Phase 2 — Event bus, tools, permissions ✅

### Blocks

#### 2.1 — Event bus
- Async pub/sub (`bus/events.py`, `pubsub.py`)
- Event types: `agent.*`, `permission.*`, `session.*`, `log.*`

#### 2.2 — Tool system
- `ToolDefinition`, `ToolResult`, `ToolRegistry`
- Tools: `read`, `write`, `edit`, `glob`, `grep`, `bash` (timeouts, workspace sandbox)

#### 2.3 — Permission engine
- Rules: tool + agent → allow | deny | ask  
- Trust modes: `interactive`, `yolo`, `readonly`, `ci`

### Review gate 2
- [x] Tools work on fixture repo  
- [x] `readonly` blocks write  
- [x] Events fire on tool execute  

---

## Phase 3 — LLM providers + agent loop ✅

### Blocks

#### 3.1 — Provider abstraction
- `LLMProvider` ABC, `ChatChunk`, token usage + cost estimates
- **OpenAI** (+ OpenAI-compatible: Groq, OpenRouter, Ollama) and **Anthropic** SDKs  
  *(LiteLLM was planned; dropped as hard dep due to Windows install issues)*
- Retries/backoff on rate limits
- `MockProvider` for tests

#### 3.2 — Base agent + loop
- Shared `agent_loop` (LLM → tools → until done)
- `create_chat_agent()` for free-form tasks

#### 3.3 — `aegis run`
- Non-interactive prompt, stream to stdout, session persistence
- Non-interactive defaults `trust_mode=yolo` when config is `interactive`

### Free / cheap usage notes
- Groq / OpenRouter / Ollama via `OPENAI_API_KEY` + `OPENAI_BASE_URL`
- Gemini free API: not native yet (can add later)
- Prefer global `~\.config\aegis\.env` for multi-project use

### Review gate 3
- [x] Tool calls execute and return (mocked + live Groq smoke)  
- [x] Tokens/cost tracked on session  
- [x] Max-iterations safety  
- [x] Unit tests with mock provider  

---

## Phase 4 — HTTP server + SSE ✅

### Blocks

#### 4.1 — Starlette app
- App factory, CORS, workspace state
- Routes:

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Landing page (browser guide) |
| GET | `/health` | Liveness |
| POST | `/session` | Create session |
| GET | `/session/{id}` | Session details |
| GET | `/session/{id}/messages` | History |
| POST | `/session/{id}/chat` | Chat (SSE if `stream: true`) |
| POST | `/tool/execute` | Debug tool run |
| GET | `/provider` | List providers |
| GET | `/events?session_id=` | Live SSE feed |

#### 4.2 — Server lifecycle
- `aegis serve [--host] [--port] [-w workspace]`
- In-process ASGI tests (httpx)

### Review gate 4
- [x] Create session + chat via API (mock provider)  
- [x] Same agent loop as `aegis run`  
- [x] Integration tests without TUI  
- [x] Browser `GET /` no longer 404  

---

# Upcoming phases

## Phase 5 — Minimal TUI ✅

### Block 5.1 — Textual shell
- Chat screen (`RichLog` + input + status bar)
- **In-process** agent by default (same loop as `aegis run`)
- Optional `--server http://127.0.0.1:4096` HTTP/SSE client mode
- Permission modal for `ask` rules (Allow / Deny)
- `aegis` / `aegis tui` launches TUI

### Review gate 5
- [x] TUI app + backend unit tests  
- [x] Headless still works via `aegis run`  
- [x] Permission modal wired for interactive trust mode  

---

---

## Phase 5.5 — Quality gate (`aegis test`) ✅

### What it does
- `aegis test` — secrets scan, unit/integration tests, optional lint, user cases
- Markdown + JSON report under `.aegis/reports/` (CodeRabbit-style summary)
- Verdict: **SAFE TO PUSH** / **NOT SAFE TO PUSH**
- `aegis push` — only pushes if gate is green
- `aegis test install-hook` — optional git pre-push hook

### Review gate 5.5
- [x] Secrets detected and redacted in report  
- [x] Unit tests auto-detected (pytest)  
- [x] User `--extra` / `--cases` supported  
- [x] Push blocked when NOT SAFE  

---

## Phase 5.6 — Living documentation (`aegis document`) ✅

### What it does
- Inventory: packages, CLI commands, HTTP routes
- Coverage map + gap/stale report
- Creates/updates `docs/CLI.md`, `API.md`, `ARCHITECTURE.md`, `GAPS.md`, changelog
- Default: write under `docs/_proposed/`; `--apply` for real files; `--check` for CI
- `aegis test --docs` includes documentation in the quality gate
- Provenance footers on generated files (anti-hallucination trail)

### Review gate 5.6
- [x] Coverage + missing topic detection  
- [x] Deterministic templates (no LLM required for v1)  
- [x] CLI + unit tests  

---

## Phase 6 — Repository Intelligence Engine (core, Python-first) ✅

### What shipped
- Python parse via **stdlib `ast`** + NetworkX
- **Import/alias resolution** (`from util import x as y` → `util.x`)
- **`self` / constructor type binding** for method calls
- **Definition index** + refined call edges with **confidence**
- Symbols, import graph, call graph; cache `.aegis/intelligence/index.json`
- CLI: `build`, `status`, `query`, `callers`, `impact`, `search`, `graph`
- Agent tool: **`graph_query`**

### Review gate 6
- [x] Resolved “who calls format_name” across files  
- [x] Alias + self/constructor cases tested  
- [x] graph_query tool registered  

---

---

---

## Phase 7 — Intelligence advanced + hybrid retrieval ✅

### What shipped
- **Class inheritance** graph (`subclasses` / `bases`, resolved parents)
- **External deps** from pyproject/requirements + importers map
- **Hybrid search**: lightweight TF-IDF (no heavy ML) + keyword + graph boost
- CLI: `search` (hybrid), `deps`, `graph --type class|dependency`
- Tools: `graph_query` expanded ops, **`codesearch`**
- Qdrant/LSP deferred (local TF-IDF fallback is the v1 path)

### Review gate 7
- [x] Inheritance + deps on fixture  
- [x] Hybrid search returns ranked symbols  
- [x] graph_query + codesearch registered  

---

---

## Phase 8 — Orchestration v1 (core workflow) ✅

### What shipped
- State machine: CLASSIFY → PLAN → RETRIEVE → CODE ⇄ ANALYZE → TEST → COMPLETE/FAILED
- Specialists: classifier, planner, retriever, coder (+ deterministic ruff/pytest stages)
- Retries on analyze/test failure back to CODE
- `aegis solve` with `--dry-run`, `--max-retries`, issue file or text
- Reports under `.aegis/reports/solve-*.md`
- Fixture e2e: failing `add` test fixed via mock tool edit

### Review gate 8
- [x] Seeded bug fixture → fix → tests pass  
- [x] Dry-run completes plan without edits  
- [x] History + report written  

---

---

## Phase 9 — Sandbox + GitHub integration ✅

### What shipped
- **`execution/`**: local process runner, Docker sandbox with **local fallback**, format→lint→test pipeline
- **`worktree/`**: git worktree create/commit/cleanup; successful fixes applied back to workspace
- **`snapshot/`**: file snapshot + revert + tree copy
- **`github/`**: issue URL parse/fetch (httpx), PR create, remote detect, push helper
- `aegis solve <issue-url>` / `owner/repo#N`
- Flags: `--docker`, `--no-worktree`, `--create-pr`, `--keep-worktree`, `--github-token`
- Doctor checks: Git, Docker, GitHub token

### Review gate 9
- [x] Unit tests: pipeline, snapshot, worktree, GitHub parse/client mocks  
- [x] Solve fixture still green; dry-run for public issue URL path  
- [x] PR path is opt-in (`--create-pr`) — never pushes without flag  

---

## Phase 10 — Full agent suite + memory ✅

### What shipped
- **Specialists**: classifier, planner, retriever, doc_retriever, coder, security, perf, regression, dependency, pr_generator, intelligence
- **Pipeline**: … → TEST → **REVIEW** (security ∥ perf, then regression ∥ deps) → **PR draft** → COMPLETE
- **Memory** (`.aegis/memory` + `~/.config/aegis/memory`): solved / failure / pattern / global
- Planning **queries memory**; success/failure **writes memory**
- CLI: `aegis memory list|show|query|forget|export|import|add`
- Solve flags: `--skip-reviews`, `--no-memory`

### Review gate 10
- [x] Full pipeline including reviews + PR body (unit + mock e2e)  
- [x] Second similar issue sees memory_hits / memory_hints  
- [x] Parallel security + performance reviews  

---

## Phase 11 — Observability, MCP/plugins, distribution ✅

### What shipped
- **Observability**: `TraceCollector` on event bus → `.aegis/traces/`; cost, latency, tools, prompts, reasoning  
- CLI: `aegis observe list|show|export|latest`  
- **Plugins**: hooks `tool.execute.before/after`, `system.prompt.transform`  
- **MCP**: JSON-RPC client skeleton + `MCPToolBridge` into ToolRegistry (mock transport for tests)  
- **Language matrix**: `docs/LANGUAGE_MATRIX.md` (Python-first honesty)  
- **Benchmark**: `aegis benchmark list|run` with built-in `add_bug` mock task  
- **Packaging**: `Dockerfile`, `.github/workflows/ci.yml`, expanded `aegis doctor`  
- Prometheus/structlog deferred; full Tree-sitter multi-lang deferred  

### Review gate 11
- [x] Session trace export with cost + reasoning  
- [x] Install path + CI workflow documented  
- [x] Honest README / language matrix of what works vs roadmap  

---

# Deferred (by design)

| Item | Until |
|------|--------|
| Full 13 agents | Done in Phases 8–10 |
| Docker sandbox | Phase 9 (local fallback) |
| Qdrant production | Post-v1 (TF-IDF hybrid ships) |
| Multi-language graphs | Post-v1 (see LANGUAGE_MATRIX) |
| SWE-bench leaderboard | Post-v1 (`aegis benchmark` skeleton ships) |
| VS Code / voice / Slack | Future enhancements |
| PyInstaller matrix + Homebrew | Post-v1 |
| Native Gemini provider | Optional small add-on (free AI Studio keys) |
| Prometheus / structlog | Post-v1 (JSON traces ship) |

---

# Defaults & assumptions

| Topic | Default |
|-------|---------|
| First language for intelligence | **Python only** (Phase 6+) |
| LLM path | OpenAI-compatible + Anthropic (Groq free tier works) |
| Early execution | Local process, not Docker |
| GitHub PRs | After local `solve` works |
| Review cadence | After each **phase** (or each block if preferred) |

---

# How we work

1. Implement **one phase** (or agreed block).  
2. Stop for review (diff, how to run, checklist).  
3. On approval → next phase.  
4. No jumping ahead without OK.

---

# Success definition for “v1 usable”

A developer can:

1. Install from source  
2. Configure a provider (e.g. Groq free via `.env`)  
3. `aegis intelligence build` on a Python repo  
4. `aegis solve` a local issue end-to-end with tests  
5. Optionally open a GitHub PR  
6. Inspect cost/reasoning with `aegis observe`  

Everything beyond that is enhancement, not a blocker for the phased v1 path.

---

# Quick commands (current)

```powershell
# Dev setup
cd C:\Projects\AI_Software_Engineer
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"

# Verify
ruff check src tests
pytest -q
aegis doctor
aegis benchmark run
aegis config path

# Run agent (any project dir if global .env set)
aegis run "Summarize the README"

# Solve + inspect
aegis solve "..." --dry-run
aegis observe show latest
aegis memory list

# API server
aegis serve
# open http://127.0.0.1:4096/

# Module entry (same as `aegis`)
python -m aegis doctor
```

**Global API keys (recommended):**  
`C:\Users\<you>\.config\aegis\.env`

**Template:** `.env.example` in this repo.

---

*Last updated: Phase 11 complete + polish; phased v1 path finished. Post-v1: multi-lang, SWE-bench, Prometheus.*
