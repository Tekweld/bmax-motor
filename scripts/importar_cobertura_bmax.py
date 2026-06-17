"""
Importa cobertura de representantes BMax para Supabase.
Lê de scripts/cobertura_bmax.json (gerado do Excel IBGE).
Requer SUPABASE_URL e SUPABASE_SERVICE_KEY.
"""
import os, sys, json, requests

SB_URL = os.environ.get('SUPABASE_URL', 'https://bmepxcnrsofofoswubuu.supabase.co')
SB_KEY = os.environ.get('SUPABASE_SERVICE_KEY')
if not SB_KEY:
    print('SUPABASE_SERVICE_KEY não definida.'); sys.exit(1)

HEADERS = {
    'apikey': SB_KEY,
    'Authorization': f'Bearer {SB_KEY}',
    'Content-Type': 'application/json',
    'Prefer': 'resolution=merge-duplicates,return=minimal',
}

json_path = os.path.join(os.path.dirname(__file__), 'cobertura_bmax.json')
with open(json_path, encoding='utf-8') as f:
    records = json.load(f)

print(f'Total: {len(records)} municípios')
print(f'Com rep BMax: {sum(1 for r in records if r.get("rep_bmax"))}')
print(f'Sem cobertura: {sum(1 for r in records if not r.get("rep_bmax"))}')

BATCH = 500
ok = 0
for i in range(0, len(records), BATCH):
    batch = records[i:i+BATCH]
    r = requests.post(
        f'{SB_URL}/rest/v1/comercial_bmax_cobertura',
        json=batch, headers=HEADERS,
        params={'on_conflict': 'ibge_codigo'},
    )
    if r.ok:
        ok += len(batch)
        print(f'  {min(i+BATCH, len(records))}/{len(records)} enviados...')
    else:
        print(f'  Erro lote {i}: {r.status_code} {r.text[:200]}')
        sys.exit(1)

print(f'Concluído: {ok} registros importados.')
