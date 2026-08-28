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


-- =====================================================================
-- TERCERA RONDA -- la ventana 735-800 refuta la hipótesis del lote
-- =====================================================================
-- La consulta del bloque 7 se hizo para probar una idea: que los importes
-- corrompidos venían en lotes, y que por tanto 741, 749 y 783 -- metidos
-- dentro de rachas podridas -- también lo estaban.
--
-- No es así. En esas 66 filas conviven importes normales con importes
-- corrompidos, fila a fila: 746 INKOPTICAL $195.000 justo antes de 747
-- FABULOSO corrompido; 782 VASOS corrompido justo antes de 783 NEXT
-- VISION. El fallo dependía de si ESA fila se escribió con decimales, no
-- del lote. La cercanía de id no prueba nada y la descarto.
--
-- Así que 741, 749, 783, 896, 412, 102 y 274 se quedan como están. No
-- tengo evidencia de que estén mal, y dividir entre 1000 un pago real de
-- laboratorio sería un daño peor que dejarlo.
--
-- Lo que la ventana SÍ confirmó es el bloque 6, y por un camino que no
-- había buscado: existen hermanas sanas de las filas que corregí.
--   785  'PRESTAMO ROSA'      $20.000   <- sana
--   827  'PRESTAMO ROSA'      $10.000   <- corregida por mí
--   789  'Pago Rosa (380-20)' $20.000   <- sana, misma anotación (NNN-NN)
--   795  'ROSA (345-10)'      $10.000   <- corregida por mí
--   798  'ROSA 335-50'        $50.000   <- sana
-- Mismo concepto, misma notación, mismo orden de magnitud. La corrección
-- dio en el sitio.


-- ---------------------------------------------------------------------
-- 9. La prueba que sí puede zanjar los siete  [CONSULTA]
-- ---------------------------------------------------------------------
-- El método de pago lo decide. Esta caja movía cientos de miles de pesos
-- al día: un pago de OCHO MILLONES en efectivo es imposible, la plata no
-- estaba ahí. Por transferencia o consignación, en cambio, es
-- perfectamente normal.
select id_gasto, fecha_gasto, descripcion, monto, metodo_pago, categoria_gasto
  from gastos_caja
 where id_gasto in (783, 896, 749, 741, 412, 102, 274)
 order by fecha_gasto;

-- Y el contexto del día: cuánto se gastó en total esas fechas. Si el día
-- del supuesto pago de ocho millones el resto de la caja se movió en
-- decenas de miles, el importe no cabe.
select date(fecha_gasto) as dia,
       count(*) as movimientos,
       sum(monto) as total_dia,
       max(monto) as mayor_del_dia
  from gastos_caja
 where date(fecha_gasto) in (date '2021-11-04', date '2021-09-18',
                             date '2021-09-24', date '2022-02-10',
                             date '2019-06-08', date '2018-02-28',
                             date '2018-11-22')
 group by 1
 order by 1;


-- ---------------------------------------------------------------------
-- 10. Cuarta pasada de clasificación  [hallazgo de la ventana]
-- ---------------------------------------------------------------------
-- Revisar 66 filas seguidas destapó algo que las pasadas anteriores no
-- podían ver: el clasificador reconoce proveedores por su NOMBRE, pero no
-- reconoce los PRODUCTOS. Siete filas de esta sola ventana quedaron en
-- SIN CLASIFICAR siendo todas material óptico: MULTISOLUTER, FRESHLOOK,
-- CY SOLUTION clear lens, POLY AR, LENS NEX, poly blue y cr ar,
-- poly color. Son lentes y soluciones de limpieza: laboratorio.
--
-- Si en 66 filas hay siete, en el histórico completo hay muchas más. El
-- orden importa: cada UPDATE solo toca lo que sigue SIN CLASIFICAR.
--
-- ANTES DE LOS UPDATE: esta consulta te muestra exactamente qué filas se
-- van a mover y a dónde, sin tocar nada. Descárgala en CSV. Es tu única
-- forma de deshacerlo, porque una vez reclasificadas ya no se distinguen
-- de las que otras pasadas clasificaron bien.
select id_gasto, fecha_gasto, descripcion, monto,
       case
         when descripcion ~* '(poly|solution|multisolut|freshlook|acuvue|biofinity|'
                             'clear lens|lens nex|\ylens\y|antirreflejo|\yar\y|'
                             'transition|fotocrom|cr39|cr 39|blue|progresiv|'
                             'bifocal|monofocal|tallado|biselado|\ybisel)'
              then 'LABORATORIO Y PROVEEDORES'
         when descripcion ~* '(tapete|escoba|trapeador|recogedor|caneca|resma|'
                             'toalla|servilleta|detergente|blanqueador|clorox)'
              then 'ASEO E INSUMOS'
         when descripcion ~* '(pickup|pick up|picup|\ydidi\y|uber|indriver|taxi|'
                             'gasolina|peaje|parqueadero)'
              then 'TRANSPORTE'
         when descripcion ~* '(interes|intereses|cuota credito|cuota banco)'
              then 'OBLIGACIONES FINANCIERAS'
       end as categoria_propuesta
  from gastos_caja
 where coalesce(categoria_gasto, 'SIN CLASIFICAR') = 'SIN CLASIFICAR'
 order by 5, descripcion;
