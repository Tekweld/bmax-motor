# BMax Motor — Documentação Técnica

> Documento de referência para quem for mexer neste repositório depois (humano ou
> sessão futura do Claude). Escrito a partir da leitura direta do código em
> 2026-09-21. Onde o código contradiz o README ou a memória do projeto, o código
> venceu — e a contradição está marcada explicitamente abaixo.

Repositório: `github.com/Tekweld/bmax-motor` (remote confirmado via `git remote -v`).
Pasta local: `BOXER/Dados - Documentos/Comercial/Geral/Estrategia/2026/Projeto BMax/bmax-motor`.

---

## 1. O que é e quem usa

BMax Motor é a **calculadora de classificação PCI** do programa comercial BMax da
Boxer Soldas. Um vendedor, representante ou admin descreve um lead (produto,
origem, se tem revenda perto, se tem representante, CEP) e o Motor devolve:

- em qual dos **16 PCIs** (Perfil de Condução de Indústria/Indicação) o lead se
  encaixa;
- qual é o **modelo de atendimento** resultante (Boxer sozinha, Boxer+Revenda,
  Revenda sozinha etc.);
- as **faixas de comissão** (VI/VT, Representante, Revenda) para aquele PCI, por
  classe de preço do cliente;
- quem é o **vendedor Boxer responsável** (por DDD) e o **representante BMax**
  responsável (por cidade/IBGE);
- se existe uma **revenda Diamante** disponível para apoio de demonstração.

Quem loga: qualquer email cadastrado em `comercial_bmax_admins` (tabela
"whitelist" de acesso — apesar do nome, não é só admin de sistema, é a lista de
quem pode abrir o Motor). Há dois perfis (coluna `perfil`): `admin` (vê a seção
"Equipe/Representantes/Configurações" no menu lateral) e um perfil padrão sem
esse acesso. Autenticação é Supabase Auth (email+senha), igual ao padrão Boxer.

O Motor é uma **ferramenta de apoio à decisão para quem está vendendo**, não um
CRM — ele não guarda o funil do lead. Consulta de "esse cliente já é de
alguém?" é delegada ao Portal BMax via `GET {PORTAL_URL}/api/motor/consulta-lead`
(o Motor não tem o token do RD Station).

## 2. Arquitetura

- **Sem build, sem framework.** `index.html` (~4140 linhas) é HTML+CSS+JS puro
  num arquivo só, carregando o SDK JS do Supabase de `vendor/supabase.min.js`
  (vendorizado localmente, não via CDN).
- Existem dois arquivos HTML standalone adicionais — `equipe.html` e
  `representantes.html` — cada um com seu próprio login e lógica. **Estão
  órfãos**: nada em `index.html` linka para eles (confirmado por grep — zero
  ocorrências de `equipe.html`/`representantes.html` dentro de `index.html`).
  Ver seção 6.
- **Autenticação/acesso client-side:** a chave `anon` do Supabase (`SB_ANON`)
  está hardcoded no HTML (linha 992 de `index.html`, e também hardcoded em
  vários scripts Python como `scripts/geocode_por_cidade.py` e
  `scripts/criar_usuario_auth.py`). Isso é o padrão esperado — a `anon key` é
  pública por design. RLS (Row Level Security) está ativo em todas as tabelas
  `comercial_bmax_*`.
- **RLS mudou de dono ao longo do tempo** (isto é o achado mais importante do
  repo, ver seção 3.1): as migrations 01–06 davam escrita a qualquer usuário
  `authenticated` (ou seja, qualquer admin logado no Motor podia escrever).
  A migration `07_lockdown_rls_portal_only.sql` (commit `27c92d5`, e
  `08_add_diamante_classe.sql` logo depois, `e0996a5`, ambas ~2026-09-11/14)
  **fechou a escrita em 4 tabelas para `service_role` apenas** — só o Portal
  BMax (que usa a service key) pode escrever nelas agora. O Motor ficou
  **somente leitura** nessas tabelas.
