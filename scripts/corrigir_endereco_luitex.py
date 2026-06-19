"""
Corrige o registro da Luitex no Supabase buscando dados completos no ZEN.

Estratégia (sem chamadas desnecessárias):
  - id_cliente 147 (bsis.db) = Luitex Americana/SP (CNPJ 51.051.811/0002-33)
  - id_cliente 145 (bsis.db) = Luitex Santa Bárbara D'Oeste/SP (CNPJ 51.051.811/0001-52)
  - id_cliente é assumido como ZEN person ID (campo id_cliente vem do /sale/saleItem)
  - Uma chamada ZEN por candidato: GET /catalog/person/person/{id}
  - Atualiza nome_fantasia, cep, endereco no Supabase

Uso:
  py -3.11 scripts/corrigir_endereco_luitex.py
  py -3.11 scripts/corrigir_endereco_luitex.py --dry-run
"""
import os, sys, requests
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / ".env")
except ImportError:
    pass

DRY_RUN   = '--dry-run' in sys.argv
ZEN_EMAIL = os.environ['ZEN_EMAIL']
ZEN_SENHA = os.environ['ZEN_SENHA']
SB_URL    = os.environ.get('SUPABASE_URL', 'https://bmepxcnrsofofoswubuu.supabase.co')
SB_KEY    = os.environ['SUPABASE_SERVICE_KEY']
ZEN_BASE  = 'https://api.zenerp.app.br'

SB_WRITE = {
    'apikey': SB_KEY,
    'Authorization': f'Bearer {SB_KEY}',
    'Content-Type': 'application/json',
    'Prefer': 'return=minimal',
}
SB_READ = {
    'apikey': SB_KEY,
    'Authorization': f'Bearer {SB_KEY}',
}

CANDIDATOS = [
    {'zen_id': 147, 'cidade': 'Americana',              'estado': 'SP'},
    {'zen_id': 145, 'cidade': "Santa Bárbara D'Oeste",  'estado': 'SP'},
]

def zen_auth():
    r = requests.post(
        f'{ZEN_BASE}/system/security/tokenOpRequest',
        headers={'tenant': 'boxer'},
        json={'email': ZEN_EMAIL, 'password': ZEN_SENHA},
        timeout=15,
    )
    r.raise_for_status()
    token = r.text.strip().strip('"')
    return {'Authorization': f'Bearer {token}', 'tenant': 'boxer'}

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

print(f"{'[DRY RUN] ' if DRY_RUN else ''}Autenticando no ZEN...")
zen_hdrs = zen_auth()
print("Autenticado.\n")

for c in CANDIDATOS:
    zid = c['zen_id']
    print(f"Buscando ZEN ID {zid} ({c['cidade']}/{c['estado']})...")

    r = requests.get(f'{ZEN_BASE}/catalog/person/person/{zid}', headers=zen_hdrs, timeout=15)
    if not r.ok:
        print(f"  ZEN {r.status_code} — ID não encontrado. Pulando.\n")
        continue

    p = r.json()
    nome_zen = (p.get('fantasyName') or p.get('name') or '').upper()
    if 'LUITEX' not in nome_zen:
        print(f"  Nome ZEN '{p.get('name')}' não é Luitex — pulando.\n")
        continue

    cep      = fmt_cep(p.get('zipcode'))
    endereco = fmt_end(p)
    nome_f   = p.get('fantasyName') or None

    print(f"  ✓ Encontrado: {p.get('name')}")
    print(f"    Fantasia:  {nome_f}")
    print(f"    Endereço:  {endereco}")
    print(f"    CEP:       {cep or '—'}")

    # Busca registro no Supabase
    enc = requests.utils.quote(c['cidade'])
    sb_r = requests.get(
        f"{SB_URL}/rest/v1/comercial_revendas_bmax?nome=ilike.*luitex*&cidade=eq.{enc}&estado=eq.{c['estado']}&select=id,nome,zen_id",
        headers=SB_READ,
    )
    rows = sb_r.json() if sb_r.ok else []
    if not rows:
        print(f"  Registro não encontrado no Supabase para {c['cidade']}. Pulando.\n")
        continue

    sb_id = rows[0]['id']
    print(f"  Supabase ID: {sb_id}")

    patch = {'zen_id': str(zid)}
    if cep:
        patch['cep'] = cep
    if endereco:
        patch['endereco'] = endereco
    if nome_f:
        patch['nome_fantasia'] = nome_f

    if DRY_RUN:
        print(f"  [DRY RUN] Patch que seria enviado: {patch}\n")
        continue

    upd = requests.patch(
        f"{SB_URL}/rest/v1/comercial_revendas_bmax?id=eq.{sb_id}",
        headers=SB_WRITE,
        json=patch,
    )
    if upd.ok:
        print(f"  ✓ Supabase atualizado com sucesso.\n")
    else:
        print(f"  Erro ao atualizar Supabase: {upd.status_code} {upd.text[:300]}\n")

print("Concluído.")
