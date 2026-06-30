import os, json, requests
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

SB_URL = os.environ['SUPABASE_URL']
SB_KEY = os.environ['SUPABASE_SERVICE_KEY']
HDRS = {'apikey': SB_KEY, 'Authorization': f'Bearer {SB_KEY}'}

rows = requests.get(
    SB_URL + '/rest/v1/comercial_revendas_bmax?select=*&limit=500',
    headers=HDRS, timeout=30
).json()

if not isinstance(rows, list):
    raise RuntimeError(f'Resposta inesperada: {rows}')

out_dir = os.path.join(os.path.dirname(__file__), '..', 'backups')
os.makedirs(out_dir, exist_ok=True)

today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
path = os.path.join(out_dir, f'revendas_bmax_{today}.json')
with open(path, 'w', encoding='utf-8') as f:
    json.dump(rows, f, ensure_ascii=False, indent=2)

ativos = sum(1 for r in rows if r.get('ativo'))
print(f'Backup salvo: {path} | {len(rows)} registros | {ativos} ativos')
