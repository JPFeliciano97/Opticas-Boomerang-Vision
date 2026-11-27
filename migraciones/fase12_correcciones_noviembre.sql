-- =====================================================================
-- FASE 12 -- Correcciones de noviembre
-- =====================================================================
-- Columnas nuevas para los arreglos pedidos. Todas con "if not exists":
-- correr el archivo dos veces no rompe nada.
--
-- La aplicación funciona ANTES y DESPUÉS de correr esto: cada sitio que
-- usa una columna nueva comprueba primero si existe, y si no está,
-- esconde esa parte en vez de fallar. Así que no hay prisa, pero hasta
-- que no se corra, lo de abajo no se ve.
--
-- EJECUTAR POR BLOQUES Y EN ORDEN. El bloque 5 solo mira.


-- ---------------------------------------------------------------------
-- 1. Observaciones propias de la factura
-- ---------------------------------------------------------------------
-- El recuadro OBS del papel se llenaba con las observaciones de la
-- HISTORIA CLÍNICA, que son otra cosa -- el diagnóstico del paciente no
-- tiene por qué ir en un documento de cobro -- y no había ningún sitio
-- donde escribir una nota de la venta.
alter table ventas_facturacion
  add column if not exists observaciones text;


-- ---------------------------------------------------------------------
-- 2. Anular un abono a un laboratorio
-- ---------------------------------------------------------------------
-- Un abono solo se podía crear. Un cero de más, o un abono cargado a la
-- factura equivocada, no tenían arreglo desde la aplicación.
--
-- No se borra: se marca. Así queda el rastro de que existió y de quién
-- lo deshizo. Como el saldo de cada factura se calcula sumando sus
-- abonos, con marcarlo la deuda vuelve sola a su sitio.
alter table pagos_laboratorio
  add column if not exists estado text default 'ACTIVO',
  add column if not exists modificado_por text,
  add column if not exists modificado_fecha timestamptz;

update pagos_laboratorio set estado = 'ACTIVO' where estado is null;


-- ---------------------------------------------------------------------
-- 3. Anular el gasto que nació con el abono
-- ---------------------------------------------------------------------
-- Cada abono a un laboratorio crea además un gasto. Si se anula el abono
-- y el gasto se queda, la analítica sigue contando una plata que no
-- salió. Los dos se mueven juntos.
alter table gastos_caja
  add column if not exists estado text default 'ACTIVO';

update gastos_caja set estado = 'ACTIVO' where estado is null;


-- ---------------------------------------------------------------------
-- 4. La Rx de lentes de contacto
-- ---------------------------------------------------------------------
-- Se guardaba en las observaciones, mezclada con todo lo demás, o no se
-- guardaba. En columnas propias se puede consultar y comparar entre un
-- control y el siguiente.
--
-- El cilindro va en numeric y siempre negativo; vacío significa que la
-- lente es esférica. El eje solo cuenta si hay cilindro.
alter table historias_clinicas
  add column if not exists lc_esfera_od   numeric,
  add column if not exists lc_cilindro_od numeric,
  add column if not exists lc_eje_od      integer,
  add column if not exists lc_esfera_oi   numeric,
  add column if not exists lc_cilindro_oi numeric,
  add column if not exists lc_eje_oi      integer,
  add column if not exists lc_marca       text;

-- Hace falta para saber cuál se corrigió más tarde, la fórmula de la
-- historia o la copia que guardó la factura: la reimpresión usa la
-- última de las dos.
alter table historias_clinicas
  add column if not exists modificado_por   text,
  add column if not exists modificado_fecha timestamptz;

alter table ventas_facturacion
  add column if not exists modificado_por   text,
  add column if not exists modificado_fecha timestamptz;


-- ---------------------------------------------------------------------
-- 5. Comprobación  [CONSULTA]
-- ---------------------------------------------------------------------
-- Las doce columnas nuevas tienen que salir aquí. Si falta alguna, el
-- bloque que la crea no se corrió.
select table_name, column_name, data_type
  from information_schema.columns
 where (table_name = 'ventas_facturacion' and column_name in
          ('observaciones', 'modificado_por', 'modificado_fecha'))
    or (table_name = 'pagos_laboratorio'  and column_name in
          ('estado', 'modificado_por', 'modificado_fecha'))
    or (table_name = 'gastos_caja'        and column_name = 'estado')
    or (table_name = 'historias_clinicas' and column_name like 'lc\_%')
 order by table_name, column_name;


-- ---------------------------------------------------------------------
-- 6. Marcha atrás
-- ---------------------------------------------------------------------
-- alter table ventas_facturacion drop column if exists observaciones;
-- alter table pagos_laboratorio  drop column if exists estado;
-- alter table gastos_caja        drop column if exists estado;
-- alter table historias_clinicas
--   drop column if exists lc_esfera_od,   drop column if exists lc_cilindro_od,
--   drop column if exists lc_eje_od,      drop column if exists lc_esfera_oi,
--   drop column if exists lc_cilindro_oi, drop column if exists lc_eje_oi,
--   drop column if exists lc_marca;
