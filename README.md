# Aegis Engineer

Autonomous software engineering platform with a **Repository Intelligence Engine**.

Aegis understands codebases through AST analysis, call graphs, dependency graphs, LSP integration, and semantic search — then uses that understanding to analyze issues, plan implementations, generate code, run tests, and open pull requests.

> **Status:** Phase 0 foundation. The CLI is installable; agent pipeline, intelligence engine, and full workflow are built in later phases.

## Requirements

- Python 3.12+
- Windows, macOS, or Linux

## Install from source

```bash
# Clone / open the repository
cd AI_Software_Engineer

# Create a virtual environment (recommended)
python -m venv .venv

# Activate (Windows PowerShell)
.venv\Scripts\Activate.ps1

# Activate (macOS / Linux)
# source .venv/bin/activate

# Editable install with dev tools
pip install -e ".[dev]"
```

## Quick checks

```bash
aegis version
aegis version --json
aegis doctor
aegis doctor --verbose
```

## Configuration (Phase 1)

```bash
aegis config list
aegis config list --json
aegis config set provider.default openai
aegis config set provider.model gpt-4o
aegis config set server.port 4096
aegis config unset provider.model
aegis config path
```

Hierarchy (later wins): **defaults → user** (`~/.config/aegis/config.json`) **→ project** (`.aegis/config.json` or `.aegis.json`) **→ env** (`AEGIS_PROVIDER`, `AEGIS_MODEL`, `AEGIS_DB_PATH`, …).

## Sessions

```bash
aegis session create --title "Fix auth"
aegis session list
aegis session show <session-id>
aegis session export <session-id> -o session.json
aegis session delete <session-id> --yes
```

## Development

```bash
# Run tests
pytest

# Lint
ruff check src tests

# Type check (optional)
mypy
```

## Project layout

```text
src/aegis/          # Main package
  cli/              # Typer CLI (version, doctor, config, session, …)
  config/           # Hierarchical configuration
  db/               # SQLite models + migrations
  session/          # Session CRUD
tests/              # pytest suite
pyproject.toml      # Package metadata and tool config
```

## Roadmap (phased)

| Phase | Focus |
|-------|--------|
| 0 | Project foundation |
| 1 | Config + SQLite storage (you are here) |
| 2 | Tools + permissions |
| 3 | LLM providers + agent loop |
| 4 | HTTP server + SSE |
| 5 | Minimal TUI |
| 6–7 | Repository Intelligence Engine |
| 8–10 | Multi-agent orchestration, GitHub, memory |
| 11 | Observability, plugins, packaging |

See `AI_Software_Engineer_Project_Blueprint.md` for the full product design.

## License

MIT