-- Revísala. Si alguna fila está mal asignada, dímelo y ajusto el patrón
-- ANTES de que corras los UPDATE.

update gastos_caja
   set categoria_gasto = 'LABORATORIO Y PROVEEDORES'
 where coalesce(categoria_gasto, 'SIN CLASIFICAR') = 'SIN CLASIFICAR'
   and descripcion ~* '(poly|solution|multisolut|freshlook|acuvue|biofinity|'
                      'clear lens|lens nex|\ylens\y|antirreflejo|\yar\y|'
                      'transition|fotocrom|cr39|cr 39|blue|progresiv|'
                      'bifocal|monofocal|tallado|biselado|\ybisel)';

-- Insumos de aseo que tampoco estaban en el diccionario.
update gastos_caja
   set categoria_gasto = 'ASEO E INSUMOS'
 where coalesce(categoria_gasto, 'SIN CLASIFICAR') = 'SIN CLASIFICAR'
   and descripcion ~* '(tapete|escoba|trapeador|recogedor|caneca|resma|'
                      'toalla|servilleta|detergente|blanqueador|clorox)';

-- Transporte: 'PICKUP' es la app Picap, igual que 'PICUK' y 'picap'.
update gastos_caja
   set categoria_gasto = 'TRANSPORTE'
 where coalesce(categoria_gasto, 'SIN CLASIFICAR') = 'SIN CLASIFICAR'
   and descripcion ~* '(pickup|pick up|picup|\ydidi\y|uber|indriver|taxi|'
                      'gasolina|peaje|parqueadero)';

-- Los intereses del tío Julio ya tienen categoría en otras filas; esta se
-- quedó fuera solo porque la descripción no lo nombra.
update gastos_caja
   set categoria_gasto = 'OBLIGACIONES FINANCIERAS'
 where coalesce(categoria_gasto, 'SIN CLASIFICAR') = 'SIN CLASIFICAR'
   and descripcion ~* '(interes|intereses|cuota credito|cuota banco)';

-- Cuánto quedó sin clasificar después de esta pasada.
select coalesce(categoria_gasto, 'SIN CLASIFICAR') as categoria,
       count(*) as filas,
       round(100.0 * count(*) / sum(count(*)) over (), 1) as pct
  from gastos_caja
 group by 1
 order by filas desc;


-- ---------------------------------------------------------------------
-- 11. Estado actual  [SOLO CONSULTA, no cambia nada]
-- ---------------------------------------------------------------------
-- Una sola consulta que dice qué bloques quedaron aplicados. Útil cuando
-- se han corrido varios archivos en varias sesiones y ya no se recuerda
-- dónde se quedó uno.
select 'bloques 2 y 6 -- montos inflados' as comprobacion,
       count(*) filter (where monto > 900000)::text || ' de 37 sin corregir'
         as resultado
  from gastos_caja
 where id_gasto in (753,702,1060,927,766,662,918,754,757,781,656,747,1067,
                    442,670,695,793,799,1102,782,920,973,763,758,978,
                    780,726,143,777,1057,1079,768,791,795,827,792,784)
union all
select 'bloque 8b -- categorias corregidas',
       'id 768 = ' || coalesce(max(categoria_gasto) filter (where id_gasto = 768), 'null')
       || ' · id 1221 = ' || coalesce(max(categoria_gasto) filter (where id_gasto = 1221), 'null')
  from gastos_caja
 where id_gasto in (768, 1221)
union all
select 'bloque 10 -- cuarta pasada',
       count(*)::text || ' filas de material optico siguen SIN CLASIFICAR'
  from gastos_caja
 where coalesce(categoria_gasto, 'SIN CLASIFICAR') = 'SIN CLASIFICAR'
   and descripcion ~* '(poly|solution|multisolut|freshlook|lens)'
union all
select 'sin clasificar en total',
       count(*) filter (where coalesce(categoria_gasto,'SIN CLASIFICAR') = 'SIN CLASIFICAR')::text
       || ' de ' || count(*)::text || ' filas ('
       || round(100.0 * count(*) filter (where coalesce(categoria_gasto,'SIN CLASIFICAR') = 'SIN CLASIFICAR')
                / nullif(count(*), 0), 1)::text || '%)'
  from gastos_caja;


-- ---------------------------------------------------------------------
-- 12. Decisiones del negocio
-- ---------------------------------------------------------------------
-- Cuatro filas que solo el dueño podía resolver.

-- 12a. 'PAGO JUAN PABLO' ($3.500.000) es sueldo, no un laboratorio.
--      Va con 'PAGO SALARIO JUAN' ($3.928.000), que ya se movió antes.
update gastos_caja
   set categoria_gasto = 'NOMINA'
 where id_gasto = 1576;

