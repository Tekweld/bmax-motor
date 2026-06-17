"""
enriquecer_cep_zen.py
Busca TODAS as filiais de cada revenda no ZEN e sincroniza com o Supabase.

Lógica:
  - Itera revendas_lista.json (fonte de verdade)
  - Para cada revenda, busca no ZEN e pega TODOS os matches válidos (não só o melhor)
  - Cada match ZEN = uma entrada no banco (filiais incluídas)
  - Preenche CEP, endereço, cidade, estado direto do ZEN
  - Geocodifica por CEP (BrasilAPI → ViaCEP → Nominatim fallback)
  - Upsert por zen_id: atualiza se já existe, insere se é filial nova

Uso:
  python scripts/enriquecer_cep_zen.py             # só revendas sem zen_id
  python scripts/enriquecer_cep_zen.py --force     # reprocessa todas

Env vars (.env ou GitHub Secrets):
  ZEN_EMAIL, ZEN_SENHA
  SUPABASE_URL, SUPABASE_SERVICE_KEY
"""

import os, sys, time, argparse, unicodedata, hashlib, requests
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
LISTA_PATH = Path(__file__).parent.parent / "revendas_lista.json"


# ── helpers gerais ──────────────────────────────────────────────
def norm(s: str) -> str:
    s = s.lower().strip()
    s = unicodedata.normalize("NFD", s)
    return "".join(c for c in s if unicodedata.category(c) != "Mn")

def fmt_cep(cep) -> str:
    d = "".join(c for c in (cep or "") if c.isdigit())
    return d if len(d) == 8 else ""

def fmt_end(item: dict) -> str:
    partes = [
        item.get("address") or item.get("street") or "",
        item.get("number") or "",
        item.get("neighborhood") or item.get("district") or "",
    ]
    return ", ".join(p for p in partes if p).strip(", ")


# ── Supabase ────────────────────────────────────────────────────
def sb(path, method="GET", body=None, params=None):
    hdrs = {
        "apikey": SB_KEY,
        "Authorization": f"Bearer {SB_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation" if method == "GET" else "return=minimal",
    }
    r = requests.request(method, SB_URL.rstrip("/") + "/rest/v1" + path,
                         headers=hdrs, json=body, params=params, timeout=20)
    if not r.ok:
        raise RuntimeError(f"Supabase {method} {path} → {r.status_code}: {r.text[:300]}")
    return r.json() if method == "GET" else r


# ── ZEN ─────────────────────────────────────────────────────────
def zen_auth() -> dict:
    r = requests.post(
        f"{ZEN_BASE}/system/security/tokenOpRequest",
        headers={"tenant": "boxer"},
        json={"email": ZEN_EMAIL, "password": ZEN_SENHA},
        timeout=15,
    )
    r.raise_for_status()
    token = r.text.strip().strip('"')
    return {"Authorization": f"Bearer {token}", "tenant": "boxer"}


def zen_buscar(hdrs: dict, termo: str) -> list:
    todos, page = [], 1
    while True:
        try:
            r = requests.get(f"{ZEN_BASE}/catalog/person/person",
                             headers=hdrs,
                             params={"search": termo, "limit": 100, "page": page},
                             timeout=30)
        except requests.exceptions.Timeout:
            print(f"      !! Timeout (termo='{termo}' page={page})")
            break
        except Exception as e:
            print(f"      !! Erro ZEN: {e}")
            break
        if not r.ok:
            break
        data = r.json()
        items = data if isinstance(data, list) else data.get("items", data.get("data", []))
        if not items:
            break
        todos.extend(items)
        if len(items) < 100:
            break
        page += 1
        time.sleep(0.3)
    return todos


def score(item: dict, nome_ref: str, cidade_ref: str) -> int:
    fn = norm(item.get("fantasyName") or item.get("name") or "")
    cn = norm(item.get("city") or "")
    nr = norm(nome_ref)
    cr = norm(cidade_ref)
    s  = 0
    if fn == nr:
        s += 100
    elif nr in fn or fn in nr:
        s += 60
    else:
        stop = {"ltda","eireli","me","sa","epp","com","de","da","do","dos","das","e"}
        comuns = {p for p in set(nr.split()) & set(fn.split())
                  if len(p) > 2 and p not in stop}
        s += len(comuns) * 20
    if cr and cn:
        if cn[:5] == cr[:5]:
            s += 40
        elif cr[:4] in cn or cn[:4] in cr:
            s += 20
    return s


def todos_matches(candidatos: list, nome_ref: str, cidade_ref: str,
                  min_score: int = 60) -> list:
    """Retorna TODOS os candidatos com score suficiente, ordenados por score desc."""
    scored = [(score(c, nome_ref, cidade_ref), c) for c in candidatos]
    validos = [(s, c) for s, c in scored if s >= min_score]
    validos.sort(key=lambda x: x[0], reverse=True)
    return [c for _, c in validos]


