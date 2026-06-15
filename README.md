# BMax Motor PCI

Motor de classificação de leads industriais da Boxer Soldas — 17 PCIs conforme planilha BMax_CRITERIOS.

## Stack

- **Frontend**: HTML/JS puro — `index.html` (single-file)
- **Banco**: Supabase `boxer-sistemas` (prefixo `comercial_`)
- **Hospedagem**: Netlify → `app.boxersoldas.com.br/bmax-motor`
- **Enriquecimento**: Python script ZEN API → Supabase

## Configuração inicial

### 1. Supabase — rodar SQL

No **SQL Editor** do Supabase (`boxer-sistemas`), execute:

```
migrations/01_create_tables.sql
```

### 2. Netlify — deploy

- Conectar repositório `Tekweld/bmax-motor` ao Netlify
- Branch: `main` · Diretório publicado: `/` (raiz)
- Configurar DNS: `app.boxersoldas.com.br` → Netlify

### 3. GitHub Secrets (para o workflow de sincronização ZEN)

```
ZEN_EMAIL               = andre.coelho@boxersoldas.com.br
ZEN_SENHA               = (senha ZEN)
SUPABASE_URL_BMAX       = https://bmepxcnrsofofoswubuu.supabase.co
SUPABASE_SERVICE_KEY_BMAX = (service_role key — solicitar ao Bruno)
```

### 4. Rodar enriquecimento ZEN (primeira vez)

```bash
pip install requests python-dotenv
python scripts/enrich_revendas_bmax.py --force
```

Ou via GitHub Actions → **Sincronizar Revendas BMax** → Run workflow (marcar "force").

## Estrutura

```
bmax-motor/
├── index.html                    # App principal (login + motor PCI)
├── revendas_lista.json           # Lista-mestre de revendas (edite aqui)
├── migrations/
│   └── 01_create_tables.sql      # SQL para criar tabelas no Supabase
├── scripts/
│   └── enrich_revendas_bmax.py   # ZEN → geocode → Supabase
└── .github/workflows/
    └── sincronizar_revendas.yml  # Trigger manual: Actions → Run workflow
```

## PCIs implementados

| Cluster | PCIs |
|---|---|
| Robô | PCI1, PCI2, PCI3 |
| Laser +2 | PCI4, PCI5, PCI6 |
| Laser ×1 | PCI7, PCI8, PCI9 |
| Máquina ≥R$50k | PCI10, PCI11, PCI12 |
| Máquina <R$50k | PCI13, PCI14, PCI15 |
| Lead Revenda (Boxer+Rev) | PCI16 |
| Lead Revenda (Rev lidera) | PCI17 |

## Atualizar lista de revendas

1. Editar `revendas_lista.json`
2. Commitar e fazer push para `main`
3. Ir em **Actions → Sincronizar Revendas BMax → Run workflow**

O script detecta a mudança via hash e só chama a ZEN API quando necessário.