-- 12b. 'saldo hoy' ($954.250) no es un gasto: es el saldo del día
--      anotado por error en la tabla equivocada. No se borra -- perder
--      la fila perdería el rastro de por qué las cuentas de ese día no
--      cuadran -- se marca, y la analítica la ignora.
--      Requiere el código nuevo: la app filtra 'NO ES UN GASTO' en el
--      origen del módulo de analítica.
update gastos_caja
   set categoria_gasto = 'NO ES UN GASTO'
 where id_gasto = 4223;

-- 12c. 'LUZ CASA' es el recibo de la vivienda, no del local. No es costo
--      de operar la óptica: es plata que sale para el dueño.
update gastos_caja
   set categoria_gasto = 'RETIROS DEL PROPIETARIO'
 where id_gasto = 797;

-- 12d. 'TV' ($400.000) se queda SIN CLASIFICAR a propósito. No se
--      recuerda si el televisor fue para el local o para la casa, y
--      adivinar lo mandaría o a inflar el gasto operativo o a inflar los
--      retiros. Sin clasificar es la respuesta honesta.

-- 12e. Si 'LUZ CASA' se coló, es probable que haya más recibos de la
--      vivienda mezclados con los del local. Esta consulta los busca;
--      NO corrige nada, porque distinguir "casa" de "local" necesita tu
--      criterio y no un patrón de texto.
select id_gasto, fecha_gasto, descripcion, monto, categoria_gasto
  from gastos_caja
 where descripcion ~* '(casa|hogar|apto|apartamento|vivienda)'
   and coalesce(categoria_gasto, 'SIN CLASIFICAR')
       not in ('RETIROS DEL PROPIETARIO', 'LABORATORIO Y PROVEEDORES')
 order by fecha_gasto desc;
-- Ojo: 'CASA OPTICA' es un laboratorio, no una casa. Por eso la consulta
-- excluye ya LABORATORIO Y PROVEEDORES -- si no, saldrían decenas de
-- filas suyas y taparían lo que sí importa.


-- ---------------------------------------------------------------------
-- 13. Por qué siguen 626 filas sin clasificar  [SOLO CONSULTAS]
-- ---------------------------------------------------------------------
-- Después de la tercera pasada el sin clasificar estaba en 6,3%. El
-- bloque 11 lo mide ahora en 13,1% (626 de 4793). Dos mediciones que no
-- pueden ser ambas ciertas sobre el mismo dato.
--
-- La sospecha: NULL y 'SIN CLASIFICAR' no son lo mismo. Todas las pasadas
-- filtran por  categoria_gasto = 'SIN CLASIFICAR'  a secas, así que una
-- fila con NULL nunca las cumple y ninguna pasada la ha tocado jamás.
-- La medición del 6,3% probablemente tampoco las contaba. El bloque 11 sí
-- las cuenta, porque usa coalesce. Si es eso, no es que la clasificación
-- haya empeorado: es que ahora se está mirando entero.

-- 13a. Separar los dos casos. Si 'nulos' es un número grande, ahí está.
select count(*) filter (where categoria_gasto is null)             as nulos,
       count(*) filter (where categoria_gasto = 'SIN CLASIFICAR')  as sin_clasificar,
       count(*) filter (where categoria_gasto = '')                as cadena_vacia,
       count(*)                                                    as total
  from gastos_caja;

-- 13b. Las nueve de material óptico que la cuarta pasada no alcanzó.
--      Corrió, pero estas se le escaparon: quiero ver por qué.
select id_gasto, fecha_gasto, descripcion, monto, categoria_gasto
  from gastos_caja
 where coalesce(categoria_gasto, 'SIN CLASIFICAR') = 'SIN CLASIFICAR'
   and descripcion ~* '(poly|solution|multisolut|freshlook|lens)'
 order by descripcion;

-- 13c. Lo que de verdad importa de las 626: no son 626 conceptos
--      distintos, son unos pocos repetidos muchas veces. Esta consulta
--      los ordena por PLATA, no por número de filas -- clasificar
--      cincuenta gastos de $2.000 mueve la aguja mucho menos que
--      clasificar cinco de $400.000.
select lower(trim(descripcion))     as concepto,
       count(*)                     as veces,
       sum(monto)                   as total,
       min(date(fecha_gasto))       as desde,
       max(date(fecha_gasto))       as hasta
  from gastos_caja
 where coalesce(categoria_gasto, 'SIN CLASIFICAR') = 'SIN CLASIFICAR'
 group by 1
 order by total desc
 limit 60;

-- 13d. Y cuánta plata hay ahí en total, para saber si vale la pena.
select count(*)                             as filas,
       sum(monto)                           as plata_sin_clasificar,
       round(100.0 * sum(monto) /
             (select sum(monto) from gastos_caja), 1) as pct_del_gasto
  from gastos_caja
 where coalesce(categoria_gasto, 'SIN CLASIFICAR') = 'SIN CLASIFICAR';
