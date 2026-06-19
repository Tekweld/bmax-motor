-- BMax Motor — Schema updates
-- Execute no SQL Editor do Supabase (projeto bmepxcnrsofofoswubuu)

-- 0. Adicionar coluna endereco à tabela de revendas (ausente no schema original)
ALTER TABLE comercial_revendas_bmax ADD COLUMN IF NOT EXISTS endereco text;

-- 1. Adicionar coluna DDD à tabela de cobertura
ALTER TABLE comercial_bmax_cobertura ADD COLUMN IF NOT EXISTS ddd smallint;

-- 2. Criar tabela de vendedores Boxer
CREATE TABLE IF NOT EXISTS comercial_bmax_vendedores (
  id        serial PRIMARY KEY,
  nome      text NOT NULL,
  tipo      text NOT NULL CHECK (tipo IN ('VI', 'VT1', 'VT2')),
  cor       text NOT NULL DEFAULT '#60a5fa',
  ddds      integer[],
  fallback  boolean DEFAULT false,
  ativo     boolean DEFAULT true,
  criado_em timestamptz DEFAULT now()
);

ALTER TABLE comercial_bmax_vendedores ENABLE ROW LEVEL SECURITY;

CREATE POLICY IF NOT EXISTS "vendedores_select" ON comercial_bmax_vendedores
  FOR SELECT USING (true);

CREATE POLICY IF NOT EXISTS "vendedores_write" ON comercial_bmax_vendedores
  FOR ALL USING (auth.role() = 'service_role');

-- 3. Seed inicial (idempotente — só insere se tabela vazia)
INSERT INTO comercial_bmax_vendedores (nome, tipo, cor, ddds, fallback, ativo)
SELECT * FROM (VALUES
  ('Max',    'VT1'::text, '#25bbee', ARRAY[12,13,14,15,19]::integer[], false, true),
  ('Lucas',  'VT2'::text, '#f59e0b', ARRAY[16,17,18,35]::integer[],    false, true),
  ('Carlos', 'VI'::text,  '#718096', NULL::integer[],                  true,  true)
) AS v(nome, tipo, cor, ddds, fallback, ativo)
WHERE NOT EXISTS (SELECT 1 FROM comercial_bmax_vendedores LIMIT 1);
