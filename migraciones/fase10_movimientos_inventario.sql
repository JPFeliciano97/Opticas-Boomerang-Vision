-- =====================================================================
-- FASE 10 -- Historial de movimientos de inventario
-- =====================================================================
-- Hasta ahora el inventario guardaba una cantidad, no una historia. Si
-- un producto decía 3 y se habían comprado 10, no había forma de saber
-- a dónde fueron los otros siete: cuántos se vendieron, cuántos se
-- rompieron, cuántos fueron un error de conteo.
--
-- Esta migración añade dos cosas:
--   1. La tabla movimientos_inventario, el libro de entradas y salidas.
--   2. La columna 'estado' en inventario, para poder descontinuar un
--      producto creado por error sin borrarlo.
--
-- La app funciona antes y después de correrla: comprueba con
-- tabla_existe() y columna_existe() antes de usarlas. Sin ella no hay
-- historial ni se pueden descontinuar productos, y todo lo demás va
-- igual.
--
-- Ejecutar por bloques y en orden.


-- ---------------------------------------------------------------------
-- 1. El libro de movimientos
-- ---------------------------------------------------------------------
-- 'delta' es el movimiento con signo: positivo entra, negativo sale.
-- 'cantidad_resultante' guarda en cuánto quedó el producto DESPUÉS del
-- movimiento. Es redundante -- se podría sumar -- pero es lo que permite
-- leer una fila suelta y entenderla sin recorrer toda la historia.
create table if not exists movimientos_inventario (
    id_movimiento       bigint generated always as identity primary key,
    codigo              text        not null,
    fecha               timestamptz not null default now(),
    delta               integer     not null check (delta <> 0),
    cantidad_resultante integer     not null,
    motivo              text,
    -- Cuando el movimiento viene de una venta. Es lo que permite que
    -- anular devuelva exactamente lo que esa factura sacó, en vez de
    -- suponer que fueron una montura y un estuche.
    numero_factura      text,
    registrado_por      text
);

create index if not exists idx_movinv_codigo  on movimientos_inventario (codigo);
create index if not exists idx_movinv_fecha   on movimientos_inventario (fecha desc);
create index if not exists idx_movinv_factura on movimientos_inventario (numero_factura);

-- RLS, como el resto de las tablas (ver fase 7). La app entra con
-- service_role, que se salta RLS; quien tenga solo la llave anon no ve
-- nada.
alter table movimientos_inventario enable row level security;


-- ---------------------------------------------------------------------
-- 2. Saldo inicial: la historia empieza con lo que hay hoy
-- ---------------------------------------------------------------------
-- Sin esto, la suma de los movimientos de un producto nunca coincidiría
-- con su cantidad, y la comprobación de cuadre de la app marcaría todo
-- como descuadrado desde el primer día.
--
-- Se apunta el stock actual como una entrada de saldo inicial. No es
-- inventarse nada: es dejar dicho que la historia arranca aquí.
insert into movimientos_inventario
       (codigo, fecha, delta, cantidad_resultante, motivo, registrado_por)
select i.codigo,
       now(),
       i.cantidad,
       i.cantidad,
       'Saldo inicial al empezar el historial',
       'Migración'
  from inventario i
 where coalesce(i.cantidad, 0) <> 0
   and not exists (select 1 from movimientos_inventario m
                    where m.codigo = i.codigo);


-- ---------------------------------------------------------------------
-- 3. Descontinuar productos
-- ---------------------------------------------------------------------
-- ACTIVO o DESCONTINUADO. Un producto creado por error no se borra: deja
-- de aparecer en el catálogo y en los ajustes, no cuenta en los totales,
-- y se puede reactivar. Su historial se conserva.
alter table inventario
  add column if not exists estado text not null default 'ACTIVO';


-- ---------------------------------------------------------------------
-- 4. Comprobación  [CONSULTA]
-- ---------------------------------------------------------------------
-- La cantidad de cada producto debe coincidir con la suma de sus
-- movimientos. Esperado: cero filas.
select i.codigo,
       i.cantidad                       as dice_el_inventario,
       coalesce(sum(m.delta), 0)        as suman_los_movimientos,
       i.cantidad - coalesce(sum(m.delta), 0) as diferencia
  from inventario i
  left join movimientos_inventario m on m.codigo = i.codigo
 group by i.codigo, i.cantidad
having i.cantidad <> coalesce(sum(m.delta), 0)
 order by abs(i.cantidad - coalesce(sum(m.delta), 0)) desc;


-- ---------------------------------------------------------------------
-- 5. Cuántos movimientos quedaron  [CONSULTA]
-- ---------------------------------------------------------------------
select count(*) as movimientos, count(distinct codigo) as productos
  from movimientos_inventario;


-- ---------------------------------------------------------------------
-- 6. Marcha atrás
-- ---------------------------------------------------------------------
-- Borra el historial y la columna de estado. El stock NO se toca: vive
-- en inventario.cantidad y esta migración nunca lo modifica.
--
-- drop table if exists movimientos_inventario;
-- alter table inventario drop column if exists estado;
