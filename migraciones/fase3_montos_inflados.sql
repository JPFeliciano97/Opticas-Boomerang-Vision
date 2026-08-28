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


-- =====================================================================
-- SEGUNDA RONDA -- resultados de los bloques 5a y 5b
-- =====================================================================
-- El fallo era 'clean_numeric_string': se quedaba solo con los dígitos y
-- tiraba el separador decimal. Así que el factor de inflado es 10 elevado
-- al número de decimales que se escribieron: "5.500,00" daba 550000
-- (x100) y "5.500,000" daba 5500000 (x1000). El importe solo se corrompía
-- si se escribió con decimales; "5.500" a secas entraba bien.
--
-- Las 25 filas de la primera ronda son x1000, y no por suposición: al
-- dividirlas quedan entre $2.400 y $10.000, y ahí dentro el bus da $2.400
-- (el pasaje de TransMilenio en 2022 era $2.500) y el agua en botella
-- $2.500. Con x100 el bus costaría $24.000. Es un bloque coherente.


-- ---------------------------------------------------------------------
-- 6. Segunda tanda de montos inflados
-- ---------------------------------------------------------------------
-- Doce filas más. Las ocho primeras son inequívocas por la descripción:
-- unos guantes, un jabón Rey, unas bolsas blancas, un rollo de fotos,
-- unos tornillos, unas onces con pan, unos buses. Al dividir entre 1000
-- caen entre $1.000 y $8.900, justo por debajo del bloque anterior:
-- es la misma caja menor.
--
-- Las cuatro de ROSA piden un párrafo aparte. Rosa es nómina y la mediana
-- de la categoría son $25.000, o sea pagos diarios. Un préstamo de diez
-- millones a una empleada no cabe en este negocio; divididos dan $10.000
-- y $5.000, que sí encajan con el resto de sus pagos. Además caen en la
-- misma ventana de id (777-795, noviembre y diciembre de 2021) donde
-- prácticamente todas las filas están corrompidas.
update gastos_caja
   set monto = monto / 1000
 where id_gasto in (780,726,143,777,1057,1079,768,791,   -- inequívocos
                    795,827,792,784)                     -- pagos a Rosa
   and monto > 900000;

-- Control: doce filas, todas de cuatro cifras o menos.
select id_gasto, fecha_gasto, descripcion, monto, categoria_gasto
  from gastos_caja
 where id_gasto in (780,726,143,777,1057,1079,768,791,795,827,792,784)
 order by monto desc;

-- Reversión del bloque 6, por si acaso:
-- update gastos_caja set monto = monto * 1000
--  where id_gasto in (780,726,143,777,1057,1079,768,791,795,827,792,784);


-- ---------------------------------------------------------------------
-- 7. Los siete que NO toco  [PENDIENTE DE DECIDIR]
-- ---------------------------------------------------------------------
-- Estos podrían ser inflados o podrían ser reales, y la diferencia
-- importa: dividir entre 1000 un pago real de laboratorio de ocho
-- millones sería destrozarlo.
--
--   783   NEXT VISION      $8.000.000   2021-11-04
--   896   NEXT VISION      $7.500.000   2022-02-10
--   749   PRECISION LAB    $5.200.000   2021-09-24
--   741   PRECISION LAB    $5.200.000   2021-09-18
--   412   doc              $9.600.000   2019-06-08
--   102   doc              $5.000.000   2018-02-28
--   274   ETB              $2.500.000   2018-11-22
--
-- A favor de que 783 y 749 sí estén inflados: caen dentro de rachas de
-- id donde casi todo lo demás está corrompido (777-795 y 747-758). Eso
-- sugiere que se cargaron en el mismo lote y con el mismo formato.
-- En contra: los pagos a ZAFIRO de 2024-2026, que entraron con el parseo
-- ya sano, van de $1.100.000 a $4.668.000. Un laboratorio de varios
-- millones es perfectamente posible en este negocio.
--
-- Esta consulta lo resuelve: saca TODAS las filas de esas rachas, no solo
-- las sospechosas. Si dentro de la ventana no hay ni una sola fila con un
-- importe normal, el lote entero venía con decimales y 783/749 están
-- inflados. Si conviven importes normales, entonces el fallo era fila a
-- fila y hay que juzgar cada una por su descripción.
select id_gasto, fecha_gasto, descripcion, monto, categoria_gasto
  from gastos_caja
 where id_gasto between 735 and 800
 order by id_gasto;


-- ---------------------------------------------------------------------
-- 8. Lo que apareció de paso y no es un problema de monto
-- ---------------------------------------------------------------------
-- 8a. Una fila que no es un gasto. "saldo hoy", $954.250, 2025-12-14:
--     parece el saldo del día registrado como si fuera un gasto. Si es
--     eso, hay que borrarla, no corregirla -- pero decídelo tú primero.
select id_gasto, fecha_gasto, descripcion, monto, metodo_pago, categoria_gasto
  from gastos_caja
 where id_gasto = 4223;

-- 8b. Categorías que no corresponden a la descripción. Los importes están
--     bien; lo que está mal es dónde suman.
--       768   'onces Dra y pan'    está en HONORARIOS POR CONSULTA
--                                  y es ALIMENTACION
--       1221  'PAGO SALARIO JUAN'  está en LABORATORIO Y PROVEEDORES
--                                  y es NOMINA
--       1576  'PAGO JUAN PABLO'    está en LABORATORIO Y PROVEEDORES
--                                  y probablemente es NOMINA o un retiro
update gastos_caja set categoria_gasto = 'ALIMENTACION' where id_gasto = 768;
update gastos_caja set categoria_gasto = 'NOMINA'       where id_gasto = 1221;
-- 1576 queda sin tocar hasta que confirmes qué es 'PAGO JUAN PABLO'.
