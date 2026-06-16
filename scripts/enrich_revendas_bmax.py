"""
enrich_revendas_bmax.py
Sincroniza revendas BMax: ZEN API → geocodificação → Supabase.

Uso:
  python scripts/enrich_revendas_bmax.py            # só roda se lista mudou
  python scripts/enrich_revendas_bmax.py --force    # força atualização total

Env vars necessárias (.env ou GitHub Secrets):
  ZEN_EMAIL, ZEN_SENHA
  SUPABASE_URL, SUPABASE_SERVICE_KEY
"""

import os, sys, json, hashlib, time, argparse
import requests
from pathlib import Path

# ── carrega .env se existir ────────────────────────────────
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / ".env")
except ImportError:
    pass

ZEN_EMAIL  = os.environ["ZEN_EMAIL"]
ZEN_SENHA  = os.environ["ZEN_SENHA"]
SB_URL     = os.environ["SUPABASE_URL"]
SB_KEY     = os.environ["SUPABASE_SERVICE_KEY"]   # service_role — nunca no frontend
FORCE      = os.getenv("FORCE_UPDATE", "").lower() in ("1", "true", "yes")

ZEN_BASE   = "https://api.zenerp.app.br"
LISTA_PATH = Path(__file__).parent.parent / "revendas_lista.json"
HASH_PATH  = Path(__file__).parent.parent / ".revendas_hash"


# ── helpers Supabase REST ──────────────────────────────────
def sb(path: str, method="GET", body=None):
    hdrs = {
        "apikey": SB_KEY,
        "Authorization": f"Bearer {SB_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation" if method == "POST" else
                  "return=minimal"         if method in ("PATCH","PUT") else "",
    }
    url  = SB_URL.rstrip("/") + "/rest/v1" + path
    resp = requests.request(method, url, headers=hdrs,
                            json=body, timeout=20)
    if not resp.ok:
        raise RuntimeError(f"Supabase {method} {path} → {resp.status_code}: {resp.text[:300]}")
    return resp.json() if method in ("GET","POST") else resp


# ── autenticação ZEN ───────────────────────────────────────
def zen_token() -> str:
    r = requests.post(
        f"{ZEN_BASE}/system/security/tokenOpRequest",
        headers={"tenant": "boxer"},
        json={"email": ZEN_EMAIL, "password": ZEN_SENHA},
        timeout=15,
    )
    r.raise_for_status()
    return r.text.strip().strip('"')


# ── busca revenda no ZEN por nome + cidade ─────────────────
def zen_buscar(token: str, nome: str, cidade: str) -> list[dict]:
    """Retorna lista de cadastros ZEN que correspondem à revenda."""
    hdrs = {"Authorization": f"Bearer {token}"}
    params = {
        "search": nome.split()[0],   # primeira palavra como busca
        "limit": 50,
    }
    r = requests.get(f"{ZEN_BASE}/catalog/person/person",
                     headers=hdrs, params=params, timeout=15)
    if not r.ok:
        return []
    items = r.json() if isinstance(r.json(), list) else r.json().get("items", [])

    # Filtra por nome (match parcial) e cidade
    cidade_norm = cidade.lower().strip()
    matches = []
    for item in items:
        fn = (item.get("fantasyName") or item.get("name") or "").lower()
        cn = (item.get("city") or "").lower().strip()
        if (nome.split()[0].lower() in fn or fn in nome.lower()) and \
           (cidade_norm[:6] in cn or cn[:6] in cidade_norm[:6]):
            matches.append(item)

    # Fallback: qualquer match de nome se não achou pela cidade
    if not matches:
        for item in items:
            fn = (item.get("fantasyName") or item.get("name") or "").lower()
            if nome.split()[0].lower() in fn:
                matches.append(item)

    return matches[:5]


# ── geocodificação BrasilAPI → ViaCEP → Nominatim ─────────
def geocode(cep: str) -> dict | None:
    cep = cep.replace("-", "").strip()
    if len(cep) != 8:
        return None

    # Camada 1: BrasilAPI v2
    try:
        r = requests.get(f"https://brasilapi.com.br/api/cep/v2/{cep}", timeout=8)
        if r.ok:
            d = r.json()
            coords = d.get("location", {}).get("coordinates", {})
            lat = coords.get("latitude")
            lng = coords.get("longitude")
            city  = d.get("city")
            state = d.get("state")
            if lat and lng:
                return {"lat": float(lat), "lng": float(lng),
                        "cidade": city, "estado": state}
            if city:
                # tenta Nominatim com cidade
                coords2 = nominatim(f"{city} {state} Brasil")
                if coords2:
                    return {**coords2, "cidade": city, "estado": state}
    except Exception:
        pass

    # Camada 2: ViaCEP
    try:
        r = requests.get(f"https://viacep.com.br/ws/{cep}/json/", timeout=8)
        if r.ok:
            d = r.json()
            if not d.get("erro"):
                city  = d.get("localidade")
                state = d.get("uf")
                coords2 = nominatim(f"{d.get('logradouro','')} {city} {state} Brasil")
                if coords2:
                    return {**coords2, "cidade": city, "estado": state}
                coords2 = nominatim(f"{city} {state} Brasil")
                if coords2:
                    return {**coords2, "cidade": city, "estado": state}
    except Exception:
        pass

    return None


