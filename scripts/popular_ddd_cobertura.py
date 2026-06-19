"""
popular_ddd_cobertura.py
Popula a coluna ddd na tabela comercial_bmax_cobertura usando a BrasilAPI.
Estratégia: itera os 67 DDDs, busca cidades na BrasilAPI, cruza por nome+estado
com os municípios do banco e faz PATCH em lote (uma chamada Supabase por DDD).
Idempotente: só atualiza registros com ddd IS NULL por padrão.
Uso:
  python scripts/popular_ddd_cobertura.py           # só registros sem DDD
  python scripts/popular_ddd_cobertura.py --force   # reprocessa todos
"""
import os, sys, time, unicodedata, argparse, requests
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / ".env")
except ImportError:
    pass

SB_URL = os.environ.get('SUPABASE_URL', 'https://bmepxcnrsofofoswubuu.supabase.co')
SB_KEY = os.environ.get('SUPABASE_SERVICE_KEY')
if not SB_KEY:
    print('SUPABASE_SERVICE_KEY não definida.'); sys.exit(1)

HEADERS = {
    'apikey': SB_KEY,
    'Authorization': f'Bearer {SB_KEY}',
    'Content-Type': 'application/json',
    'Prefer': 'return=minimal',
}

DDDS = [
    11,12,13,14,15,16,17,18,19,
    21,22,24,27,28,
    31,32,33,34,35,37,38,
    41,42,43,44,45,46,47,48,49,
    51,53,54,55,
    61,62,63,64,65,66,67,68,69,
    71,73,74,75,77,
    79,
    81,82,83,84,85,86,87,88,89,
    91,92,93,94,95,96,97,98,99,
]

def norm(s: str) -> str:
    s = s.upper().strip()
    s = unicodedata.normalize('NFD', s)
    return ''.join(c for c in s if unicodedata.category(c) != 'Mn')

def load_cobertura(force: bool) -> list:
    all_records, page = [], 0
    base = f'{SB_URL}/rest/v1/comercial_bmax_cobertura'
    extra = '' if force else '&ddd=is.null'
    while True:
        r = requests.get(
            f'{base}?select=ibge_codigo,cidade,estado{extra}&limit=1000&offset={page*1000}',
            headers=HEADERS, timeout=20
        )
        data = r.json()
        if not data: break
        all_records.extend(data)
        if len(data) < 1000: break
        page += 1
    return all_records

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--force', action='store_true')
    args = parser.parse_args()

    print('Carregando municípios do Supabase...')
    records = load_cobertura(args.force)
    if not records:
        print('Nenhum registro a atualizar.'); return
    print(f'  {len(records)} municípios a processar')

    # Índice: (CIDADE_NORM, ESTADO) → ibge_codigo
    lookup: dict[tuple, str] = {}
    for rec in records:
        lookup[(norm(rec['cidade']), rec['estado'])] = rec['ibge_codigo']

    # Para cada DDD, busca cidades na BrasilAPI e cruza com o lookup
    ddd_to_ibges: dict[int, list[str]] = {}
    nao_encontrados = 0

    for ddd in DDDS:
        try:
            r = requests.get(f'https://brasilapi.com.br/api/ddd/v1/{ddd}', timeout=10)
            if not r.ok:
                print(f'  DDD {ddd}: BrasilAPI {r.status_code}')
                continue
            data = r.json()
            state  = data.get('state', '')
            cities = data.get('cities', [])
            matched = []
            for city in cities:
                key = (norm(city), state)
                if key in lookup:
                    matched.append(lookup[key])
                else:
                    nao_encontrados += 1
            if matched:
                ddd_to_ibges[ddd] = matched
                print(f'  DDD {ddd} ({state}): {len(cities)} cidades → {len(matched)} matches')
            else:
                print(f'  DDD {ddd} ({state}): sem matches')
            time.sleep(0.15)
        except Exception as e:
            print(f'  DDD {ddd}: erro {e}')

    total_matches = sum(len(v) for v in ddd_to_ibges.values())
    print(f'\nTotal: {total_matches} matches | Sem match: {nao_encontrados}')
    print('Atualizando Supabase...')

    updated = 0
    CHUNK = 150  # máx IBGEs por URL para não estourar limite de URL
    for ddd, ibges in ddd_to_ibges.items():
        for i in range(0, len(ibges), CHUNK):
            chunk = ibges[i:i+CHUNK]
            in_filter = ','.join(chunk)
            r = requests.patch(
                f'{SB_URL}/rest/v1/comercial_bmax_cobertura?ibge_codigo=in.({in_filter})',
                headers=HEADERS, json={'ddd': ddd}, timeout=20,
            )
            if r.ok:
                updated += len(chunk)
            else:
                print(f'  Erro DDD {ddd}: {r.status_code} {r.text[:100]}')
        time.sleep(0.1)

    print(f'Concluído: {updated} registros atualizados.')

if __name__ == '__main__':
    main()
