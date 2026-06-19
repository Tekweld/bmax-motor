"""
Enriquece todos os registros de comercial_revendas_bmax que estão sem zen_id ou cep.

Estratégia (zero buscas de texto no ZEN):
  1. Carrega revendas do Supabase que precisam de enriquecimento
  2. Cruza com bsis.db (origem=corrente) por nome normalizado + cidade/estado
     → id_cliente do corrente = ZEN person ID real
  3. Uma chamada ZEN por match: GET /catalog/person/person/{id}
  4. Atualiza Supabase com zen_id, cep, endereco, nome_fantasia

Usa bsis.db como proxy de IDs ZEN — sem nenhuma busca de texto no ZEN.

Uso:
  py -3.11 scripts/enriquecer_enderecos_bmax.py [--bsis caminho/bsis.db] [--dry-run] [--force]
  --force     reprocessa mesmo quem já tem zen_id + cep
  --dry-run   mostra o que faria sem alterar Supabase
"""
import os, sys, re, unicodedata, sqlite3, requests, time
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / ".env")
except ImportError:
    pass

# ─── config ───────────────────────────────────────────────────────────────────
DRY_RUN   = '--dry-run' in sys.argv
FORCE     = '--force'   in sys.argv

# localização padrão do bsis.db (CI usa caminho relativo ao repo; local usa SharePoint)
BSIS_DEFAULT_PATHS = [
    Path(__file__).parent.parent / "bsis.db",                 # raiz do repo (CI)
    Path(r"C:\Users\andre.coelho.BXSD\BOXER\Fileserver - Documentos\COMERCIAL\Gestor\Salescope\bsis.db"),
]
bsis_arg = next((sys.argv[i+1] for i, a in enumerate(sys.argv) if a == '--bsis'), None)
if bsis_arg:
    BSIS_PATH = Path(bsis_arg)
else:
    BSIS_PATH = next((p for p in BSIS_DEFAULT_PATHS if p.exists()), None)

if not BSIS_PATH or not BSIS_PATH.exists():
    print(f"ERRO: bsis.db não encontrado. Use --bsis <caminho>")
    sys.exit(1)

ZEN_EMAIL = os.environ['ZEN_EMAIL']
ZEN_SENHA = os.environ['ZEN_SENHA']
SB_URL    = os.environ.get('SUPABASE_URL', 'https://bmepxcnrsofofoswubuu.supabase.co')
SB_KEY    = os.environ['SUPABASE_SERVICE_KEY']
ZEN_BASE  = 'https://api.zenerp.app.br'

SB_WRITE = {
    'apikey': SB_KEY, 'Authorization': f'Bearer {SB_KEY}',
    'Content-Type': 'application/json', 'Prefer': 'return=minimal',
}
SB_READ = {'apikey': SB_KEY, 'Authorization': f'Bearer {SB_KEY}'}

# ─── helpers ──────────────────────────────────────────────────────────────────
def norm(s):
    """Normaliza nome para matching: uppercase, sem acento, só alfanum+espaço."""
    s = (s or '').upper().strip()
    s = unicodedata.normalize('NFKD', s)
    s = s.encode('ascii', 'ignore').decode()
    s = re.sub(r'[^A-Z0-9 ]', ' ', s)
    return re.sub(r'\s+', ' ', s).strip()

def norm_cidade(s):
    return norm(s).replace("D OESTE", "D OESTE").replace("D ESTE", "D ESTE")

def fmt_cep(raw):
    d = ''.join(c for c in (raw or '') if c.isdigit())
    return d if len(d) == 8 else None

def fmt_end(p):
    partes = [
        p.get('address') or p.get('street') or '',
        p.get('number') or '',
        p.get('neighborhood') or p.get('district') or '',
    ]
    return ', '.join(x for x in partes if x).strip(', ') or None

def zen_auth():
    r = requests.post(
        f'{ZEN_BASE}/system/security/tokenOpRequest',
        headers={'tenant': 'boxer'},
        json={'email': ZEN_EMAIL, 'password': ZEN_SENHA},
        timeout=15,
    )
    r.raise_for_status()
    return {'Authorization': f'Bearer {r.text.strip().strip(chr(34))}', 'tenant': 'boxer'}

# ─── 1. carrega lookup do bsis.db (origem=corrente preferida) ──────────────────
print(f"Carregando bsis.db de: {BSIS_PATH}")
conn = sqlite3.connect(str(BSIS_PATH))
conn.row_factory = sqlite3.Row
cur = conn.cursor()

# Pega por corrente primeiro; agrupado por (nome_norm, cidade_norm, estado)
# Prefere o registro com endereço mais completo (contém vírgula = rua+número)
cur.execute("""
    SELECT id_cliente, nome_cliente, cidade, estado, cnpj, endereco, origem
    FROM vendas
    WHERE origem IN ('corrente', 'historico')
      AND id_cliente IS NOT NULL
    ORDER BY
      CASE origem WHEN 'corrente' THEN 0 ELSE 1 END,
      CASE WHEN endereco LIKE '%, %' THEN 0 ELSE 1 END,
      id_cliente DESC
""")

bsis_lookup = {}   # (nome_norm, cidade_norm, estado) → {id_cliente, endereco, cnpj, origem}
bsis_by_cnpj = {}  # cnpj_digits → {id_cliente, ...}  (fallback)

