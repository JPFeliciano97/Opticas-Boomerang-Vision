-- =====================================================================
-- FASE 3 -- Montos inflados por el fallo de parseo
-- =====================================================================
-- Ejecutar en el editor SQL de Supabase, por bloques y en orden.
--
-- Contexto: la versión vieja de la app leía "5.500,000" como 5500000 en
-- lugar de 5500. El parseo ya está corregido en el código (parse_money_co),
-- así que esto NO puede volver a pasar; lo que queda son los registros
-- que entraron antes. Inflan cualquier promedio, comparación o gráfico
-- que mire gasto por categoría.
--
-- NO uses un UPDATE genérico del tipo "todo lo que supere X, entre 1000".
-- Un gasto de $8.000.000 puede ser perfectamente real (un pago de
-- laboratorio, la nómina de una quincena). La lista del bloque 2 salió de
-- revisar la descripción de cada fila una por una.


-- ---------------------------------------------------------------------
-- 1. Antes de tocar nada: fotografía de lo que se va a cambiar
-- ---------------------------------------------------------------------
-- Guarda este resultado (Download CSV en el editor). Es tu punto de
-- retorno si algo sale mal, aparte del UPDATE de reversión del bloque 4.
select id_gasto, fecha_gasto, descripcion, monto, categoria_gasto,
       monto / 1000 as monto_corregido
  from gastos_caja
 where id_gasto in (753,702,1060,927,766,662,918,754,757,781,656,747,1067,
                    442,670,695,793,799,1102,782,920,973,763,758,978)
 order by monto desc;


-- ---------------------------------------------------------------------
-- 2. La corrección
-- ---------------------------------------------------------------------
-- 25 filas, todas entre 2019 y 2022, todas consumibles menores: bolsas,
-- guantes, agua, gaseosa, un bus, un bombillo de nevera, una despinchada.
-- Ninguna puede costar millones, y las 25 dividen exacto entre 1000 --
-- que es justo la huella del fallo: el separador de miles se leyó como
-- decimal. Sumadas valen $127.980.000 cuando en realidad son $127.980.
--
-- El filtro repite la condición 'monto > 2000000' a propósito: si por lo
-- que sea el bloque ya se corrió, la segunda vez no encuentra nada y no
-- vuelve a dividir. Sin eso, ejecutarlo dos veces deja los montos en
-- una milésima de lo que valen.
update gastos_caja
   set monto = monto / 1000
 where id_gasto in (753,702,1060,927,766,662,918,754,757,781,656,747,1067,
                    442,670,695,793,799,1102,782,920,973,763,758,978)
   and monto > 2000000;


-- ---------------------------------------------------------------------
-- 3. Comprobación
-- ---------------------------------------------------------------------
-- Deben salir 25 filas con importes de tres o cuatro cifras: el bus a
-- $2.400, el sándwich a $5.500, la despinchada a $6.000.
select id_gasto, fecha_gasto, descripcion, monto, categoria_gasto
  from gastos_caja
 where id_gasto in (753,702,1060,927,766,662,918,754,757,781,656,747,1067,
                    442,670,695,793,799,1102,782,920,973,763,758,978)
 order by monto desc;

-- Y esta debe devolver CERO filas.
select count(*) as deben_ser_cero
  from gastos_caja
 where monto > 2000000
   and categoria_gasto in ('ALIMENTACION','ASEO E INSUMOS','TRANSPORTE');


-- ---------------------------------------------------------------------
-- 4. Reversión, por si acaso
-- ---------------------------------------------------------------------
-- Solo si algo salió mal. Deshace exactamente el bloque 2.
-- update gastos_caja
--    set monto = monto * 1000
--  where id_gasto in (753,702,1060,927,766,662,918,754,757,781,656,747,1067,
--                     442,670,695,793,799,1102,782,920,973,763,758,978);


-- ---------------------------------------------------------------------
-- 5. Lo que falta por revisar  [NO ES UNA CORRECCIÓN, ES UNA BÚSQUEDA]
-- ---------------------------------------------------------------------
-- El bloque 2 limpia el caso fácil: inflado x1000 y por encima de dos
-- millones. Quedan dos zonas sin barrer, y las dos necesitan tu ojo.
--
-- 5a. El inflado x100. El mismo fallo, con otra forma del importe:
--     "5.500,00" se leía como 550000 en vez de 5500. Eso deja gastos
--     menores en la banda de las centenas de miles, donde ya no chillan.
--     Un almuerzo de $550.000 es absurdo; una compra de insumos de
--     $550.000 podría ser real. Mira la descripción de cada uno.
select id_gasto, fecha_gasto, descripcion, monto, categoria_gasto
  from gastos_caja
 where monto between 100000 and 2000000
   and categoria_gasto in ('ALIMENTACION','ASEO E INSUMOS','TRANSPORTE')
 order by monto desc;

-- 5b. Las demás categorías. Aquí los importes altos suelen ser legítimos,
--     así que en vez de una lista plana conviene comparar cada gasto con
--     lo normal de SU categoría: lo que se sale es lo que hay que mirar.
with normal as (
    select categoria_gasto,
           percentile_cont(0.5) within group (order by monto) as mediana
      from gastos_caja
     where monto > 0
     group by categoria_gasto
)
select g.id_gasto, g.fecha_gasto, g.descripcion, g.monto,
       g.categoria_gasto, n.mediana,
       round((g.monto / nullif(n.mediana, 0))::numeric, 1) as veces_la_mediana
  from gastos_caja g
  join normal n using (categoria_gasto)
 where n.mediana > 0
   and g.monto > n.mediana * 20
 order by veces_la_mediana desc
 limit 60;
