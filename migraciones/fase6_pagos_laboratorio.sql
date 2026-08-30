-- =====================================================================
-- FASE 6 -- Cuentas por pagar a laboratorios
-- =====================================================================
-- Ejecutar en el editor SQL de Supabase, por bloques y en orden.
--
-- El flujo que esto modela es el real: se mandan varios trabajos a un
-- laboratorio, el laboratorio pasa UNA factura por todos, y esa factura se
-- paga de una vez o en abonos. La unidad de la deuda es la factura del
-- laboratorio, no el trabajo, porque el sistema no sabe cuánto cobra el
-- laboratorio por cada trabajo -- eso solo aparece en su factura.
--
-- Hasta ahora un pago a laboratorio era solo un gasto en caja: se veía
-- cuánto se pagó, nunca cuánto quedaba debiendo.


-- ---------------------------------------------------------------------
-- 1. Las facturas que emite el laboratorio
-- ---------------------------------------------------------------------
create table if not exists facturas_laboratorio (
    id_factura_lab      bigint generated always as identity primary key,
    laboratorio         text        not null,
    numero_factura_lab  text,
    fecha_factura       date        not null,
    fecha_vencimiento   date,
    total               numeric     not null check (total > 0),
    -- ACTIVA o ANULADA. Si está pagada o no NO se guarda aquí: se calcula
    -- sumando sus pagos. Un dato que se puede calcular y además se guarda
    -- acaba desincronizándose, y entonces hay dos verdades.
    estado              text        not null default 'ACTIVA',
    observaciones       text,
    creado_por          text,
    fecha_creacion      timestamptz not null default now(),
    modificado_por      text,
    modificado_fecha    timestamptz
);

create index if not exists idx_flab_laboratorio on facturas_laboratorio (laboratorio);
create index if not exists idx_flab_fecha       on facturas_laboratorio (fecha_factura desc);


-- ---------------------------------------------------------------------
-- 2. Los abonos que se le hacen a cada factura
-- ---------------------------------------------------------------------
-- 'id_gasto' apunta al gasto que el pago creó en gastos_caja. Es lo que
-- permite comprobar que el dinero salió una sola vez: cada abono aquí
-- tiene su gasto allá, y ninguno de los dos existe sin el otro.
create table if not exists pagos_laboratorio (
    id_pago         bigint generated always as identity primary key,
    id_factura_lab  bigint      not null
                    references facturas_laboratorio (id_factura_lab) on delete cascade,
    fecha_pago      timestamptz not null default now(),
    monto           numeric     not null check (monto > 0),
    metodo_pago     text,
    id_gasto        bigint,
    registrado_por  text
);

create index if not exists idx_plab_factura on pagos_laboratorio (id_factura_lab);


-- ---------------------------------------------------------------------
-- 3. Comprobación
-- ---------------------------------------------------------------------
select table_name, column_name, data_type
  from information_schema.columns
 where table_name in ('facturas_laboratorio', 'pagos_laboratorio')
 order by table_name, ordinal_position;


-- ---------------------------------------------------------------------
-- 4. Lo que se debe a cada laboratorio  [CONSULTA]
-- ---------------------------------------------------------------------
-- La misma cuenta que hace la app, por si se quiere revisar desde aquí.
select f.laboratorio,
       count(*)                                          as facturas,
       sum(f.total)                                      as facturado,
       coalesce(sum(p.abonado), 0)                       as abonado,
       sum(f.total) - coalesce(sum(p.abonado), 0)        as saldo
  from facturas_laboratorio f
  left join (select id_factura_lab, sum(monto) as abonado
               from pagos_laboratorio group by id_factura_lab) p
         on p.id_factura_lab = f.id_factura_lab
 where f.estado = 'ACTIVA'
 group by f.laboratorio
having sum(f.total) - coalesce(sum(p.abonado), 0) > 0
 order by saldo desc;


-- ---------------------------------------------------------------------
-- 5. Para deshacerlo
-- ---------------------------------------------------------------------
-- Borra las dos tablas y todo lo que tengan dentro. Los gastos que se
-- hayan creado en gastos_caja NO se tocan: son dinero que salió de
-- verdad y siguen siendo validos por su cuenta.
-- drop table if exists pagos_laboratorio;
-- drop table if exists facturas_laboratorio;
