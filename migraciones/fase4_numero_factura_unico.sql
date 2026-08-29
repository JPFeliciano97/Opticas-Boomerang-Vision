-- =====================================================================
-- FASE 4 -- Un número de factura no puede repetirse
-- =====================================================================
-- Ejecutar en el editor SQL de Supabase, por bloques y en orden.
--
-- El número de factura se calcula en la app como "el mayor que exista,
-- más uno", y luego se comprueba con una consulta aparte antes de
-- guardar. Entre esa comprobación y el guardado pasa tiempo -- el que
-- tarda quien factura en llenar el resto del formulario -- y en ese rato
-- otra persona puede estar facturando en otro computador. Los dos ven el
-- mismo número libre, los dos pasan la comprobación, los dos guardan.
--
-- Eso no se arregla en la app: mientras la comprobación y el guardado
-- sean dos pasos, siempre habrá un hueco entre ellos. Se arregla en la
-- base de datos, que es la única que puede decidir quién llegó primero.


-- ---------------------------------------------------------------------
-- 1. ¿Ya hay duplicados?  [CONSULTA]
-- ---------------------------------------------------------------------
-- El bloque 2 falla si existe aunque sea uno. Míralos primero: hay que
-- decidir qué hacer con cada uno (renumerar el segundo, o anularlo si
-- resultó ser la misma venta guardada dos veces).
select numero_factura,
       count(*)                    as veces,
       min(fecha_venta)            as primera,
       max(fecha_venta)            as ultima,
       string_agg(distinct titular_nombre, ' | ') as titulares
  from ventas_facturacion
 group by numero_factura
having count(*) > 1
 order by veces desc, numero_factura;


-- ---------------------------------------------------------------------
-- 2. La restricción
-- ---------------------------------------------------------------------
-- Solo si el bloque 1 no devolvió nada. A partir de aquí, el segundo
-- intento de guardar un número repetido lo rechaza Postgres, y la app
-- muestra el error en vez de crear la factura gemela en silencio.
alter table ventas_facturacion
  add constraint ventas_facturacion_numero_unico unique (numero_factura);


-- ---------------------------------------------------------------------
-- 3. Comprobación
-- ---------------------------------------------------------------------
select conname as restriccion, contype as tipo
  from pg_constraint
 where conrelid = 'ventas_facturacion'::regclass
   and conname = 'ventas_facturacion_numero_unico';


-- ---------------------------------------------------------------------
-- 4. Para deshacerlo
-- ---------------------------------------------------------------------
-- alter table ventas_facturacion
--   drop constraint ventas_facturacion_numero_unico;
