"""
corrigir_banco_bmax.py
Sincroniza classe e rep de TODAS as revendas do banco com revendas_lista.json.
Remove duplicatas (mesmo nome+cidade, mantém o registro com melhor coordenada).

Env vars: SUPABASE_URL, SUPABASE_SERVICE_KEY
"""

import os, sys, json, requests
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / ".env")
except ImportError:
    pass

SB_URL = os.environ["SUPABASE_URL"]
SB_KEY = os.environ["SUPABASE_SERVICE_KEY"]


def sb(path, method="GET", body=None, params=None):
    hdrs = {
        "apikey": SB_KEY,
        "Authorization": f"Bearer {SB_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation" if method == "POST" else "return=minimal" if method in ("PATCH", "DELETE") else "",
    }
    r = requests.request(method, SB_URL.rstrip("/") + "/rest/v1" + path,
                         headers=hdrs, json=body, params=params, timeout=20)
    if not r.ok:
        raise RuntimeError(f"Supabase {method} {path} → {r.status_code}: {r.text[:300]}")
    return r.json() if method == "GET" else r


def main():
    lista_path = Path(__file__).parent.parent / "revendas_lista.json"
    lista_raw = json.loads(lista_path.read_text(encoding="utf-8"))
    lista = lista_raw["revendas"]

    # Índice da lista por nome (normalizado)
    lista_idx = {r["nome"].strip().upper(): r for r in lista}

    # Carrega TODAS as revendas do banco (ativas e inativas)
    todas = sb("/comercial_revendas_bmax?select=id,nome,cidade,estado,classe,rep,lat,lng,ativo")
    print(f"Revendas no banco: {len(todas)}\n")

    atualizadas = 0
    deletadas = 0

    # ── 1. Corrigir classe e rep conforme lista ──────────────────────────────
    print("=== Verificando classe/rep de cada revenda ===")
    for rev in todas:
        chave = rev["nome"].strip().upper()
        ref = lista_idx.get(chave)
        if not ref:
            # Filiais (mesmo nome, cidades diferentes) — herdam classe do registro-pai
            # Busca por prefixo do nome
            nome_base = rev["nome"].strip().upper()
            for k, v in lista_idx.items():
                if k == nome_base:
                    ref = v
                    break

        if not ref:
            print(f"  [?] {rev['nome']} ({rev['cidade']}) — não encontrado na lista, ignorando")
            continue

        alteracoes = {}
        if rev["classe"] != ref["classe"]:
            alteracoes["classe"] = ref["classe"]
        if rev["rep"] != ref.get("rep"):
            alteracoes["rep"] = ref.get("rep")

        if alteracoes:
            sb(f"/comercial_revendas_bmax?id=eq.{rev['id']}", "PATCH", alteracoes)
            campos = ", ".join(f"{k}: {rev.get(k)!r} → {v!r}" for k, v in alteracoes.items())
            print(f"  ✓ {rev['nome']} ({rev['cidade']}/{rev['estado']}) | {campos}")
            atualizadas += 1
        else:
            print(f"  = {rev['nome']} ({rev['cidade']}/{rev['estado']}) — ok")

    # ── 2. Remover duplicatas (mesmo nome+cidade) ────────────────────────────
    print("\n=== Verificando duplicatas (mesmo nome+cidade) ===")
    from collections import defaultdict
    grupos = defaultdict(list)
    for rev in todas:
        chave = (rev["nome"].strip().upper(), (rev["cidade"] or "").strip().upper())
        grupos[chave].append(rev)

    for chave, grupo in grupos.items():
        if len(grupo) <= 1:
            continue
        nome, cidade = chave
        print(f"\n  Duplicata detectada: {nome} / {cidade} ({len(grupo)} registros)")

        # Ordena: prioriza registros com lat/lng válidos, depois ativo=True
        def score(r):
            has_coords = 1 if (r.get("lat") and r.get("lng")) else 0
            is_active = 1 if r.get("ativo") else 0
            return (has_coords, is_active)

        grupo_ord = sorted(grupo, key=score, reverse=True)
        manter = grupo_ord[0]
        deletar = grupo_ord[1:]

        print(f"    Mantendo:  id={manter['id'][:8]} lat={manter.get('lat')} ativo={manter.get('ativo')}")
        for d in deletar:
            print(f"    Deletando: id={d['id'][:8]} lat={d.get('lat')} ativo={d.get('ativo')}")
            sb(f"/comercial_revendas_bmax?id=eq.{d['id']}", "DELETE")
            deletadas += 1

    # ── Resumo ───────────────────────────────────────────────────────────────
    print(f"\n=== Resultado ===")
    print(f"  Registros atualizados (classe/rep): {atualizadas}")
    print(f"  Duplicatas deletadas:               {deletadas}")
    print("  Concluído.")


if __name__ == "__main__":
    main()
