-- BMax — Lote 7: fecha a RLS de escrita das 4 tabelas migradas para o Portal
-- Execute no SQL Editor do Supabase (projeto boxer-sistemas, ref bmepxcnrsofofoswubuu)
--
-- Pré-requisito (já feito): o Portal passou a escrever nessas tabelas usando a
-- chave service_role (SUPABASE_SERVICE_KEY_SISTEMAS), não mais a anon key que
-- o Motor também usa. Sem isso, travar aqui quebraria o Portal junto.
--
-- Leitura (SELECT) continua pública — o Motor só lê essas tabelas, nunca escreve.

DROP POLICY IF EXISTS "vendedores_write" ON comercial_bmax_vendedores;
CREATE POLICY "vendedores_write" ON comercial_bmax_vendedores
  FOR ALL USING (auth.role() = 'service_role');

DROP POLICY IF EXISTS "bmax_rev_write" ON comercial_revendas_bmax;
CREATE POLICY "bmax_rev_write" ON comercial_revendas_bmax
  FOR ALL USING (auth.role() = 'service_role');

DROP POLICY IF EXISTS "cobertura_write" ON comercial_bmax_cobertura;
DROP POLICY IF EXISTS "Authenticated can update cobertura" ON comercial_bmax_cobertura;
CREATE POLICY "cobertura_write" ON comercial_bmax_cobertura
  FOR ALL USING (auth.role() = 'service_role');

DROP POLICY IF EXISTS "bmax_cfg_write" ON comercial_bmax_config;
CREATE POLICY "bmax_cfg_write" ON comercial_bmax_config
  FOR ALL USING (auth.role() = 'service_role');
