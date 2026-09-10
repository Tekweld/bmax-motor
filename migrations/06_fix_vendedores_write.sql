-- BMax Motor — Corrige RLS de escrita em comercial_bmax_vendedores
-- Execute no SQL Editor do Supabase (projeto boxer-sistemas, ref bmepxcnrsofofoswubuu)
--
-- Bug: a policy original (04_schema_updates.sql) exigia auth.role() = 'service_role'
-- para INSERT/UPDATE/DELETE, mas o Motor (equipe.html/index.html) grava via chave
-- anon (sbClient), autenticado como 'authenticated' — nunca como service_role.
-- Resultado: "new row violates row-level security policy for table
-- comercial_bmax_vendedores" em qualquer tentativa de cadastro/edição.
--
-- Fix: alinhar com o padrão já usado em comercial_revendas_bmax, comercial_bmax_config
-- e comercial_bmax_cobertura (todas com auth.role() = 'authenticated').

DROP POLICY IF EXISTS "vendedores_write" ON comercial_bmax_vendedores;

CREATE POLICY "vendedores_write" ON comercial_bmax_vendedores
  FOR ALL USING (auth.role() = 'authenticated');
