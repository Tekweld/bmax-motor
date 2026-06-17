-- ============================================================
-- BMax Motor — Tabela de cobertura de representantes por cidade
-- Execute no SQL Editor do Supabase (projeto bmepxcnrsofofoswubuu)
-- ============================================================

CREATE TABLE IF NOT EXISTS comercial_bmax_cobertura (
  ibge_codigo  text PRIMARY KEY,
  cidade       text NOT NULL,
  estado       text NOT NULL,
  rep_bmax     text,
  ativo        boolean DEFAULT true,
  criado_em    timestamptz DEFAULT now()
);

ALTER TABLE comercial_bmax_cobertura ENABLE ROW LEVEL SECURITY;

CREATE POLICY "cobertura_select" ON comercial_bmax_cobertura
  FOR SELECT USING (true);

CREATE POLICY "cobertura_write" ON comercial_bmax_cobertura
  FOR ALL USING (auth.role() = 'service_role');