- **Hospedagem: Cloudflare Pages, não Netlify.** O `README.md` (e o padrão
  corporativo em CLAUDE.md) descreve Netlify + `app.boxersoldas.com.br`, mas os
  workflows reais (`.github/workflows/atualizar_bmax.yml` e
  `deploy_on_push.yml`) fazem `npx wrangler pages deploy . --project-name=bmax-motor`
  — ou seja, **Cloudflare Pages**, projeto `bmax-motor`, publicado em
  `bmax-motor.pages.dev` (confirmado pelo `redirectTo` usado no fluxo de reset
  de senha: `https://bmax-motor.pages.dev`). **O README está desatualizado
  nesse ponto** — não é confiável para saber onde o site está hospedado.
- Deploy é automático: qualquer push em `main` que toque `index.html` (ou
  `admin_supabase.html`/`*.css`/`*.js`) dispara `deploy_on_push.yml`. Além
  disso, o workflow diário `atualizar_bmax.yml` também republica o site como
  parte do job 5 ("Publicar portal").
- Projeto Supabase: **`boxer-sistemas`**, ref `bmepxcnrsofofoswubuu` — mesmo
  projeto do padrão Boxer e o mesmo que o Portal BMax usa. Confirmado em
  comentários no topo de vários arquivos de migration.

## 3. Modelo de dados (Supabase `boxer-sistemas`, prefixo `comercial_`)

Reconstruído a partir de `migrations/01` a `08` + uso real no JS (algumas
colunas usadas no JS não aparecem em nenhuma migration — ver 3.2).

| Tabela | Propósito | Colunas-chave | Quem escreve hoje |
|---|---|---|---|
| `comercial_revendas_bmax` | Cadastro de revendas (parceiras que vendem/indicam) | `zen_id`, `nome`, `nome_fantasia`, `rep`, `cidade`, `estado`, `cep`, `lat`/`lng`, `classe` (`Ouro`/`Prata`/`Diamante`/`Não Aplica`, migration 08 adicionou Diamante), `zen_group`, `endereco`, `mesorregiao_ibge`, `demonstrador_nome`, `ativo` | **Só Portal** (RLS `service_role` desde migration 07) |
| `comercial_bmax_config` | Config chave/valor do pipeline (raio, thresholds, comissões, tabela de comissão inteira) | `chave` (PK/unique), `valor` (texto — inclusive JSON serializado) | **Só Portal** (RLS `service_role` desde migration 07) |
| `comercial_bmax_classificacoes` | Log de cada classificação feita no wizard (analytics de uso) | `usuario_email`, `pci_id`, `produto`, `origem`, `condutor`, `cep_lead`/`cidade_lead`/`estado_lead`/`lat_lead`/`lng_lead`, `resultado` (jsonb), `diamante_disponivel`, `diamante_revenda_id` | Motor (INSERT via `authenticated`) |
| `log_alteracoes` | Log de alterações genérico (padrão Boxer) | `usuario_email`, `tabela_ref`, `registro_id`, `campo`, `valor_anterior`, `valor_novo` | Definida mas **não vi nenhum INSERT real** no JS lido — parece não estar em uso ativo no Motor |
| `comercial_bmax_cobertura` | Representante BMax responsável por cidade (chave: código IBGE) | `ibge_codigo` (PK), `cidade`, `estado`, `rep_bmax`, `ddd`, `mesorregiao` (usada no JS, não vista em migration — ver 3.2), `ativo` | **Só Portal** (RLS `service_role` desde migration 07; era `service_role` desde a criação, migration 02) |
| `comercial_bmax_vendedores` | Vendedores Boxer internos (VI/VT1/VT2), área de atuação por DDD | `nome`, `tipo` (`VI`/`VT1`/`VT2`), `cor`, `ddds` (array int), `fallback` (bool — vendedor default quando DDD não bate), `ativo` | **Só Portal** desde migration 07 (antes, migration 06 tinha corrigido para `authenticated` — ida e volta, ver 3.1) |
| `comercial_bmax_admins` | Whitelist de quem pode logar no Motor/Portal + perfil de acesso | `email` (unique), `nome`, `perfil` (usado no JS como `'admin'` vs. outro — **coluna não existe em nenhuma migration lida**, drift de schema), `ativo` | Admins existentes podem inserir/desativar outros (RLS própria, migration 05) |
| `comercial_bmax_log_revendas` | Log específico de alterações em revendas (ação, campo, valor antes/depois) | `revenda_id`, `zen_id`, `acao`, `campo`, `valor_anterior`, `valor_novo`, `usuario_email` | Referenciada em `index.html` (`saveRev()`) mas **sem migration correspondente no repo** — criada direto no Supabase, fora do controle de versão |

