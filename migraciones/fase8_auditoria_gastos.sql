-- =====================================================================
-- FASE 8 -- Auditoría en gastos_caja
-- =====================================================================
-- Reclasificar un gasto cambia en qué casilla cae el dinero, y de esas
-- casillas salen las gráficas del mes. Es una edición de un dato ya
-- guardado, así que debería dejar rastro de quién la hizo -- igual que
-- ya lo dejan las ventas, las historias clínicas y los pacientes.
--
-- gastos_caja es la única tabla editable que no tiene esas columnas.
-- Mientras no se corran, la app NO firma esos cambios: lo comprueba con
-- columna_existe() antes de escribir, así que correr esto es opcional y
-- no romper nada si no se corre. En cuanto existan, empieza a firmar
-- sola, sin tocar el código.


-- ---------------------------------------------------------------------
-- 1. ¿Están ya?  [CONSULTA]
-- ---------------------------------------------------------------------
select column_name, data_type
  from information_schema.columns
 where table_schema = 'public'
   and table_name = 'gastos_caja'
   and column_name in ('modificado_por', 'modificado_fecha');


-- ---------------------------------------------------------------------
-- 2. Crearlas
-- ---------------------------------------------------------------------
-- Nulas a propósito: las filas que ya existen no las tocó nadie desde el
-- sistema, y rellenarlas con un nombre inventado sería peor que dejarlas
-- vacías. Vacío aquí significa "nunca se editó", que es la verdad.
alter table gastos_caja
  add column if not exists modificado_por   text,
  add column if not exists modificado_fecha timestamptz;


-- ---------------------------------------------------------------------
-- 3. Comprobación
-- ---------------------------------------------------------------------
-- Deben salir las dos filas. Después, reclasifica un gasto cualquiera
-- desde la app y vuelve a mirar: esa fila debe quedar con tu nombre.
select column_name, data_type, is_nullable
  from information_schema.columns
 where table_schema = 'public'
   and table_name = 'gastos_caja'
   and column_name in ('modificado_por', 'modificado_fecha')
 order by column_name;


-- ---------------------------------------------------------------------
-- 4. Marcha atrás
-- ---------------------------------------------------------------------
-- alter table gastos_caja
--   drop column if exists modificado_por,
--   drop column if exists modificado_fecha;
