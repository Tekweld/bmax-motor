"""
popular_ddd_cobertura.py
Popula a coluna ddd na tabela comercial_bmax_cobertura usando a BrasilAPI.
Estratégia: itera os 67 DDDs, busca cidades na BrasilAPI, cruza por nome+estado
com os municípios do banco e faz PATCH em lote (uma chamada Supabase por DDD).
Idempotente: só atualiza registros com ddd IS NULL por padrão.

Resíduo (fallback por estado): alguns municípios nunca vão casar por nome exato
— hífen/apóstrofo (`Olho d'Água do Borges`) ou porque a própria BrasilAPI não
lista a cidade nesse DDD. Para esses, em vez de deixar ddd NULL para sempre
(o que fazia este script falhar todo dia, sem nunca resolver), atribuímos o
DDD mais frequente já usado no mesmo estado — um "chute" deliberado, melhor
que nenhum valor, já que DDD aqui só serve para roteamento aproximado de
vendedor/representante, não para discagem real. O log do job lista quais
municípios levaram o valor exato e quais levaram o chute por estado.

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
        if not r.ok:
            raise RuntimeError(f'Supabase GET cobertura → {r.status_code}: {r.text[:300]}')
        data = r.json()
        if not isinstance(data, list) or not data: break
        all_records.extend(data)
        if len(data) < 1000: break
        page += 1
    return all_records

def load_ddd_mode_por_estado() -> dict:
    """DDD mais frequente já gravado em cada estado, entre os registros que já
    têm ddd preenchido — usado como chute para o resíduo que nunca casa por
    nome exato. Baseado na base inteira (não só nos registros desta execução),
    então funciona mesmo quando sobram poucos nulls para processar."""
    from collections import Counter
    counters: dict[str, Counter] = {}
    page = 0
    base = f'{SB_URL}/rest/v1/comercial_bmax_cobertura'
    while True:
        r = requests.get(
            f'{base}?select=estado,ddd&ddd=not.is.null&limit=1000&offset={page*1000}',
            headers=HEADERS, timeout=20
        )
        if not r.ok:
            raise RuntimeError(f'Supabase GET cobertura (ddd mode) → {r.status_code}: {r.text[:300]}')
        data = r.json()
        if not isinstance(data, list) or not data: break
        for rec in data:
            counters.setdefault(rec['estado'], Counter())[rec['ddd']] += 1
        if len(data) < 1000: break
        page += 1
    return {estado: counter.most_common(1)[0][0] for estado, counter in counters.items()}

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
    print(f'\nTotal exato: {total_matches} matches | Cidades da BrasilAPI sem correspondência: {nao_encontrados}')

    # Resíduo: registros que não casaram por nome exato em nenhum DDD.
    casados_exato = {ibge for ibges in ddd_to_ibges.values() for ibge in ibges}
    residuo = [rec for rec in records if rec['ibge_codigo'] not in casados_exato]

    if residuo:
        print(f'\n{len(residuo)} município(s) não casaram por nome exato — tentando chute por estado...')
        ddd_mode = load_ddd_mode_por_estado()
        sem_chute_possivel = []
        for rec in residuo:
            chute = ddd_mode.get(rec['estado'])
            if chute is None:
                sem_chute_possivel.append(rec)
                continue
            ddd_to_ibges.setdefault(chute, []).append(rec['ibge_codigo'])
            print(f"  {rec['cidade']}/{rec['estado']} → DDD {chute} (chute, DDD mais comum do estado)")
        if sem_chute_possivel:
            print(f"  Sem chute possível (estado sem nenhum DDD já gravado): "
                  + ', '.join(f"{r['cidade']}/{r['estado']}" for r in sem_chute_possivel))

    total_a_gravar = sum(len(v) for v in ddd_to_ibges.values())
    print(f'\nTotal a gravar (exato + chute): {total_a_gravar} de {len(records)} município(s) pendentes')

    # Só aborta se não sobrou NADA para gravar nem por chute — sinal real de
    # BrasilAPI fora do ar (sem exato) combinado com base ainda vazia (sem
    # histórico de ddd por estado para chutar). Um resíduo pequeno e estável
    # de casos-limite (hífen/apóstrofo, cidade ausente da BrasilAPI) não deve
    # mais derrubar o job todo dia — antes disso ser corrigido, o job falhava
    # 100% das vezes mesmo com a base 97%+ completa.
    if total_a_gravar == 0:
        print('Nenhum registro pôde ser atualizado (nem exato, nem chute) — provável falha da BrasilAPI com base ainda sem histórico de DDD. Abortando.')
        sys.exit(1)

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