### 3.1 Achado central: o Motor deixou de ser dono da escrita

A leitura cronológica das migrations conta a história real do sistema:

1. `01_create_tables.sql` (commit `ddd7081`): cria `comercial_revendas_bmax`,
   `comercial_bmax_config`, `comercial_bmax_classificacoes`, `log_alteracoes`.
   Escrita liberada para qualquer `authenticated`.
2. `04_schema_updates.sql`: cria `comercial_bmax_vendedores`, escrita restrita a
   `service_role` — **mas isso quebrou o cadastro pelo Motor**, corrigido em
   `06_fix_vendedores_write.sql` para `authenticated` de novo (o próprio commit
   `d2d9133` documenta o bug: *"new row violates row-level security policy"*).
3. `07_lockdown_rls_portal_only.sql` (commit `27c92d5`, "fecha RLS de escrita —
   só o Portal (service_role) grava no Supabase"): reverte de vez. A partir daí
   `comercial_bmax_vendedores`, `comercial_revendas_bmax`,
   `comercial_bmax_cobertura` e `comercial_bmax_config` só aceitam escrita de
   `service_role`. O comentário no SQL é explícito: *"Pré-requisito (já feito):
   o Portal passou a escrever nessas tabelas usando a chave service_role
   (SUPABASE_SERVICE_KEY_SISTEMAS), não mais a anon key que o Motor também
   usa."*

**Consequência prática, confirmada no JS atual de `index.html`:** as 3 seções
do menu admin do Motor (Equipe Comercial, Representantes, Configurações) **não
têm mais formulário próprio** — `adm_enterSection()` (linha ~3085) injeta um
HTML estático (`ADM_RESUMO_HTML`, linha ~3059) que só lista links para
`{PORTAL_URL}/#gestao`. O comentário no código (linhas 3054–3058) confirma a
intenção: *"Vendedores, Revendas, Cobertura, Representantes BMax e
Comissão/Classificação agora só têm cadastro no Portal BMax — o Motor apenas
replica (lê)."*

Só que o código antigo de escrita **não foi removido**, só ficou inalcançável
pela UI: `saveRev()` (linha 2644, grava em `comercial_revendas_bmax` +
`comercial_bmax_log_revendas`), `saveCfg()`/`saveConfigToSb()` (linha 3026/1523,
grava em `comercial_bmax_config`, inclusive a chave `comissao_tabela`), e todo
o CRUD de `comAddClasse`/`comAddLinha`/`comRemoveLinha`/`comAddComplemento` para
editar a tabela de comissão continuam no arquivo. O formulário HTML que
alimentava `saveRev()` (`#rev-form-wrapper`) é forçado para `display:none` em
`showApp()` (linha 1096) e a coluna de ações da tabela de revendas
(`#rev-acoes-th`) também é escondida. **Essas funções são código morto na
prática — se alguém achar um jeito de chamá-las (ex.: via console), vão falhar
com erro de RLS 403**, porque as tabelas que tentam escrever já são
`service_role`-only.

O mesmo vale, com mais força ainda, para **`equipe.html` e
`representantes.html`**: são páginas completas, com login próprio, que fazem
`insert`/`update` diretamente em `comercial_bmax_vendedores` e
`comercial_bmax_cobertura` via `sbClient` (chave `anon`/`authenticated`). Elas
não são linkadas de lugar nenhum, mas se alguém tiver a URL direta
(`/equipe.html`, `/representantes.html`, publicadas normalmente pelo Cloudflare
Pages porque estão na raiz do repo) consegue logar — e qualquer tentativa de
salvar vai falhar silenciosamente ou com toast de erro, porque a política RLS
não permite mais escrita por `authenticated` nessas tabelas.

### 3.2 Drift de schema (fora do controle de versão)

Duas coisas usadas no JS não aparecem em nenhuma migration do repo — foram
criadas manualmente no SQL Editor do Supabase e nunca versionadas:

- coluna `perfil` em `comercial_bmax_admins` (usada para diferenciar `admin`
  de acesso comum);
- coluna `mesorregiao` em `comercial_bmax_cobertura` e a tabela inteira
  `comercial_bmax_log_revendas`.

Se for mexer nessas tabelas via migration nova, confira o schema real no
Supabase antes de assumir que as migrations do repo são a fonte completa da
verdade.

### 3.3 Tabelas compartilhadas com o Portal BMax (ponto de acoplamento)

Todas as tabelas `comercial_bmax_*` e `comercial_revendas_bmax` são
compartilhadas com o Portal BMax (mesmo projeto `boxer-sistemas`). Depois da
migration 07, a direção do acoplamento é clara e unidirecional:

- **Portal escreve, Motor só lê**: `comercial_revendas_bmax`,
  `comercial_bmax_config` (inclusive `comissao_tabela`/`comissao_complementos`),
  `comercial_bmax_cobertura`, `comercial_bmax_vendedores`.
  Qualquer mudança de schema nessas tabelas feita a partir do Portal (nova
  coluna, novo `CHECK`, renomeação) impacta o Motor sem aviso — o Motor não
  tem teste automatizado, só quebra em produção se o formato do JSON em
  `comissao_tabela` mudar ou se uma constraint nova rejeitar valores que o
  Motor tentava usar (foi exatamente o caso do bug corrigido na migration 08:
  o formulário sempre ofereceu "Diamante" como opção de classe, mas a
  constraint só aceitava Ouro/Prata/Não Aplica até 2026-09-11).
- **Motor escreve, ninguém mais lê (por enquanto)**:
  `comercial_bmax_classificacoes` — é só log de uso do próprio Motor.
- **`comercial_bmax_admins`** é compartilhada mas com regra própria (qualquer
  admin ativo pode inserir/desativar outro admin) — não foi trancada pela
  migration 07. É a lista de acesso comum a Motor e Portal.

## 4. Classificação em 16 PCIs

A tabela `PCIS` (const, `index.html` linha ~1214) é a fonte da verdade da
lógica — um array de objetos, um por PCI, com os campos `id`, `grupo`, `prod`
(`robo`/`laser`/`maquina`), `dist` (tem revenda no raio?), `rep` (tem
representante?), `origem` (`BOXER` ou `REVENDA`), `atend` (`VI_VT` ou
`REVENDA`), `modelo` (ex.: `BOX>IND`, `BOX+REV>IND`, `BOX>REV`), `repPct`,
`viBase`, `revBase`, `portal` (quem vê o lead no Portal: `ADM`, `ADM + REP`,
`TODOS`, `NÃO`) e opcionalmente `forcedClass` (trava a classe de preço).

Clusters, conforme o comentário no topo do array ("16 PCIs — V2 (planilha
BMAX_CRITERIOS)"):

| Cluster | PCIs | Critério de árvore de decisão |
|---|---|---|
| Robô | PCI1, PCI2, PCI3 | sem revenda/sem rep → PCI1; sem revenda/com rep → PCI2; com revenda no raio → PCI3 |
| Laser (unificado) | PCI4, PCI5, PCI6 | mesma árvore que Robô |
| Máquina >R$25k | PCI7, PCI8, PCI9 | mesma árvore, quando `ans.nf === 'acima'` |
| Máquina ≤R$25k | PCI10, PCI11, PCI12(A/B) | mesma árvore, quando NF ≤ R$25k |
| Lead Revenda | PCI13 (robô), PCI14 (laser), PCI15 (máquina), PCI16 | origem do lead é a própria revenda |

A árvore de decisão real está em `matchPCI()` (linha ~2187): usa
`ans.produto`, `ans.origem`, `ans.rep`, `temRevenda()` (há revenda dentro do
raio `CFG.raio`, padrão 50 km) e `ans.nf` (acima/abaixo de R$25k — note que o
**limiar não é mais R$50k**: `loadConfig()` linha 1510 tem uma migração
inline, *"if (CFG.nf === 50000) CFG.nf = 25000"*, corrigindo configs antigas
salvas com o valor V1).

**PCI12 é o único caso ambíguo por design**: quando é Máquina ≤R$25k com
revenda no raio, `matchPCI()` devolve um objeto provisório `_isPCI12:true`
(linha 2227) em vez de um PCI fechado — a decisão final entre **PCI12A**
(`BOX>REV`, a revenda decide conduzir sozinha) e **PCI12B** (`BOX+REV>IND`,
Boxer conduz e a revenda ganha cashback) depende de validação humana com a
revenda, feita em `classify()` (linha 2235 em diante). Ambos PCI12A e PCI12B
têm `forcedClass:6` — a classe de preço é sempre travada em "Classe 6",
independente do valor real do negócio.

**Lead Revenda**: se `ans.condutor === 'revenda_lidera'`, vai direto para
PCI16 (revenda conduz sozinha, `BOX>REV`), senão cai em PCI13/14/15 por
produto (Boxer + Revenda conduzem juntas).

### 4.1 Diamante — mecanismo operacional, não classificatório (confirmado)

`checkDiamante(pci)` (linha 1581) roda **depois** que o PCI já foi decidido —
nunca entra na árvore de `matchPCI()`. As regras:

```js
function checkDiamante(pci) {
  if (!leadGeo || leadGeo.state === 'SP') return null;   // só fora de SP
  if (ans.produto !== 'laser') return null;               // só produto Laser
  const diamantes = revendas.filter(r => r.ativo !== false && r.classe === 'Diamante' && r.mesorregiao_ibge);
  ...
}
```

Ou seja: Diamante só entra em jogo para leads de **Laser fora de São Paulo**, e
só se existir alguma revenda classe `Diamante` cadastrada com
`mesorregiao_ibge` preenchida. Se achar uma revenda Diamante na mesma
mesorregião (ou, na falta, no mesmo estado, ou a única do sistema),
`renderDiamanteBanner()` mostra um banner pedindo para **"solicitar apoio de
demonstração Laser ao Gerente Industrial, que acionará a Revenda Diamante"** —
inclusive nomeando o `demonstrador_nome` cadastrado na revenda. Isso é o único
efeito do Diamante no Motor: **roteamento de suporte de demonstração**, nunca
muda o PCI, a comissão ou o modelo de atendimento calculado. A classe
`Diamante` também dá um raio de proximidade bônus na busca de revendas
próximas (`BONUS_KM = { Diamante: 30, Ouro: 15, Prata: 0, 'Não Aplica': 0 }`,
linha 2136) — ou seja, ela também influencia se uma revenda aparece como "no
raio" para fins de PCI (revenda Diamante conta como perto até 30 km a mais que
o raio configurado), mas isso é comportamento de *proximidade*, não uma regra
de PCI específica para Diamante.

