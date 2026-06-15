-- ============================================================
-- BMax Motor PCI — Tabelas Supabase (projeto boxer-sistemas)
-- Prefixo: comercial_  |  Execute no SQL Editor do Supabase
-- ============================================================

-- 1. REVENDAS BMAX -----------------------------------------
CREATE TABLE IF NOT EXISTS comercial_revendas_bmax (
  id             uuid DEFAULT gen_random_uuid() PRIMARY KEY,
  zen_id         text,
  nome           text NOT NULL,
  nome_fantasia  text,
  rep            text,
  cidade         text,
  estado         text,
  cep            text,
  lat            double precision,
  lng            double precision,
  classe         text DEFAULT 'Prata' CHECK (classe IN ('Ouro','Prata','Não Aplica')),
  zen_group      text,
  ativo          boolean DEFAULT true,
  criado_em      timestamptz DEFAULT now(),
  atualizado_em  timestamptz DEFAULT now()
);

ALTER TABLE comercial_revendas_bmax ENABLE ROW LEVEL SECURITY;

-- Leitura pública (necessário para o motor sem login ainda carregado)
CREATE POLICY "bmax_rev_select" ON comercial_revendas_bmax
  FOR SELECT USING (true);

-- Escrita apenas para usuários autenticados
CREATE POLICY "bmax_rev_write" ON comercial_revendas_bmax
  FOR ALL USING (auth.role() = 'authenticated');

-- Trigger para atualizar atualizado_em
CREATE OR REPLACE FUNCTION set_atualizado_em()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN NEW.atualizado_em = now(); RETURN NEW; END;
$$;

CREATE TRIGGER trg_bmax_rev_updated
  BEFORE UPDATE ON comercial_revendas_bmax
  FOR EACH ROW EXECUTE FUNCTION set_atualizado_em();

-- 2. CONFIGURAÇÕES ----------------------------------------
CREATE TABLE IF NOT EXISTS comercial_bmax_config (
  id           uuid DEFAULT gen_random_uuid() PRIMARY KEY,
  chave        text UNIQUE NOT NULL,
  valor        text NOT NULL,
  descricao    text,
  criado_em    timestamptz DEFAULT now(),
  atualizado_em timestamptz DEFAULT now()
);

ALTER TABLE comercial_bmax_config ENABLE ROW LEVEL SECURITY;

CREATE POLICY "bmax_cfg_select" ON comercial_bmax_config
  FOR SELECT USING (true);

CREATE POLICY "bmax_cfg_write" ON comercial_bmax_config
  FOR ALL USING (auth.role() = 'authenticated');

-- Valores padrão
INSERT INTO comercial_bmax_config (chave, valor, descricao) VALUES
  ('raio_km',      '50',     'Raio máximo revenda (km)'),
  ('nf_threshold', '50000',  'Limiar de valor de NF (R$)'),
  ('vinculo_dias', '120',    'Prazo de vínculo após validação'),
  ('rep_pct_r1',   '1',      'Comissão rep — Robô/Laser múltiplo'),
  ('rep_pct_r3a',  '3',      'Comissão rep — Laser simples c/ revenda'),
  ('rep_pct_r3b',  '3',      'Comissão rep — Máquina ≥50k c/ revenda'),
  ('rep_pct_r5',   '5',      'Comissão rep — Máquina <50k'),
  ('vi_pct',       '1.2',    'Comissão Vendedor Interno')
ON CONFLICT (chave) DO NOTHING;

-- 3. CLASSIFICAÇÕES (log de uso) --------------------------
CREATE TABLE IF NOT EXISTS comercial_bmax_classificacoes (
  id             uuid DEFAULT gen_random_uuid() PRIMARY KEY,
  usuario_email  text,
  pci_id         text NOT NULL,
  produto        text,
  origem         text,
  condutor       text,
  cep_lead       text,
  cidade_lead    text,
  estado_lead    text,
  lat_lead       double precision,
  lng_lead       double precision,
  resultado      jsonb,
  ativo          boolean DEFAULT true,
  criado_em      timestamptz DEFAULT now()
);

ALTER TABLE comercial_bmax_classificacoes ENABLE ROW LEVEL SECURITY;

CREATE POLICY "bmax_cls_select" ON comercial_bmax_classificacoes
  FOR SELECT USING (auth.role() = 'authenticated');

CREATE POLICY "bmax_cls_insert" ON comercial_bmax_classificacoes
  FOR INSERT WITH CHECK (auth.role() = 'authenticated');

-- 4. LOG DE ALTERAÇÕES (padrão Boxer) ---------------------
CREATE TABLE IF NOT EXISTS log_alteracoes (
  id              uuid DEFAULT gen_random_uuid() PRIMARY KEY,
  usuario_id      uuid,
  usuario_email   text,
  tabela_ref      text,
  registro_id     text,
  campo           text,
  valor_anterior  text,
  valor_novo      text,
  criado_em       timestamptz DEFAULT now()
);

ALTER TABLE log_alteracoes ENABLE ROW LEVEL SECURITY;

CREATE POLICY "log_insert" ON log_alteracoes
  FOR INSERT WITH CHECK (auth.role() = 'authenticated');

CREATE POLICY "log_select" ON log_alteracoes
  FOR SELECT USING (auth.role() = 'authenticated');
