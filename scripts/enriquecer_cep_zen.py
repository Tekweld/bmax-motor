"""
enriquecer_cep_zen.py
Busca o CEP de cada revenda no ZEN via /catalog/person/person
e atualiza a tabela comercial_revendas_bmax no Supabase.

Uso:
  python scripts/enriquecer_cep_zen.py             # só revendas sem CEP
  python scripts/enriquecer_cep_zen.py --force     # reprocessa todas

Env vars (.env ou GitHub Secrets):
  ZEN_EMAIL, ZEN_SENHA
  SUPABASE_URL, SUPABASE_SERVICE_KEY
"""

import os, sys, time, argparse, unicodedata, requests
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / ".env")
except ImportError:
    pass

ZEN_EMAIL = os.environ["ZEN_EMAIL"]
ZEN_SENHA = os.environ["ZEN_SENHA"]
SB_URL    = os.environ["SUPABASE_URL"]
SB_KEY    = os.environ["SUPABASE_SERVICE_KEY"]

ZEN_BASE  = "https://api.zenerp.app.br"


# ── helpers ────────────────────────────────────────────────────
def norm(s: str) -> str:
    """Normaliza string: minúsculo, sem acento, sem pontuação."""
    s = s.lower().strip()
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return s


def fmt_cep(cep: str) -> str:
    d = "".join(c for c in (cep or "") if c.isdigit())
    return d if len(d) == 8 else ""


def sb(path, method="GET", body=None, params=None):
    hdrs = {
        "apikey": SB_KEY,
        "Authorization": f"Bearer {SB_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal" if method in ("PATCH",) else "return=representation",
    }
    r = requests.request(method, SB_URL.rstrip("/") + "/rest/v1" + path,
                         headers=hdrs, json=body, params=params, timeout=20)
    if not r.ok:
        raise RuntimeError(f"Supabase {method} {path} → {r.status_code}: {r.text[:300]}")
    return r.json() if method == "GET" else r


def zen_headers() -> dict:
    r = requests.post(
        f"{ZEN_BASE}/system/security/tokenOpRequest",
        headers={"tenant": "boxer"},
        json={"email": ZEN_EMAIL, "password": ZEN_SENHA},
        timeout=15,
    )
    r.raise_for_status()
    token = r.text.strip().strip('"')
    return {"Authorization": f"Bearer {token}", "tenant": "boxer"}


def zen_buscar_todos(hdrs: dict, termo: str) -> list[dict]:
    """Busca em /catalog/person/person com paginação completa."""
    page, todos = 1, []
    while True:
        r = requests.get(f"{ZEN_BASE}/catalog/person/person",
                         headers=hdrs,
                         params={"search": termo, "limit": 100, "page": page, "tenant": "boxer"},
                         timeout=15)
        if not r.ok:
            break
        data = r.json()
        items = data if isinstance(data, list) else data.get("items", data.get("data", []))
        if not items:
            break
        todos.extend(items)
        # Para se vier menos que o limite (última página)
        if len(items) < 100:
            break
        page += 1
        time.sleep(0.3)
    return todos


def score_match(item: dict, nome_rev: str, cidade_rev: str) -> int:
    """
    Pontua o quanto um cadastro ZEN bate com a revenda.
    Maior = melhor.
    """
    fn  = norm(item.get("fantasyName") or item.get("name") or "")
    cn  = norm(item.get("city") or "")
    nr  = norm(nome_rev)
    cr  = norm(cidade_rev)

    score = 0

    # Nome: match exato
    if fn == nr:
        score += 100
    # Nome: contém
    elif nr in fn or fn in nr:
        score += 60
    # Palavras em comum
    else:
        palavras_rev = set(nr.split())
        palavras_zen = set(fn.split())
        comuns = palavras_rev & palavras_zen
        # Ignora palavras muito curtas ou genéricas
        comuns = {p for p in comuns if len(p) > 2 and p not in
                  {"ltda","eireli","me","sa","epp","com","de","da","do","dos","das","e"}}
        score += len(comuns) * 20

    # Cidade: match parcial (primeiros 5 chars)
    if cr and cn:
        if cn[:5] == cr[:5]:
            score += 40
        elif cr[:4] in cn or cn[:4] in cr:
            score += 20

    return score