## 5. Cálculo de comissão

Cada linha de `PCIS` já carrega uma comissão "base" hardcoded via `viBase`
(`'std'` → tabela `_VI_STD = [1.2, 1.5, 1.7, 1.9, 2.0, 2.1]` por classe 1–6;
`'lr'` → `_VI_LR`, comissão menor para Lead Revenda) e `revBase`
(`'fixed-1.5'`, `'fixed-2.0'`, ou uma das tabelas `_REV_CLASSES` por cluster).
Isso é só o **fallback**: a fonte real é o Supabase.

`loadConfig()` (linha 1495) lê `comercial_bmax_config`, procura a chave
**`comissao_tabela`** e faz `JSON.parse(map.comissao_tabela)` para popular
`COM_TABELA` — um objeto `{classes: [...6 nomes...], linhas: [{pci, agente,
valores:[...6 números...]}, ...]}`, uma linha por combinação PCI×agente
(`VI/VT`, `Rep`, `Revenda`). Há também `comissao_complementos`
(`COM_COMPLEMENTOS`) para casos especiais (ex.: "Rep conduz sozinho" em
PCI2/PCI3/PCI5/etc., valores mais altos que o padrão — ver `_EXC_CLASSES`
como fallback). Se a chave não existir ou o JSON não parsear,
`buildDefaultComTabela()`/`buildDefaultComComplementos()` reconstroem a tabela
a partir dos valores hardcoded em `PCIS`.