for r in cur.fetchall():
    key = (norm(r['nome_cliente']), norm_cidade(r['cidade']), (r['estado'] or '').upper())
    if key not in bsis_lookup:
        bsis_lookup[key] = {
            'id_cliente': r['id_cliente'],
            'endereco':   r['endereco'],
            'cnpj':       r['cnpj'],
            'origem':     r['origem'],
        }
    # índice por CNPJ (sem pontuação)
    cnpj_d = re.sub(r'\D', '', r['cnpj'] or '')
    if cnpj_d and cnpj_d not in bsis_by_cnpj:
        bsis_by_cnpj[cnpj_d] = {
            'id_cliente': r['id_cliente'],
            'endereco':   r['endereco'],
            'cnpj':       r['cnpj'],
            'origem':     r['origem'],
        }

conn.close()
print(f"  {len(bsis_lookup):,} entradas no lookup (por nome+cidade)")
print(f"  {len(bsis_by_cnpj):,} entradas no lookup (por CNPJ)")

# ─── 2. carrega revendas do Supabase ──────────────────────────────────────────
print("\nCarregando revendas do Supabase...")
sb_r = requests.get(
    f"{SB_URL}/rest/v1/comercial_revendas_bmax?ativo=eq.true&select=id,nome,cidade,estado,cep,zen_id,endereco",
    headers=SB_READ,
)
sb_r.raise_for_status()
revendas = sb_r.json()
print(f"  {len(revendas)} revendas ativas")

if not FORCE:
    revendas = [r for r in revendas if not (r.get('zen_id') and r.get('cep'))]
    print(f"  {len(revendas)} precisam de enriquecimento (sem zen_id ou cep)")

# ─── 3. faz matching ──────────────────────────────────────────────────────────
matches = []
sem_match = []

for rev in revendas:
    nome_n  = norm(rev['nome'])
    cid_n   = norm_cidade(rev.get('cidade') or '')
    est     = (rev.get('estado') or '').upper()

    entry = None

    # Tenta match exato
    entry = bsis_lookup.get((nome_n, cid_n, est))

    # Tenta match por prefixo do nome da revenda dentro do nome do cliente bsis
    if not entry:
        for (bn, bc, be), val in bsis_lookup.items():
            if be == est and bc == cid_n and bn.startswith(nome_n):
                entry = val
                break

    # Fallback: nome contido em bsis (qualquer cidade do mesmo estado)
    if not entry and est:
        candidates = [(k, v) for (bn, bc, be), v in bsis_lookup.items()
                      if be == est and bn.startswith(nome_n)
                      for k in [(bn, bc, be)]]
        if len(candidates) == 1:
            entry = candidates[0][1]

    if entry:
        matches.append({'rev': rev, 'bsis': entry})
    else:
        sem_match.append(rev)

print(f"\n  {len(matches)} com match no bsis.db")
print(f"  {len(sem_match)} sem match (serão pulados)")
if sem_match:
    for r in sem_match:
        print(f"    - {r['nome']} / {r.get('cidade')}, {r.get('estado')}")

if not matches:
    print("\nNada a processar.")
    sys.exit(0)

# ─── 4. autenticação ZEN ──────────────────────────────────────────────────────
print(f"\n{'[DRY RUN] ' if DRY_RUN else ''}Autenticando no ZEN...")
zen_hdrs = zen_auth()
print("Autenticado.\n")

# ─── 5. enriquece via ZEN e atualiza Supabase ─────────────────────────────────
ok = 0
erros = 0

for item in matches:
    rev   = item['rev']
    bsis  = item['bsis']
    zid   = bsis['id_cliente']

    print(f"[{rev['nome']}] {rev.get('cidade')}/{rev.get('estado')} — ZEN ID {zid} (bsis {bsis['origem']})")

    # Chama ZEN
    r = requests.get(f'{ZEN_BASE}/catalog/person/person/{zid}', headers=zen_hdrs, timeout=15)
    if not r.ok:
        print(f"  ZEN {r.status_code} — pulando\n")
        erros += 1
        time.sleep(0.3)
        continue

    p = r.json()
    cep      = fmt_cep(p.get('zipcode'))
    endereco = fmt_end(p)
    nome_f   = p.get('fantasyName') or None

    print(f"  ZEN nome: {p.get('name')}")
    print(f"  Endereço: {endereco}  |  CEP: {cep or '—'}")

    patch = {'zen_id': str(zid)}
    if cep:      patch['cep']           = cep
    if endereco: patch['endereco']      = endereco
    if nome_f:   patch['nome_fantasia'] = nome_f

    if DRY_RUN:
        print(f"  [DRY RUN] patch: {patch}\n")
        ok += 1
        time.sleep(0.3)
        continue

    upd = requests.patch(
        f"{SB_URL}/rest/v1/comercial_revendas_bmax?id=eq.{rev['id']}",
        headers=SB_WRITE, json=patch,
    )
    if upd.ok:
        print(f"  ✓ Supabase atualizado\n")
        ok += 1
    else:
        print(f"  ERRO Supabase {upd.status_code}: {upd.text[:200]}\n")
        erros += 1

    time.sleep(0.3)  # respeita rate limit ZEN

print(f"Concluído: {ok} atualizados, {erros} erros.")
