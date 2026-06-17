-- BMax Motor — Tabela de configuração/estado do pipeline
-- Execute no SQL Editor do Supabase (projeto bmepxcnrsofofoswubuu)

CREATE TABLE IF NOT EXISTS comercial_bmax_config (
  chave        text PRIMARY KEY,
  valor        text,
  atualizado_em timestamptz DEFAULT now()
);

ALTER TABLE comercial_bmax_config ENABLE ROW LEVEL SECURITY;

CREATE POLICY "config_select" ON comercial_bmax_config
  FOR SELECT USING (true);

CREATE POLICY "config_write" ON comercial_bmax_config
  FOR ALL USING (auth.role() = 'service_role');