Isso **confirma a suposição da memória do projeto**: o Portal BMax lê
`comercial_bmax_config` chave `comissao_tabela` para o sistema de cashback, e
o formato é exatamente esse JSON `{classes, linhas}` que o Motor também
consome. **Mas atenção**: como visto na seção 3.1, quem escreve essa chave
hoje é só o **Portal** (RLS `service_role`) — a função `saveConfigToSb()` que
grava `comissao_tabela` a partir do Motor (linha 1523) é código morto, sem UI
que a acione. Se o formato do JSON mudar do lado do Portal sem avisar o Motor,
`comGetLinha()`/`fmtVI()`/`fmtRepPct()`/`fmtRevPct()` (linhas 1330–1384) que
leem essa estrutura quebram silenciosamente (voltam pro fallback hardcoded,
que pode estar desatualizado frente à tabela real de comissão vigente).

A comissão do representante é fixa por PCI (`repPct`: 0, 1 ou 2, conforme o
PCI — nunca varia por classe, exceto onde há linha específica em `COM_TABELA`
vinda do Portal). A comissão de revenda em PCI6/PCI9/PCI12B é fixa (`1,5%` ou
`2,0%`, rotulada no código como "fixo · cashback portal"); em PCI13/14/15 e
PCI2/3/5/8/11 varia por classe de preço via `_REV_CLASSES`/`_EXC_CLASSES`
(fallback) ou pela tabela dinâmica.