def melhor_match(items: list[dict], nome_rev: str, cidade_rev: str,
                 min_score: int = 40) -> dict | None:
    melhor, melhor_score = None, 0
    for item in items:
        s = score_match(item, nome_rev, cidade_rev)
        if s > melhor_score:
            melhor_score, melhor = s, item
    if melhor_score >= min_score:
        return melhor
    return None


# ── main ───────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true",
                        help="Reprocessa mesmo revendas que já têm CEP")
    args = parser.parse_args()

    # 1. Carregar revendas do Supabase
    filtro = "/comercial_revendas_bmax?select=id,nome,cidade,estado,cep,ativo"
    if not args.force:
        filtro += "&cep=is.null&ativo=eq.true"
    else:
        filtro += "&ativo=eq.true"

    revendas = sb(filtro)
    print(f"Revendas a processar: {len(revendas)}\n")
    if not revendas:
        print("Nada a fazer.")
        return

    # 2. Autenticar ZEN
    print("Autenticando no ZEN...")
    hdrs_zen = zen_headers()
    print("Token obtido.\n")

    achou = 0
    nao_achou = []

    for i, rev in enumerate(revendas, 1):
        nome   = rev["nome"]
        cidade = rev.get("cidade") or ""
        estado = rev.get("estado") or ""
        print(f"[{i:02d}/{len(revendas):02d}] {nome} — {cidade}/{estado}")

        # Estratégias de busca em ordem crescente de abrangência
        termos = []
        palavras = [p for p in nome.split()
                    if len(p) > 2 and p.upper() not in
                    ("LTDA","EIRELI","S.A","SA","ME","EPP","COM","DE","DA","DO","DOS","DAS")]
        if palavras:
            termos.append(palavras[0])            # primeira palavra significativa
        if len(palavras) > 1:
            termos.append(" ".join(palavras[:2])) # duas primeiras palavras
        if cidade:
            termos.append(cidade.split()[0])      # cidade como fallback

        candidatos = []
        for termo in termos:
            items = zen_buscar_todos(hdrs_zen, termo)
            candidatos.extend(items)
            time.sleep(0.2)

        # Remove duplicatas por id
        seen = set()
        unicos = []
        for item in candidatos:
            rid = item.get("id")
            if rid not in seen:
                seen.add(rid)
                unicos.append(item)

        match = melhor_match(unicos, nome, cidade)

        if match:
            cep_raw = fmt_cep(match.get("zipcode") or "")
            zen_nome = (match.get("fantasyName") or match.get("name") or "")[:50]
            zen_cidade = match.get("city") or ""
            score = score_match(match, nome, cidade)

            if cep_raw:
                sb(f"/comercial_revendas_bmax?id=eq.{rev['id']}", "PATCH",
                   {"cep": cep_raw, "zen_id": str(match.get("id") or "")})
                print(f"   ✓ CEP {cep_raw[:5]}-{cep_raw[5:]} | ZEN: {zen_nome} ({zen_cidade}) score={score}")
                achou += 1
            else:
                print(f"   ~ Match sem CEP: {zen_nome} ({zen_cidade}) score={score}")
                nao_achou.append(f"{nome} — match sem CEP no ZEN")
        else:
            print(f"   ✗ Não encontrado ({len(unicos)} candidatos)")
            nao_achou.append(nome)

        time.sleep(0.3)

    print(f"\n=== Resultado ===")
    print(f"  CEP encontrado: {achou}")
    print(f"  Sem match:      {len(nao_achou)}")
    if nao_achou:
        print("  Lista sem match:")
        for n in nao_achou:
            print(f"    • {n}")


if __name__ == "__main__":
    main()
