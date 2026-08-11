# Language support matrix

Honest status of Repository Intelligence and solve tooling per language.

| Language | AST / symbols | Import graph | Call graph | Hybrid search | Solve agents | Notes |
|----------|---------------|--------------|------------|---------------|--------------|-------|
| **Python** | ✅ stdlib `ast` | ✅ | ✅ (resolved) | ✅ TF-IDF | ✅ | Primary target |
| JavaScript | ⬜ planned | ⬜ | ⬜ | partial keyword | partial | Tree-sitter later |
| TypeScript | ⬜ planned | ⬜ | ⬜ | partial keyword | partial | Tree-sitter later |
| Go | ⬜ | ⬜ | ⬜ | — | — | Phase 11.3+ |
| Rust | ⬜ | ⬜ | ⬜ | — | — | Phase 11.3+ |
| Other | — | — | — | grep/read tools only | text-only | No graph intelligence |

## What works today without graphs

Even for non-Python repos you can still:

- `aegis run` / TUI with read/grep/glob/edit tools  
- `aegis solve` (LLM-driven; quality depends on tests present)  
- Quality gate (`aegis test`) if pytest/ruff apply  

## Multi-language roadmap

1. Tree-sitter grammars for JS/TS  
2. Shared symbol index format  
3. Call graph heuristics per language  
4. Optional LSP enrichment  

Until then, treat intelligence CLI as **Python-first**.