## 6. Telas — o que `equipe.html` e `representantes.html` realmente gerenciam

Confirmado pela leitura do código (não presumido pelo nome do arquivo):

- **`equipe.html`** — CRUD de **vendedores Boxer internos** na tabela
  `comercial_bmax_vendedores`: nome, tipo (`VI`/`VT1`/`VT2` — Vendedor Interno
  / Vendedor Técnico 1 / Vendedor Técnico 2), cor (usada nos badges do Motor),
  lista de DDDs de atuação, flag `fallback` (vendedor que pega o lead quando o
  DDD não bate com ninguém) e `ativo`. Tem também uma segunda seção de
  **Admins** (`loadAdmins()`/CRUD de `comercial_bmax_admins`) — controla quem
  pode logar no Motor.
- **`representantes.html`** — gestão da **cobertura de representantes BMax
  por cidade** (`comercial_bmax_cobertura`), com filtros e paginação: para
  cada município (chave `ibge_codigo`), define qual `rep_bmax` (representante
  externo BMax) é responsável. É o dado que `getRepBmax()` no Motor consulta
  para sugerir o representante certo durante a classificação.

Como já registrado na seção 3.1, **ambas são páginas órfãs**: continuam no
repo, continuam sendo publicadas pelo Cloudflare Pages (é conteúdo estático na
raiz), têm login funcional (`comercial_bmax_admins` continua com escrita
liberada), mas qualquer tentativa de salvar dado vai falhar por RLS —
`comercial_bmax_vendedores` e `comercial_bmax_cobertura` só aceitam
`service_role` desde a migration 07.

## 7. Coupling e gotchas com o Portal BMax — resumo para quem for mexer

1. **Motor não edita mais nada de cadastro — só o Portal edita.** Revendas,
   Cobertura, Vendedores, Representantes BMax e a Matriz de Comissão só têm
   formulário no Portal (`{PORTAL_URL}/#gestao`, `PORTAL_URL =
   'https://bmax.boxersoldas.com.br'`). Se um botão de "salvar" parecer não
   fazer nada no Motor, é porque ele foi desligado de propósito — não é bug a
   corrigir reativando escrita, é um lembrete de que a superfície de edição
   migrou.