# ── geocoding ───────────────────────────────────────────────────
def geocode_cep(cep: str) -> dict | None:
    if not cep:
        return None
    # BrasilAPI
    try:
        r = requests.get(f"https://brasilapi.com.br/api/cep/v2/{cep}", timeout=8)
        if r.ok:
            d = r.json()
            coords = (d.get("location") or {}).get("coordinates") or {}
            lat, lng = coords.get("latitude"), coords.get("longitude")
            city, state = d.get("city"), d.get("state")
            if lat and lng:
                return {"lat": float(lat), "lng": float(lng), "cidade": city, "estado": state}
            if city:
                geo = nominatim(f"{city} {state} Brasil")
                if geo:
                    return {**geo, "cidade": city, "estado": state}
    except Exception:
        pass
    # ViaCEP
    try:
        r = requests.get(f"https://viacep.com.br/ws/{cep}/json/", timeout=8)
        if r.ok:
            d = r.json()
            if not d.get("erro"):
                city, state = d.get("localidade"), d.get("uf")
                geo = nominatim(f"{d.get('logradouro','')} {city} {state} Brasil")
                if geo:
                    return {**geo, "cidade": city, "estado": state}
                geo = nominatim(f"{city} {state} Brasil")
                if geo:
                    return {**geo, "cidade": city, "estado": state}
    except Exception:
        pass
    return None


def nominatim(query: str) -> dict | None:
    time.sleep(1.1)
    try:
        r = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": query, "format": "json", "limit": 1, "countrycodes": "br"},
            headers={"User-Agent": "BMaxMotorPCI/1.0 (boxersoldas.com.br)"},
            timeout=10,
        )
        if r.ok and r.json():
            it = r.json()[0]
            return {"lat": float(it["lat"]), "lng": float(it["lon"])}
    except Exception:
        pass
    return None


# ── Supabase upsert por zen_id ───────────────────────────────────
def upsert_filial(registro: dict) -> str:
    """
    Retorna 'inserido', 'atualizado' ou 'sem_alteracao'.
    Chave: zen_id. Se zen_id null, usa nome+cidade.
    """
    zen_id = registro.get("zen_id")
    if zen_id:
        existente = sb(f"/comercial_revendas_bmax?zen_id=eq.{zen_id}")
    else:
        nome_enc  = requests.utils.quote(registro["nome"])
        cid_enc   = requests.utils.quote(registro.get("cidade") or "")
        existente = sb(f"/comercial_revendas_bmax?nome=eq.{nome_enc}&cidade=eq.{cid_enc}")

    if existente:
        rid = existente[0]["id"]
        # Atualiza apenas campos que mudaram (não sobrescreve lat/lng se já tinha coords precisas)
        atual = existente[0]
        patch = {}
        for campo in ("cep", "endereco", "cidade", "estado", "zen_id", "classe", "rep", "ativo"):
            novo = registro.get(campo)
            if novo is not None and atual.get(campo) != novo:
                patch[campo] = novo
        # lat/lng: só atualiza se o novo é mais preciso (veio de CEP) ou não tinha nenhum
        if registro.get("lat") and (not atual.get("lat") or registro.get("_cep_geocoded")):
            patch["lat"] = registro["lat"]
            patch["lng"] = registro["lng"]
        if patch:
            sb(f"/comercial_revendas_bmax?id=eq.{rid}", "PATCH", patch)
            return "atualizado"
        return "sem_alteracao"
    else:
        reg_insert = {k: v for k, v in registro.items() if not k.startswith("_")}
        sb("/comercial_revendas_bmax", "POST", reg_insert)
        return "inserido"


# ── hash da lista ────────────────────────────────────────────────
CONFIG_TABLE = "/comercial_bmax_config"
HASH_CHAVE   = "hash_revendas_lista"

def hash_lista() -> str:
    return hashlib.sha256(LISTA_PATH.read_bytes()).hexdigest()

def hash_salvo() -> str | None:
    try:
        rows = sb(f"{CONFIG_TABLE}?chave=eq.{HASH_CHAVE}&select=valor")
        return rows[0]["valor"] if rows else None
    except Exception:
        return None

def salvar_hash(h: str):
    try:
        hdrs_extra = {"Prefer": "resolution=merge-duplicates,return=minimal"}
        requests.post(
            SB_URL.rstrip("/") + "/rest/v1" + CONFIG_TABLE,
            headers={
                "apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}",
                "Content-Type": "application/json", **hdrs_extra,
            },
            json={"chave": HASH_CHAVE, "valor": h},
            params={"on_conflict": "chave"},
            timeout=10,
        )
    except Exception as e:
        print(f"  Aviso: não foi possível salvar hash ({e})")


