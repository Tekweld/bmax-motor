# Graph Report - graph  (2026-08-27)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 106 nodes · 134 edges · 19 communities (11 shown, 8 thin omitted)
- Extraction: 99% EXTRACTED · 1% INFERRED · 0% AMBIGUOUS · INFERRED: 1 edges (avg confidence: 0.85)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `c84a26d0`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- enriquecer_cep_zen.py
- enriquecer_por_zen_id.py
- enrich_revendas_bmax.py
- enriquecer_enderecos_bmax.py
- sincronizar_excel_bmax.py
- 01_create_tables.sql
- corrigir_endereco_luitex.py
- geocode_por_cidade.py
- popular_ddd_cobertura.py
- corrigir_banco_bmax.py
- baixar_bsis_sharepoint.py
- criar_usuario_auth.py
- 02_cobertura_bmax.sql
- 03_config_bmax.sql
- 04_schema_updates.sql
- 05_bmax_admins.sql
- importar_cobertura_bmax.py

## God Nodes (most connected - your core abstractions)
1. `main()` - 14 edges
2. `main()` - 10 edges
3. `main()` - 6 edges
4. `main()` - 6 edges
5. `score()` - 5 edges
6. `sb()` - 4 edges
7. `todos_matches()` - 4 edges
8. `upsert_filial()` - 4 edges
9. `upsert_revenda()` - 4 edges
10. `geocode_cep()` - 3 edges

## Surprising Connections (you probably didn't know these)
- `main()` --indirect_call--> `score()`  [INFERRED]
  scripts/corrigir_banco_bmax.py → scripts/enriquecer_cep_zen.py

## Import Cycles
- None detected.

## Communities (19 total, 8 thin omitted)

### Community 0 - "enriquecer_cep_zen.py"
Cohesion: 0.21
Nodes (18): fmt_cep(), fmt_end(), geocode_cep(), hash_lista(), hash_salvo(), main(), nominatim(), norm() (+10 more)

### Community 1 - "enriquecer_por_zen_id.py"
Cohesion: 0.23
Nodes (14): fmt_cep(), fmt_end(), geocode(), main(), nominatim(), enriquecer_por_zen_id.py Atualiza as 8 revendas do BMAX CRITERIOS.xlsx que têm…, Busca revenda no ZEN diretamente por ID., Autentica como usuário admin e retorna JWT access token. (+6 more)

### Community 2 - "enrich_revendas_bmax.py"
Cohesion: 0.27
Nodes (11): geocode(), lista_hash(), main(), nominatim(), enrich_revendas_bmax.py Sincroniza revendas BMax: ZEN API → geocodificação →…, Upsert via nome+cidade como chave de negócio., Retorna lista de cadastros ZEN que correspondem à revenda., sb() (+3 more)

### Community 3 - "enriquecer_enderecos_bmax.py"
Cohesion: 0.29
Nodes (4): norm(), norm_cidade(), Enriquece todos os registros de comercial_revendas_bmax que estão sem zen_id ou…, Normaliza nome para matching: uppercase, sem acento, só alfanum+espaço.

### Community 4 - "sincronizar_excel_bmax.py"
Cohesion: 0.43
Nodes (7): baixar_excel(), geocodificar(), get_graph_token(), main(), parsear_excel(), sincronizar_excel_bmax.py Sincronização automática: BMAX CRITERIOS.xlsx…, sb()

### Community 5 - "01_create_tables.sql"
Cohesion: 0.33
Nodes (6): comercial_bmax_classificacoes, comercial_bmax_config, comercial_revendas_bmax, log_alteracoes, set_atualizado_em(), trg_bmax_rev_updated

### Community 7 - "geocode_por_cidade.py"
Cohesion: 0.50
Nodes (4): main(), nominatim(), geocode_por_cidade.py Geocodifica revendas sem lat/lng usando cidade/estado via…, Retorna (lat, lng) ou None.

### Community 8 - "popular_ddd_cobertura.py"
Cohesion: 0.60
Nodes (4): load_cobertura(), main(), norm(), popular_ddd_cobertura.py Popula a coluna ddd na tabela comercial_bmax_cobertura…

### Community 9 - "corrigir_banco_bmax.py"
Cohesion: 0.67
Nodes (3): main(), corrigir_banco_bmax.py Sincroniza classe e rep de TODAS as revendas do banco…, sb()

## Knowledge Gaps
- **8 isolated node(s):** `comercial_bmax_cobertura`, `comercial_bmax_config`, `comercial_bmax_vendedores`, `comercial_bmax_admins`, `comercial_bmax_classificacoes` (+3 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **8 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `score()` connect `enriquecer_cep_zen.py` to `corrigir_banco_bmax.py`?**
  _High betweenness centrality (0.013) - this node is a cross-community bridge._
- **Why does `main()` connect `corrigir_banco_bmax.py` to `enriquecer_cep_zen.py`?**
  _High betweenness centrality (0.010) - this node is a cross-community bridge._
- **What connects `comercial_bmax_cobertura`, `comercial_bmax_config`, `comercial_bmax_vendedores` to the rest of the system?**
  _8 weakly-connected nodes found - possible documentation gaps or missing edges._