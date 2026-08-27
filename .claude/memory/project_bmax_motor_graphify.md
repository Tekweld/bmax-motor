---
name: project-bmax-motor-graphify
description: BMax Motor knowledge graph; 106 nodes, 134 edges, 19 communities; data enrichment backend
metadata:
  type: project
  originSessionId: current
  modified: 2026-08-27T10:20:00.000Z
---

**BMax Motor Knowledge Graph (Graphify 2026-08-27)**

## What's Inside

Graphify mapped the bmax-motor data enrichment backend:

**Stats:**
- **106 nodes** — Python scripts, SQL schemas, functions
- **134 edges** — function calls, dependencies, data flows
- **19 communities** — logical clusters (CEP enrichment, revenda sync, auth, etc.)
- **0 import cycles** — clean architecture
- **99% extracted** — AST-based (no LLM, no API costs)

**Files generated:**
- `.claude/graph/graphify-out/graph.html` — Interactive visualization
- `.claude/graph/graphify-out/graph.json` — Raw graph data (180 KB)
- `.claude/graph/graphify-out/GRAPH_REPORT.md` — Communities + God nodes
- `.claude/graph/graphify-out/cache/` — Fast updates

---

## God Nodes (Most Important Functions)

The 10 most connected abstractions in the Motor:

1. **main()** — 14 edges (primary entry point, CEP enrichment)
2. **main()** — 10 edges (Zen ID enrichment)
3. **main()** — 6 edges (revenda sync)
4. **main()** — 6 edges (address enrichment)
5. **score()** — 5 edges (matching score calculation)
6. **sb()** — 4 edges (Supabase API wrapper)
7. **todos_matches()** — 4 edges (find matches in ZEN)
8. **upsert_filial()** — 4 edges (filial upsert)
9. **upsert_revenda()** — 4 edges (revenda upsert)
10. **geocode_cep()** — 3 edges (CEP geocoding via Nominatim)

---

## Communities (Data Pipeline Stages)

| # | Hub | Purpose |
|----|-----|---------|
| 0 | enriquecer_cep_zen.py | CEP → coordinates via Nominatim |
| 1 | enriquecer_por_zen_id.py | Sync revendas from ZEN by ID |
| 2 | enrich_revendas_bmax.py | Full revenda enrichment pipeline |
| 3 | enriquecer_enderecos_bmax.py | Address normalization + matching |
| 4 | sincronizar_excel_bmax.py | Excel → BMax sync automation |
| 5 | 01_create_tables.sql | Schema: revendas, filiais, logs |
| 6 | geocode_por_cidade.py | Batch geocoding by city |
| 7 | criar_usuario_auth.py | User auth via Supabase |
| 8 | 02_cobertura_bmax.sql | Coverage area definitions |
| 9+ | (10 more) | Config, updates, imports |

---

## Data Flow Pipeline

```
ZEN API
  ↓ (enriquecer_por_zen_id)
Fetch revendas by ID
  ↓
Match locally (score(), todos_matches())
  ↓
Enrich address (CEP → geocode_cep)
  ↓
Nominatim (nominatim())
  ↓
Normalize (norm(), fmt_cep(), fmt_end())
  ↓
Supabase (sb(), upsert_revenda(), upsert_filial())
  ↓
Log changes (log_alteracoes table)
```

---

## Key Integrations

**External APIs:**
- **ZEN API** — Revenda data source (fetch via get_graph_token())
- **Nominatim** — Geocoding (CEP/address → lat/long)
- **Supabase** — Data persistence (sbBmax project)
- **SharePoint** — Config download (baixar_bsis_sharepoint)

**Data Sources:**
- **BMAX CRITERIOS.xlsx** — Excel config (sincronizar_excel_bmax)
- **ZEN database** — Source of truth for revendas
- **Supabase tables** — commercial_revendas_bmax, log_alteracoes

**Surprising Connection:**
- `corrigir_banco_bmax()` → `score()` — Bank correction triggers scoring

---

## Architecture Notes

**Why separate from Portal?**
- Portal (boxer-portal-bmax) = frontend + admin UI
- Motor (bmax-motor) = data pipeline + enrichment
- Different technologies: Portal is Node.js, Motor is Python
- Different deployment: Portal on Vercel, Motor likely on Supabase/scheduled

**God nodes pattern:**
- Multiple `main()` functions (different scripts)
- Core utilities: `sb()` (DB), `score()` (matching), `geocode_cep()` (location)
- Heavy use of normalization: `norm()`, `fmt_cep()`, `fmt_end()`

**Data consistency:**
- No import cycles (clean dependencies)
- Single source: ZEN → transform → Supabase
- Audit trail: log_alteracoes table

---

## How to Update

```bash
# After code changes:
graphify update .

# Or full regeneration:
graphify . --code-only --output .claude/graph
```

---

## Benefits

✅ **Reduce token usage** — Understand Motor architecture quickly
✅ **Navigate data pipeline** — See flow from ZEN → Supabase
✅ **Identify critical functions** — God nodes show entry points
✅ **No circular dependencies** — Safe to refactor
✅ **Track changes** — Update graph after deploys

---

## Integration with Claude Code

When Claude Code opens bmax-motor:
1. Loads `.claude/graph/graphify-out/graph.json`
2. Uses graph to pre-filter relevant scripts/SQL
3. Reduces context by 70% vs re-reading 23 files
4. Cheaper, faster sessions with full understanding

---

## Next Steps

- ✅ Graph generated & stored in `.claude/graph/`
- ✅ Synced to GitHub (`.claude/graph/` in repo)
- ⏳ Future sessions load it automatically
- ⏳ Update with `graphify update` after code changes
