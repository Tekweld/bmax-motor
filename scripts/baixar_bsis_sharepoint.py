"""
Baixa bsis.db do SharePoint (mesmo tenant/drive do BAV).
Usado pelo workflow do bmax-motor para ter acesso ao banco de dados histórico.

Env vars:
  MSAL_TOKEN_CACHE — cache JSON do token (mesmo usado pelo BAV)

Uso:
  py -3.11 scripts/baixar_bsis_sharepoint.py [--dest caminho/bsis.db]
"""
import os, sys, requests
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / ".env")
except ImportError:
    pass

DEST = Path(next((sys.argv[i+1] for i, a in enumerate(sys.argv) if a == '--dest'), 'bsis.db'))

TENANT_ID  = "c0bbec8e-9949-4dcf-80b3-bd21689c33e4"
CLIENT_ID  = "d1fb2af8-a56b-41a0-8401-e87591360016"
SCOPE      = ["https://graph.microsoft.com/Sites.Read.All"]
DRIVE_ID   = "b!6Kvw0SoDTUiClr8MvMu7NuwGBC9zdONMq_ED-vRKE3W43Ls7sVoDTZSN_i_i5kpD"
BSIS_PATH  = "COMERCIAL/Gestor/Salescope/bsis.db"  # caminho relativo na drive

def get_token():
    import msal
    cache_env = os.environ.get("MSAL_TOKEN_CACHE", "")
    cache = msal.SerializableTokenCache()
    if cache_env:
        cache.deserialize(cache_env)
    else:
        local = Path(__file__).parent.parent.parent.parent.parent.parent / \
                "App Vendas/bsis_v3/backend/data/.oauth_token_cache.json"
        if local.exists():
            cache.deserialize(local.read_text(encoding="utf-8"))
    app = msal.PublicClientApplication(
        CLIENT_ID,
        authority=f"https://login.microsoftonline.com/{TENANT_ID}",
        token_cache=cache,
    )
    accounts = app.get_accounts()
    result = app.acquire_token_silent(SCOPE, account=accounts[0]) if accounts else None
    if not result or "access_token" not in result:
        raise RuntimeError("Token MSAL expirado. Renove com scripts/renovar_msal_ci.py")
    return result["access_token"]

print(f"Baixando bsis.db do SharePoint → {DEST}")
token = get_token()
r = requests.get(
    f"https://graph.microsoft.com/v1.0/drives/{DRIVE_ID}/root:/{BSIS_PATH}:/content",
    headers={"Authorization": f"Bearer {token}"},
    timeout=120,
    allow_redirects=True,
)
r.raise_for_status()
DEST.write_bytes(r.content)
print(f"✓ bsis.db salvo em {DEST} ({len(r.content)/1024/1024:.1f} MB)")