2. **`comissao_tabela` em `comercial_bmax_config` é o contrato entre os dois
   sistemas.** Formato `{classes:[...], linhas:[{pci, agente, valores:[...]}]}`.
   Qualquer mudança de formato precisa ser coordenada nos dois repos — o Motor
   só lê, nunca escreve mais essa chave em produção.
3. **RLS por `service_role` protege as tabelas certas, mas a chave `anon`
   ainda aparece hardcoded em vários lugares** (`index.html`,
   `equipe.html`, `representantes.html`, `geocode_por_cidade.py`,
   `criar_usuario_auth.py`). Isso é esperado (anon key é pública por design),
   mas serve de lembrete: não adianta "esconder" a anon key achando que isso é
   segurança — a segurança real está inteiramente nas policies RLS.
4. **Schema drift**: colunas/tabelas usadas em produção
   (`comercial_bmax_admins.perfil`, `comercial_bmax_cobertura.mesorregiao`,
   `comercial_bmax_log_revendas` inteira) não têm migration correspondente no
   repo. Antes de escrever uma migration nova, confira o schema real via MCP
   do Supabase ou SQL Editor — não confie que `migrations/` está completo.
5. **README desatualizado**: fala em Netlify/`app.boxersoldas.com.br`; a
   hospedagem real e ativa é Cloudflare Pages (`bmax-motor.pages.dev`), via
   Wrangler nos workflows do GitHub Actions.
6. **`scripts/criar_usuario_auth.py` tem senha em texto puro no arquivo**
   (`NEW_PASS`, `ANDRE_PASS`) — é um script histórico de setup (criação da
   conta do Adriel), não deveria ser reexecutado como está sem trocar as
   senhas ali hardcoded.
7. **Um job inteiro do pipeline diário foi desativado em produção e documentado
   inline** (`corrigir_banco_bmax.py`, comentado em
   `.github/workflows/atualizar_bmax.yml`): apagou de verdade uma filial
   legítima da revenda "Cascavel Soldas" (o dedupe por nome+cidade não vale
   mais porque revendas podem ter múltiplas filiais) e sobrescrevia a classe
   (ex. Diamante → Ouro) a partir de um `revendas_lista.json` estático e
   desatualizado, brigando com o Portal como fonte única de verdade. **Não
   reativar sem reescrever a lógica de dedupe/classe.**

## 8. Scripts Python em `scripts/`

Todos rodam do lado de fora do navegador (CI ou manual), usando a
`SUPABASE_SERVICE_KEY` (não a anon key) quando precisam escrever. Nenhum tem
teste automatizado.