# ── main ────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true",
                        help="Reprocessa revendas que já têm zen_id")
    args = parser.parse_args()

    import json

    # Verifica se a lista mudou desde o último enriquecimento
    h_atual = hash_lista()
    h_banco  = hash_salvo()
    if not args.force and h_atual == h_banco:
        print("Lista revendas_lista.json não mudou desde o último enriquecimento. Nada a fazer.")
        sys.exit(0)

    lista = json.loads(LISTA_PATH.read_text(encoding="utf-8"))["revendas"]
    print(f"Revendas na lista: {len(lista)}\n")

    # Carrega zen_ids já presentes para pular se não --force
    if not args.force:
        ja_tem = {r["zen_id"] for r in sb("/comercial_revendas_bmax?select=zen_id&ativo=eq.true")
                  if r.get("zen_id")}
        print(f"Registros com zen_id no banco: {len(ja_tem)}\n")
    else:
        ja_tem = set()

    print("Autenticando no ZEN...")
    hdrs_zen = zen_auth()
    print("Token obtido.\n")

    total_inseridos = total_atualizados = total_sem_cep = total_nao_encontrados = 0

    for i, rev in enumerate(lista, 1):
        nome   = rev["nome"]
        cidade = rev.get("cidade") or ""
        estado = rev.get("estado") or ""
        classe = rev.get("classe", "Prata")
        rep    = rev.get("rep", "")
        print(f"[{i:02d}/{len(lista):02d}] {nome} — {cidade}/{estado}")

        # Termos de busca: palavras significativas do nome
        stop = {"LTDA","EIRELI","S.A","SA","ME","EPP","COM","DE","DA","DO","DOS","DAS"}
        palavras = [p for p in nome.split() if len(p) > 2 and p.upper() not in stop]
        termos = []
        if palavras:
            termos.append(palavras[0])
        if len(palavras) > 1:
            termos.append(" ".join(palavras[:2]))

        # Busca ZEN
        candidatos = []
        seen_ids = set()
        for termo in termos:
            for item in zen_buscar(hdrs_zen, termo):
                rid = item.get("id")
                if rid not in seen_ids:
                    seen_ids.add(rid)
                    candidatos.append(item)
            time.sleep(0.2)

        matches = todos_matches(candidatos, nome, cidade)

        if not matches:
            print(f"   ✗ Não encontrado no ZEN ({len(candidatos)} candidatos)")
            total_nao_encontrados += 1
            time.sleep(0.3)
            continue

        print(f"   {len(matches)} match(es) encontrado(s):")

        for m in matches:
            zen_id  = str(m.get("id") or "")
            zen_nome = (m.get("fantasyName") or m.get("name") or "")[:60]
            zen_cid  = m.get("city") or cidade
            zen_est  = m.get("state") or estado
            cep_raw  = fmt_cep(m.get("zipcode"))
            endereco = fmt_end(m)
            sc       = score(m, nome, cidade)

            # Pula se já tem zen_id no banco e não é --force
            if zen_id and zen_id in ja_tem and not args.force:
                print(f"      = zen_id {zen_id} já no banco — pulando")
                continue

            # Geocoding pelo CEP do ZEN
            geo = None
            cep_geocoded = False
            if cep_raw:
                geo = geocode_cep(cep_raw)
                if geo:
                    cep_geocoded = True

            # Fallback: Nominatim por cidade/estado
            if not geo and zen_cid:
                geo = nominatim(f"{zen_cid} {zen_est} Brasil")

            registro = {
                "nome":          nome,
                "rep":           rep,
                "classe":        classe,
                "cidade":        geo.get("cidade") or zen_cid if geo else zen_cid,
                "estado":        geo.get("estado") or zen_est if geo else zen_est,
                "cep":           cep_raw or None,
                "endereco":      endereco or None,
                "zen_id":        zen_id or None,
                "lat":           geo["lat"] if geo else None,
                "lng":           geo["lng"] if geo else None,
                "ativo":         True,
                "_cep_geocoded": cep_geocoded,
            }

            resultado = upsert_filial(registro)

            cep_str = f"{cep_raw[:5]}-{cep_raw[5:]}" if cep_raw else "sem CEP"
            geo_str = f"lat={geo['lat']:.4f}" if geo else "sem coords"
            print(f"      [{resultado}] {zen_nome} | {zen_cid}/{zen_est} | {cep_str} | {geo_str} | score={sc}")

            if resultado == "inserido":
                total_inseridos += 1
            elif resultado == "atualizado":
                total_atualizados += 1
            if not cep_raw:
                total_sem_cep += 1

            time.sleep(0.3)

    print(f"\n=== Resultado ===")
    print(f"  Inseridos:          {total_inseridos}")
    print(f"  Atualizados:        {total_atualizados}")
    print(f"  Sem CEP no ZEN:     {total_sem_cep}")
    print(f"  Não encontrados:    {total_nao_encontrados}")

    salvar_hash(h_atual)
    print(f"\nHash da lista salvo: {h_atual[:12]}...")


if __name__ == "__main__":
    main()
