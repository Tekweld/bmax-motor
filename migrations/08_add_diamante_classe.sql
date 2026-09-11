-- BMax — adiciona 'Diamante' à constraint de classe de comercial_revendas_bmax
-- Execute no SQL Editor do Supabase (projeto boxer-sistemas, ref bmepxcnrsofofoswubuu)
--
-- Bug: a constraint original (01_create_tables.sql) só permitia
-- 'Ouro'/'Prata'/'Não Aplica', mas o formulário de revenda (Portal e Motor)
-- sempre ofereceu "Diamante" como opção, com campos extras específicos
-- (mesorregiao_ibge, demonstrador_nome). Nunca dava pra salvar de verdade —
-- só ninguém tinha tentado até 2026-09-11 (erro 23514 ao cadastrar
-- "Cascavel Soldas" como Diamante).

ALTER TABLE comercial_revendas_bmax DROP CONSTRAINT comercial_revendas_bmax_classe_check;

ALTER TABLE comercial_revendas_bmax ADD CONSTRAINT comercial_revendas_bmax_classe_check
  CHECK (classe = ANY (ARRAY['Ouro'::text, 'Prata'::text, 'Diamante'::text, 'Não Aplica'::text]));