def nominatim(query: str) -> dict | None:
    time.sleep(1.1)   # respeita rate limit 1 req/s
    try:
        r = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": query, "format": "json", "limit": 1, "countrycodes": "br"},
            headers={"User-Agent": "BMaxMotorPCI/1.0 (boxersoldas.com.br)"},
            timeout=10
        )
        if r.ok and r.json():
            item = r.json()[0]
            return {"lat": float(item["lat"]), "lng": float(item["lon"])}
    except Exception:
        pass
    return None


# ── calcula hash da lista ──────────────────────────────────
def lista_hash(lista: list) -> str:
    s = json.dumps(lista, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(s.encode()).hexdigest()[:16]


# ── upsert no Supabase ─────────────────────────────────────
def upsert_revenda(rev: dict):
    """Upsert via nome+cidade como chave de negócio."""
    existing = sb(
        f"/comercial_revendas_bmax?nome=eq.{requests.utils.quote(rev['nome'])}"
        f"&cidade=eq.{requests.utils.quote(rev['cidade'])}",
        "GET"
    )
    if existing:
        rid = existing[0]["id"]
        sb(f"/comercial_revendas_bmax?id=eq.{rid}", "PATCH", rev)
        print(f"  ↻ atualizado: {rev['nome']} — {rev['cidade']}")
    else:
        sb("/comercial_revendas_bmax", "POST", rev)
        print(f"  ✚ inserido:   {rev['nome']} — {rev['cidade']}")


# ── main ───────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", default=FORCE)
    args = parser.parse_args()

    lista_data = json.loads(LISTA_PATH.read_text(encoding="utf-8"))
    lista = lista_data["revendas"]
    h = lista_hash(lista)

    # Verifica se a lista mudou
    prev_hash = HASH_PATH.read_text().strip() if HASH_PATH.exists() else ""
    if h == prev_hash and not args.force:
        print(f"✓ Lista não mudou (hash={h}) — nada a sincronizar.")
        print("  Use --force para forçar atualização.")
        return

    print(f"🔄 Lista mudou (hash {prev_hash} → {h}). Iniciando sincronização...")
    print(f"   Total: {len(lista)} revendas")

    # Autentica no ZEN
    print("\n1. Autenticando no ZEN...")
    try:
        token = zen_token()
        print("   ✓ Token ZEN obtido")
    except Exception as e:
        print(f"   ✗ Falha ZEN auth: {e}")
        token = None

    erros = []
    for i, rev in enumerate(lista, 1):
        print(f"\n[{i:02d}/{len(lista):02d}] {rev['nome']} — {rev['cidade']}/{rev['estado']}")
        cep  = None
        zen_id = None
        nome_fantasia = None

        # Busca CEP no ZEN
        if token:
            try:
                matches = zen_buscar(token, rev["nome"], rev["cidade"])
                if matches:
                    best = matches[0]
                    cep  = (best.get("zipcode") or "").replace("-", "").strip()
                    zen_id = str(best.get("id") or "")
                    nome_fantasia = best.get("fantasyName") or best.get("name")
                    print(f"   ZEN: {nome_fantasia} | CEP={cep} | id={zen_id}")
                    if len(matches) > 1:
                        print(f"   ℹ  {len(matches)} cadastros encontrados — usando o primeiro")
                else:
                    print("   ⚠  Não encontrado no ZEN — sem CEP")
            except Exception as e:
                print(f"   ✗ Erro ZEN: {e}")
                erros.append({"rev": rev["nome"], "erro": str(e)})

        # Geocodifica
        coords = None
        if cep:
            coords = geocode(cep)
            if coords:
                print(f"   Geo: {coords['lat']:.5f}, {coords['lng']:.5f}")
            else:
                print("   ⚠  Geocodificação falhou")

        # Monta registro
        registro = {
            "nome":          rev["nome"],
            "nome_fantasia": nome_fantasia,
            "rep":           rev.get("rep"),
            "cidade":        coords.get("cidade") or rev.get("cidade") if coords else rev.get("cidade"),
            "estado":        coords.get("estado") or rev.get("estado") if coords else rev.get("estado"),
            "cep":           cep,
            "lat":           coords.get("lat") if coords else None,
            "lng":           coords.get("lng") if coords else None,
            "classe":        rev.get("classe", "Prata"),
            "zen_id":        zen_id,
            "zen_group":     None,
            "ativo":         True,
        }

        try:
            upsert_revenda(registro)
        except Exception as e:
            print(f"   ✗ Erro Supabase: {e}")
            erros.append({"rev": rev["nome"], "erro": str(e)})

        time.sleep(0.3)  # evita flood

    # Atualiza hash
    HASH_PATH.write_text(h)
    print(f"\n✅ Sincronização concluída. Hash salvo: {h}")
    if erros:
        print(f"\n⚠  {len(erros)} erro(s):")
        for e in erros:
            print(f"   • {e['rev']}: {e['erro']}")
        sys.exit(1)


if __name__ == "__main__":
    main()
