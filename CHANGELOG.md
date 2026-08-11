# Changelog

## 0.1.0 — Phased v1

First installable release covering the phased roadmap (Phases 0–11).

### Capabilities

- **CLI / TUI**: `aegis`, `run`, `serve`, `tui`, `doctor`, `config`, `session`
- **Solve pipeline**: classify → plan → retrieve → code ⇄ analyze/test → reviews → PR draft
- **Isolation**: git worktree, file snapshot, Docker sandbox with local fallback
- **GitHub**: issue fetch (`url` / `owner/repo#N`), optional `--create-pr`
- **Intelligence** (Python): AST graphs, call resolution, hybrid TF-IDF search
- **Memory**: repo + global stores; plan-time query; success/failure write
- **Observability**: session traces under `.aegis/traces/`; `aegis observe`
- **Plugins**: tool/prompt hooks; MCP tool bridge skeleton
- **Quality**: `aegis test` gate, `document`, `benchmark run` (mock `add_bug`)
- **Packaging**: `Dockerfile`, GitHub Actions CI, `python -m aegis`, MIT license

### Not in v1 (post-v1)

- Multi-language Tree-sitter graphs (see `docs/LANGUAGE_MATRIX.md`)
- SWE-bench leaderboard, Prometheus metrics, PyInstaller matrix
- Native Gemini provider, VS Code / Slack integrations