| Script | Propósito (uma linha) | Executa via cron? |
|---|---|---|
| `sincronizar_excel_bmax.py` | Baixa `BMAX CRITERIOS.xlsx` do SharePoint (MSAL/Graph) e sincroniza revendas Ouro/Prata para `comercial_revendas_bmax`; nunca mexe em `ativo` (gerenciado só pelo Portal) | **Sim** — job 1 do workflow diário `atualizar_bmax.yml` |
| `importar_cobertura_bmax.py` | Importa `scripts/cobertura_bmax.json` (gerado do Excel de IBGE) para `comercial_bmax_cobertura` | **Sim** — job 4 do diário |
| `popular_ddd_cobertura.py` | Preenche a coluna `ddd` em `comercial_bmax_cobertura` via BrasilAPI, cruzando por nome de cidade; usa "chute" por estado quando não casa por nome exato | **Sim** — job 4 do diário, depois do anterior |
| `backup_revendas.py` | Dump de `comercial_revendas_bmax` para JSON, salvo como artefato do GitHub Actions | **Sim** — job 6 do diário, retenção de 30 dias |
| `baixar_bsis_sharepoint.py` | Baixa `bsis.db` (mesmo banco histórico do BAV) do SharePoint via MSAL | Só sob demanda — job 3 do diário, mas **condicionado a `workflow_dispatch`** (não roda no cron automático, só quando alguém dispara manualmente com "force_enrich") |
| `enriquecer_enderecos_bmax.py` | Enriquece revendas sem `zen_id`/CEP cruzando `bsis.db` (nome+cidade) para achar o ID de pessoa no ZEN, depois faz 1 chamada ZEN por match | Mesmo job condicional do anterior |
| `enrich_revendas_bmax.py` | Pipeline standalone ZEN→geocode→Supabase, citado no README como "rode na primeira vez"; parece ser a versão anterior/manual do que os jobs `enriquecer_enderecos_bmax.py`/`sincronizar_excel_bmax.py` fazem hoje no CI | Manual (não está em nenhum workflow atual) |
| `enriquecer_cep_zen.py` | Busca todas as filiais de cada revenda no ZEN a partir de `revendas_lista.json`, geocodifica (BrasilAPI→ViaCEP→Nominatim) e faz upsert por `zen_id` | Manual — não referenciado em workflow |
| `enriquecer_por_zen_id.py` | Atualiza as 8 revendas específicas do Excel que já têm ZEN ID conhecido, consolidando duplicatas | Manual, script pontual/histórico |
| `corrigir_endereco_luitex.py` | Correção pontual de um registro específico (Luitex, dois `id_cliente` de duas filiais) | Manual, script de correção única (histórico) |
| `corrigir_banco_bmax.py` | Sincronizava classe/rep de todas as revendas com `revendas_lista.json` e removia duplicatas por nome+cidade | **Desativado em produção** (ver seção 7, item 7) — existe no repo mas comentado fora do workflow |
| `geocode_por_cidade.py` | Geocodifica revendas sem lat/lng por cidade/estado via Nominatim, usando só a anon key (RLS aberto para leitura) | Manual |
| `criar_usuario_auth.py` | Script de setup único: cria conta Supabase Auth + admin para o Adriel | Manual, histórico (não reexecutar sem trocar as senhas hardcoded) |

O workflow `atualizar_bmax.yml` roda todo dia às 08:00 BRT (cron `0 11 * * *`)
e tem um job de alerta por email (Resend) que dispara para
`andre.coelho@boxersoldas.com.br` se qualquer etapa falhar. `deploy_on_push.yml`
só cuida do deploy do site estático quando `index.html`/`*.css`/`*.js` mudam
em `main`.

---

## Coisas que não consegui verificar / vale conferir

- Não tenho acesso à instância real do Supabase para confirmar o schema atual
  de `comercial_bmax_admins.perfil`, `comercial_bmax_cobertura.mesorregiao` e
  `comercial_bmax_log_revendas` (não estão em nenhuma migration do repo — ver
  seção 3.2). Rodar `list_tables`/`execute_sql` via MCP do Supabase resolveria
  isso rapidamente se precisar confiar 100% no schema.
- Não abri o repositório do Portal BMax nesta sessão para confirmar do lado
  dele que `comissao_tabela` é lida exatamente no formato `{classes, linhas}`
  — a memória do projeto já dava isso como resolvido, e o formato bate com o
  que o Motor grava/lê, mas não fiz a leitura cruzada linha a linha do código
  do Portal.
- Não testei em runtime (não tenho credencial de login) se `equipe.html` e
  `representantes.html` de fato retornam erro de RLS ao tentar salvar — a
  conclusão vem da leitura estática do código + das migrations, não de um
  teste real contra o Supabase.
- README.md também lista "17 PCIs" no cabeçalho e uma tabela de clusters com
  PCI16/PCI17 junto com "Lead Revenda (Boxer+Rev)" e "Lead Revenda (Rev
  lidera)" — o código atual (`PCIS`) só tem **16 entradas até PCI16**
  (PCI12 se desdobra em PCI12A/12B, não conta como PCI extra). Ou o README
  reflete uma versão anterior (V1) do critério, ou há uma pequena divergência
  de contagem entre documentação e código — não achei um "PCI17" em lugar
  nenhum do JS atual.
