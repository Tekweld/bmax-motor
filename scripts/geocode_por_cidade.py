"""
geocode_por_cidade.py
Geocodifica revendas sem lat/lng usando cidade/estado via Nominatim.
Usa a anon key do Supabase (RLS aberto para anon).
Não precisa de ZEN nem service_role key.
"""
import json, time, requests, sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

SB_URL  = "https://bmepxcnrsofofoswubuu.supabase.co"
SB_ANON = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImJtZXB4Y25yc29mb2Zvc3d1YnV1Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3Nzk3MTczNzMsImV4cCI6MjA5NTI5MzM3M30.S55ouFczRYlUYNFf5PotYKXBPT5idypTSmbzR-x2Pk0"

HDRS = {
    "apikey": SB_ANON,
    "Authorization": f"Bearer {SB_ANON}",
    "Content-Type": "application/json",
    "Prefer": "return=minimal",
}


def nominatim(cidade: str, estado: str) -> tuple[float, float] | None:
    """Retorna (lat, lng) ou None."""
    time.sleep(1.2)   # respeita rate limit Nominatim: 1 req/s
    query = f"{cidade}, {estado}, Brasil"
    try:
        r = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": query, "format": "json", "limit": 1, "countrycodes": "br"},
            headers={"User-Agent": "BMaxMotorPCI/1.0 (boxersoldas.com.br)"},
            timeout=12,
        )
        if r.ok and r.json():
            item = r.json()[0]
            return float(item["lat"]), float(item["lon"])
    except Exception as e:
        print(f"   ✗ Nominatim erro: {e}")
    return None


def main():
    # 1. Busca todas as revendas sem lat/lng
    r = requests.get(
        f"{SB_URL}/rest/v1/comercial_revendas_bmax",
        params={"select": "id,nome,cidade,estado", "lat": "is.null"},
        headers=HDRS,
        timeout=15,
    )
    revendas = r.json()
    print(f"Revendas sem lat/lng: {len(revendas)}\n")

    ok = 0
    falha = []
    for i, rev in enumerate(revendas, 1):
        cidade = rev["cidade"] or ""
        estado = rev["estado"] or ""
        # Para cidades com múltiplos nomes (ex: "São Bento do Sul e Canoinhas"), usa o primeiro
        cidade_principal = cidade.split(" e ")[0].strip()
        print(f"[{i:02d}/{len(revendas):02d}] {rev['nome']} — {cidade_principal}/{estado}", end="  ")

        coords = nominatim(cidade_principal, estado)
        if coords:
            lat, lng = coords
            patch = requests.patch(
                f"{SB_URL}/rest/v1/comercial_revendas_bmax",
                params={"id": f"eq.{rev['id']}"},
                headers=HDRS,
                json={"lat": lat, "lng": lng},
                timeout=10,
            )
            if patch.ok:
                print(f"✓ {lat:.5f}, {lng:.5f}")
                ok += 1
            else:
                print(f"✗ Supabase erro: {patch.status_code}")
                falha.append(rev["nome"])
        else:
            print("✗ não encontrado")
            falha.append(rev["nome"])

    print(f"\n✅ {ok} geocodificadas   ✗ {len(falha)} falhas")
    if falha:
        print("Falhas:")
        for n in falha:
            print(f"  • {n}")


if __name__ == "__main__":
    main()
