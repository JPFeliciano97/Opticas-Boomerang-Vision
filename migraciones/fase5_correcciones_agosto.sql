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

-- '6 UNIDADES COLA RATON': confirmado por el negocio que es un accesorio
-- antideslizante de silicona para las gafas. Es mercancía, no aseo.
update gastos_caja
   set categoria_gasto = 'LABORATORIO Y PROVEEDORES'
 where id_gasto = 4748;


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

-- 3b. De qué día son en realidad  [CONSULTA]
-- No hace falta abrir el Excel. Las tres filas son consecutivas -- 4360,
-- 4361 y 4362 -- así que entraron juntas en la migración, y la migración
-- cargó los gastos en orden de fecha. Sus vecinas de id delatan el día:
-- si la 4359 es del 12 de enero y la 4363 del 13, las tres del medio son
-- de esa misma fecha y no de noviembre.
select id_gasto,
       fecha_gasto,
       to_char(fecha_gasto at time zone 'America/Bogota', 'YYYY-MM-DD') as dia,
       descripcion,
       monto,
       case when id_gasto between 4360 and 4362 then '<<< LAS TRES' end as marca
  from gastos_caja
 where id_gasto between 4350 and 4372
 order by id_gasto;

-- 3c. Resuelto: son del 13 de FEBRERO de 2026
-- La ventana no deja lugar a duda. La fila 4359 es del 11 de febrero y la
-- 4363 del 14, y entre ellas solo caben el 12 y el 13. El dato corrupto
-- dice '2026-11-13': el DÍA sobrevivió y lo que se estropeó fue el mes,
-- 02 leído como 11. Trece está dentro de la ventana; doce no explicaría
-- de dónde salió ese día.
update gastos_caja
   set fecha_gasto = '2026-02-13 00:00:00-05'
 where id_gasto in (4360, 4361, 4362);

-- Control: las tres deben quedar entre la 4359 y la 4363, en orden.
select id_gasto, to_char(fecha_gasto at time zone 'America/Bogota', 'YYYY-MM-DD') as dia,
       descripcion, monto
  from gastos_caja
 where id_gasto between 4358 and 4364
 order by id_gasto;


-- ---------------------------------------------------------------------
-- 3d. Dos abonos idénticos a COOAPA en la misma semana  [CONSULTA]
-- ---------------------------------------------------------------------
-- Al mirar la ventana aparece algo que no venía buscando: la fila 4351 es
-- 'ABONO A COOAPA' de $700.000 el 9 de febrero, y la 4361 es 'ABONO
-- COOAPA' de $700.000 el 13. Mismo importe redondo, mismo acreedor,
-- cuatro días de diferencia. Puede ser real -- dos cuotas seguidas -- o
-- puede ser la misma fila cargada dos veces por la migración.
--
-- NO lo corrijo: $700.000 borrados por equivocación son $700.000. Esta
-- consulta saca todos los abonos a COOAPA para que veas el ritmo normal;
-- si siempre hay uno al mes, dos en la misma semana sobran.
-- CORRECCIÓN: la primera versión de esta consulta buscaba 'coapa', con
-- una sola O, y la cooperativa es COOAPA, con dos. Devolvió cero filas y
-- eso parecía una respuesta -- «no hay duplicados» -- cuando en realidad
-- era el patrón que estaba mal. Una consulta vacía no es un dato hasta
-- que se comprueba que la consulta era correcta.
-- Ahora el patrón tolera las variantes: co+apa acepta COAPA, COOAPA y
-- cualquier número de oes, por si alguna fila se escribió con un dedazo.
select id_gasto,
       to_char(fecha_gasto at time zone 'America/Bogota', 'YYYY-MM-DD') as dia,
       descripcion, monto, metodo_pago
  from gastos_caja
 where descripcion ~* 'c[o]+apa'
 order by fecha_gasto;


-- ---------------------------------------------------------------------
-- 4. Un pago registrado dos veces  [REVISAR ANTES]
-- ---------------------------------------------------------------------
-- 'PAGO NOMINA ROSA' de $40.000 aparece dos veces el 24/08 con UN SEGUNDO
-- de diferencia (id 4789 y 4790). Un segundo no es tiempo suficiente para
-- escribir el mismo gasto dos veces: es un doble clic en Guardar.
select id_gasto, fecha_gasto, descripcion, monto, metodo_pago
  from gastos_caja
 where id_gasto in (4789, 4790);

-- CONFIRMADO por el negocio: fue un solo pago. Se borra el segundo.
delete from gastos_caja where id_gasto = 4790;


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


-- ---------------------------------------------------------------------
-- 6. El abono a COOAPA de $1.270
-- ---------------------------------------------------------------------
-- El negocio lo da por un $1.270.000 al que se le perdieron los ceros.
-- Encaja: el resto de sus abonos a COOAPA va de $100.000 a $2.400.000, y
-- mil doscientos setenta pesos no es un abono a un crédito.
--
-- OJO CON EL PORQUÉ, porque cambia lo que se puede hacer después. Esto NO
-- es el fallo de parseo que se limpió en la fase 3. Aquel INFLABA importes
-- (se comía el separador decimal y "5.500,00" entraba como 550000); este
-- los deja CORTOS, así que es otra cosa -- un dedazo al teclear o una
-- celda truncada en la migración. Y eso importa: el fallo de parseo se
-- podía cazar con un patrón porque siempre multiplicaba por la misma
-- potencia de diez. Un dedazo no deja huella. Si hay más como este, no
-- hay consulta que los encuentre a todos.
update gastos_caja
   set monto = 1270000
 where id_gasto = 3918
   and monto = 1270;

-- Control.
select id_gasto,
       to_char(fecha_gasto at time zone 'America/Bogota', 'YYYY-MM-DD') as dia,
       descripcion, monto
  from gastos_caja
 where id_gasto = 3918;

-- Los dos pagos de $400.000 del 3 de diciembre se quedan como están: el
-- negocio no puede confirmar que sobre uno, y ante la duda no se borra.


-- ---------------------------------------------------------------------
-- 7. Buscar otros importes que se hayan quedado cortos  [CONSULTA]
-- ---------------------------------------------------------------------
-- El espejo de la búsqueda del bloque 5b de la fase 3, que cazaba los
-- importes demasiado GRANDES para su categoría. Este busca los demasiado
-- PEQUEÑOS: un arriendo de $2.000, una nómina de $400, un laboratorio de
-- $150. No prueba que estén mal -- puede haber un ajuste pequeño de
-- verdad -- pero es donde estarían si les faltan ceros.
with normal as (
    select categoria_gasto,
           percentile_cont(0.5) within group (order by monto) as mediana
      from gastos_caja
     where monto > 0
     group by categoria_gasto
)
select g.id_gasto,
       to_char(g.fecha_gasto at time zone 'America/Bogota', 'YYYY-MM-DD') as dia,
       g.descripcion, g.monto, g.categoria_gasto, n.mediana,
       round((n.mediana / nullif(g.monto, 0))::numeric, 0) as veces_por_debajo
  from gastos_caja g
  join normal n using (categoria_gasto)
 where n.mediana > 0
   and g.monto > 0
   and g.monto < n.mediana / 20
   -- Las categorías de gasto menudo quedan fuera: ahí un importe de tres
   -- cifras es lo normal y saldrían decenas de filas correctas tapando
   -- las pocas que importan.
   and g.categoria_gasto not in ('ALIMENTACION', 'TRANSPORTE', 'ASEO E INSUMOS')
 order by veces_por_debajo desc
 limit 40;
