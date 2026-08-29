-- =====================================================================
-- FASE 5 -- Correcciones sobre la exportación del 29/08/2026
-- =====================================================================
-- Ejecutar en el editor SQL de Supabase, por bloques y en orden.
--
-- AVISO SOBRE EL EDITOR DE SUPABASE: corta el resultado en 100 filas.
-- No avisa de que lo hace. Una consulta agrupada que devuelva exactamente
-- 100 filas casi seguro está truncada, y si va ordenada por categoría,
-- lo que se pierde es siempre el final del alfabeto. Ya pasó dos veces
-- en este proyecto: una hizo creer que no había ventas desde marzo, y
-- otra que no había ni un retiro del propietario en 18 meses -- cuando
-- en un solo mes hay trece. Cuando cuentes filas, usa count(*), no la
-- longitud de lo que se ve en pantalla.


-- ---------------------------------------------------------------------
-- 1. Gastos sin clasificar de agosto
-- ---------------------------------------------------------------------
-- 'AUSTRALERNS' es un laboratorio de lentes, igual que CERLENTS o QARZO.
update gastos_caja
   set categoria_gasto = 'LABORATORIO Y PROVEEDORES'
 where id_gasto = 4700;

-- 'GOTEROS Y SPRAYS 20ML' es lo mismo que 'DISTRISASAYO GOTEROS + SPRAYS'
-- (id 4362), que ya está en laboratorio y proveedores. Se igualan.
update gastos_caja
   set categoria_gasto = 'LABORATORIO Y PROVEEDORES'
 where id_gasto = 4718;

-- '6 UNIDADES COLA RATON' se deja SIN CLASIFICAR a propósito, pendiente
-- de confirmar qué es. En una óptica «cola de ratón» es el cordón para
-- colgar las gafas, que sería mercancía; pero también puede ser cola
-- para ratones, que sería aseo. Son categorías distintas y la
-- descripción no lo resuelve. Cuando lo confirmes:
--   update gastos_caja set categoria_gasto = 'LABORATORIO Y PROVEEDORES'
--    where id_gasto = 4748;   -- si es cordón para gafas
--   update gastos_caja set categoria_gasto = 'ASEO E INSUMOS'
--    where id_gasto = 4748;   -- si es cola para ratones


-- ---------------------------------------------------------------------
-- 2. Un almuerzo no son honorarios
-- ---------------------------------------------------------------------
-- 'PAGO ALMUERZO OPTOMETRA' estaba en HONORARIOS POR CONSULTA. Invitar a
-- almorzar a la optómetra no es pagarle la consulta: mezclarlo hace
-- parecer que las consultas cuestan más de lo que cuestan.
update gastos_caja
   set categoria_gasto = 'ALIMENTACION'
 where id_gasto = 4726;

-- 'CAFE BOLSITA+ VASOS' estaba en ASEO E INSUMOS. Manda el café.
update gastos_caja
   set categoria_gasto = 'ALIMENTACION'
 where id_gasto = 4793;


-- ---------------------------------------------------------------------
-- 3. Tres gastos fechados en noviembre  [REVISAR ANTES]
-- ---------------------------------------------------------------------
-- Vienen de la migración (método de pago 'DESCONOCIDO', hora a
-- medianoche) y están fechados el 13 de noviembre de 2026, que aún no ha
-- llegado. Son $735.000, y el más grande es un abono de $700.000.
select id_gasto, fecha_gasto, descripcion, monto, categoria_gasto
  from gastos_caja
 where fecha_gasto > now()
 order by fecha_gasto;

-- Mira en el Excel original de qué día son y descomenta con la fecha
-- correcta. NO se corrigen a ciegas: un abono de $700.000 movido al mes
-- equivocado desordena dos meses en vez de uno.
-- update gastos_caja set fecha_gasto = '2026-01-13 00:00:00-05' where id_gasto = 4360;
-- update gastos_caja set fecha_gasto = '2026-01-13 00:00:00-05' where id_gasto = 4361;
-- update gastos_caja set fecha_gasto = '2026-01-13 00:00:00-05' where id_gasto = 4362;


-- ---------------------------------------------------------------------
-- 4. Un pago registrado dos veces  [REVISAR ANTES]
-- ---------------------------------------------------------------------
-- 'PAGO NOMINA ROSA' de $40.000 aparece dos veces el 24/08 con UN SEGUNDO
-- de diferencia (id 4789 y 4790). Un segundo no es tiempo suficiente para
-- escribir el mismo gasto dos veces: es un doble clic en Guardar.
select id_gasto, fecha_gasto, descripcion, monto, metodo_pago
  from gastos_caja
 where id_gasto in (4789, 4790);

-- Si confirmas que fue un solo pago, se borra el segundo:
-- delete from gastos_caja where id_gasto = 4790;


-- ---------------------------------------------------------------------
-- 5. Comprobación
-- ---------------------------------------------------------------------
select coalesce(categoria_gasto, 'SIN CLASIFICAR') as categoria,
       count(*) as filas,
       sum(monto) as total
  from gastos_caja
 where fecha_gasto >= date '2026-08-01'
 group by 1
 order by total desc;
