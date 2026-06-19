-- BMax Motor — Tabela de administradores
-- Execute no SQL Editor do Supabase (projeto bmepxcnrsofofoswubuu)

CREATE TABLE IF NOT EXISTS comercial_bmax_admins (
  id        serial PRIMARY KEY,
  email     text NOT NULL UNIQUE,
  nome      text,
  ativo     boolean DEFAULT true,
  criado_em timestamptz DEFAULT now()
);

ALTER TABLE comercial_bmax_admins ENABLE ROW LEVEL SECURITY;

-- Admins veem todos os rows ativos; não-admins não veem nada
DO $$ BEGIN
  CREATE POLICY "bmax_admins_select" ON comercial_bmax_admins
    FOR SELECT USING (
      EXISTS (SELECT 1 FROM comercial_bmax_admins a WHERE a.email = auth.email() AND a.ativo = true)
    );
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- Admins existentes podem inserir novos admins
DO $$ BEGIN
  CREATE POLICY "bmax_admins_insert" ON comercial_bmax_admins
    FOR INSERT WITH CHECK (
      EXISTS (SELECT 1 FROM comercial_bmax_admins WHERE email = auth.email() AND ativo = true)
    );
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- Admins existentes podem desativar outros admins (UPDATE)
DO $$ BEGIN
  CREATE POLICY "bmax_admins_update" ON comercial_bmax_admins
    FOR UPDATE USING (
      EXISTS (SELECT 1 FROM comercial_bmax_admins WHERE email = auth.email() AND ativo = true)
    );
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- Seed: André como primeiro admin
INSERT INTO comercial_bmax_admins (email, nome) VALUES
  ('andre.coelho@boxersoldas.com.br', 'André')
ON CONFLICT (email) DO NOTHING;
