-- =====================================================================
-- FASE 11 -- Códigos únicos y ficha de montura
-- =====================================================================
-- Sale de revisar el inventario real: 38 monturas, todas cargadas el 11
-- y el 12 de septiembre de 2026. En esas 38 filas aparecieron cuatro
-- cosas que esta migración arregla.
--
--   1. 'H1905' está DOS veces, y son dos monturas distintas (una azul y
--      una negra brillante). Al facturar, la búsqueda se queda con la
--      primera: una de las dos no se puede vender ni descontar nunca.
--
--   2. Los códigos nunca se recortan al guardarlos, así que 'H1905 ' con
--      un espacio al final pasa por otro código y en pantalla se ve
--      idéntico. Es la explicación más probable del punto 1.
--
--   3. Cuatro erratas de nombre sobre 38 filas: MF APLQIUE, MF BLUE
--      LIGTH, MF COMPAMY, y una montura con material PLASTICA (que no
--      existe en el desplegable; PLASTICO sí).
--
--   4. El modelo, el color y la talla ya se están usando como datos,
--      pero metidos dentro del código y de la descripción, cada vez de
--      una forma distinta: 'KNM28 LILA', '8818C2', '1909 C5',
--      'PC-008' frente a 'PC008', 'DZM110-55-18-140'.
--
-- EJECUTAR POR BLOQUES Y EN ORDEN. Los bloques 1 y 2 solo miran.
--
-- CORREGIDO DESPUÉS DE FALLAR AL EJECUTARSE. La primera versión decía
-- "recortar antes de deduplicar" y es al revés, por algo que no se había
-- comprobado: inventario.codigo YA tenía una restricción de unicidad,
-- 'inventario_codigo_key', desde antes de esta migración.
--
-- Encaja con el duplicado: para Postgres 'H1905 ' y 'H1905' son valores
-- distintos, así que la restricción funcionaba y el espacio se la
-- saltaba. Pero al recortar, 'H1905 ' choca con 'H1905', el UPDATE
-- entero se deshace, y con él también el recorte de los demás.
--
-- Por eso ahora se renombra el duplicado PRIMERO, buscándolo con btrim()
-- para encontrarlo lleve o no el espacio, y se recorta después.


-- ---------------------------------------------------------------------
-- 1. Códigos con espacios de sobra  [CONSULTA]
-- ---------------------------------------------------------------------
-- Los corchetes hacen visible el espacio. Si sale alguna fila, ese es el
-- mecanismo por el que entró el duplicado.
select codigo,
       length(codigo)          as largo,
       '[' || codigo || ']'    as con_corchetes,
       descripcion
  from inventario
 where codigo <> btrim(codigo)
 order by codigo;


-- ---------------------------------------------------------------------
-- 2. Qué códigos chocarían al recortar  [CONSULTA]
-- ---------------------------------------------------------------------
-- Esperado: solo H1905. Si sale alguno más, hay que decidir qué hacer
-- con él ANTES de seguir -- el bloque 4 solo sabe resolver el conocido.
select btrim(upper(codigo)) as codigo_limpio,
       count(*)             as veces,
       string_agg(descripcion, '  ||  ') as descripciones
  from inventario
 group by 1
having count(*) > 1
 order by 1;


-- ---------------------------------------------------------------------
-- 3. Resolver el duplicado H1905  -- ANTES de recortar
-- ---------------------------------------------------------------------
-- Se renombra la NEGRA BRILLANTE siguiendo la convención que ya usa el
-- negocio en KNM28 BLANCA y VNN134 CAFE: código base más el color. La
-- azul se queda con el código original porque entró primero.
--
-- El WHERE usa btrim() y no una comparación directa: la fila que hay que
-- renombrar es justamente la que lleva el espacio, así que buscarla por
-- 'H1905' a secas no la encontraría.
update inventario
   set codigo = 'H1905 NEGRA'
 where btrim(codigo) = 'H1905'
   and descripcion ilike '%NEGRA BRILLANTE%';


-- ---------------------------------------------------------------------
-- 4. Recortar los códigos, arrastrando las referencias
-- ---------------------------------------------------------------------
-- Las ventas y los movimientos apuntan al inventario por el texto del
-- código, no por una clave. Recortar solo el inventario dejaría esas
-- referencias huérfanas, así que se recortan las tres a la vez.
update inventario
   set codigo = btrim(upper(codigo))
 where codigo <> btrim(upper(codigo));

update ventas_facturacion
   set montura_codigo = btrim(upper(montura_codigo))
 where montura_codigo is not null
   and montura_codigo <> btrim(upper(montura_codigo));

update movimientos_inventario
   set codigo = btrim(upper(codigo))
 where codigo <> btrim(upper(codigo));

-- Los movimientos de saldo inicial de H1905 se rehacen: había dos filas
-- con el mismo código para dos monturas distintas, y ahora son dos
-- códigos. Se borran solo los del saldo inicial, que los puso la
-- migración anterior y no representan ningún movimiento real.
delete from movimientos_inventario
 where codigo in ('H1905', 'H1905 NEGRA')
   and motivo = 'Saldo inicial al empezar el historial';

insert into movimientos_inventario
       (codigo, fecha, delta, cantidad_resultante, motivo, registrado_por)
select i.codigo, now(), i.cantidad, i.cantidad,
       'Saldo inicial al empezar el historial', 'Migración'
  from inventario i
 where i.codigo in ('H1905', 'H1905 NEGRA')
   and coalesce(i.cantidad, 0) <> 0;


-- ---------------------------------------------------------------------
-- 5. Comprobar que ya no hay duplicados  [CONSULTA]
-- ---------------------------------------------------------------------
-- Tiene que dar CERO filas antes de pasar al bloque 6.
select codigo, count(*) as veces
  from inventario
 group by codigo
having count(*) > 1;


-- ---------------------------------------------------------------------
-- 6. La restricción de unicidad  [CONSULTA]
-- ---------------------------------------------------------------------
-- NO hay que añadir nada: 'inventario_codigo_key' ya existía. Lo que
-- fallaba no era la restricción sino los espacios, que la volvían inútil
-- -- 'H1905 ' y 'H1905' son valores distintos para Postgres.
--
-- Debe salir inventario_codigo_key UNIQUE (codigo). Si además aparece
-- 'inventario_codigo_unico', lo creó la primera versión de este archivo
-- y sobra:
--
--   alter table inventario drop constraint inventario_codigo_unico;
select conname, pg_get_constraintdef(oid) as definicion
  from pg_constraint
 where conrelid = 'inventario'::regclass
   and contype in ('u', 'p');


-- ---------------------------------------------------------------------
-- 7. Erratas de marca, proveedor y material
-- ---------------------------------------------------------------------
-- Cuatro sobre 38 filas. Son las mismas letras en distinto orden, así
-- que no hay duda de cuál es la buena.
update inventario set marca = 'MF APLIQUE'    where marca = 'MF APLQIUE';
update inventario set marca = 'MF BLUE LIGHT' where marca = 'MF BLUE LIGTH';
update inventario set proveedor = 'MF COMPANY' where proveedor = 'MF COMPAMY';

-- PLASTICA no existe en el desplegable de materiales; PLASTICO sí. Esa
-- descripción se escribió a mano, no salió de la lista.
update inventario
   set descripcion = replace(descripcion, 'MONTURA PLASTICA', 'MONTURA PLASTICO')
 where descripcion like 'MONTURA PLASTICA%';

-- 'MF MONTURAS' se deja como está: puede ser una errata de MF COMPANY o
-- un proveedor de verdad. No se toca lo que no se sabe.


-- ---------------------------------------------------------------------
-- 8. La ficha de la montura
-- ---------------------------------------------------------------------
-- Modelo, color, material y talla dejan de vivir dentro del código y de
-- la descripción. Nulas para lo que no es una montura.
alter table inventario
  add column if not exists modelo   text,
  add column if not exists color    text,
  add column if not exists material text,
  add column if not exists talla    text;


-- ---------------------------------------------------------------------
-- 9. Rellenar la ficha con lo que ya se sabe
-- ---------------------------------------------------------------------
-- El material y el color salen de la descripción, que tiene la forma
-- 'MONTURA <material> - COLOR <color>' en las 38 filas.
update inventario
   set material = btrim(substring(descripcion from 'MONTURA (.+?) - COLOR')),
       color    = btrim(substring(descripcion from ' - COLOR (.+)$'))
 where lower(coalesce(categoria, '')) = 'montura'
   and descripcion ~ 'MONTURA .+ - COLOR .+';

-- El modelo es la parte del código anterior al sufijo de color o talla.
-- Tres reglas, en este orden, probadas contra los 38 códigos reales:
--
--   1. Sufijo C y número, EXIGIENDO un dígito antes. Sin esa exigencia,
--      'PC008' se partiría en 'P' -- la C de PC entraría por el patrón.
--      Con ella: '8818C2' y '1909 C5' -> '8818' y '1909'.
--   2. Talla al final con guiones: 'DZM110-55-18-140' -> 'DZM110'.
--   3. Color al final: espacio más una palabra de tres letras o más.
--      'KNM28 LILA' -> 'KNM28'.
--
-- Lo que no encaje en esas tres se queda entero, que es lo prudente:
-- 'FN-08', 'PC-008' y '8822-1' son su propio modelo. Es mejor un modelo
-- de más que partir un código por la mitad.
update inventario
   set modelo = btrim(
         regexp_replace(
           regexp_replace(
             regexp_replace(codigo, '^(.*[0-9])\s*C[0-9]+$', '\1'),
             '-[0-9]+-[0-9]+-[0-9]+$', ''),
           '\s+[A-ZÁÉÍÓÚÑ]{3,}$', ''))
 where lower(coalesce(categoria, '')) = 'montura';
-- Sin 'and modelo is null': si el renombrado o el recorte se corrigieron
-- después, los códigos cambiaron y el modelo calculado antes quedó mal.
-- '82307 ROSADA ' con el espacio final no encajaba en la regla del color
-- y se quedó con el modelo '82307 ROSADA' en vez de '82307'.

-- La única talla que estaba metida en un código: 55-18-140.
update inventario
   set talla = '55-18-140'
 where codigo = 'DZM110-55-18-140';


-- ---------------------------------------------------------------------
-- 10. Comprobación  [CONSULTA]
-- ---------------------------------------------------------------------
-- Revisa que el modelo y el color quedaran bien repartidos. Lo que
-- salga raro se corrige a mano desde Editar Producto.
select codigo, marca, modelo, color, material, coalesce(talla, '—') as talla
  from inventario
 where lower(coalesce(categoria, '')) = 'montura'
 order by marca, modelo, codigo;


-- ---------------------------------------------------------------------
-- 11. El precio invertido de KNM28 LILA  [REVISAR ANTES DE CORRER]
-- ---------------------------------------------------------------------
-- Esta montura está a compra $250.000 y venta $130.000: cada venta
-- perdería $120.000. Sus dos hermanas del mismo modelo, KNM28 y KNM28
-- BLANCA, cuestan $25.000. Todo apunta a un cero de más.
--
-- NO va descomentado a propósito: es una suposición sobre un precio, no
-- un dato leído de una factura. Confírmalo con la factura de MF COMPANY
-- y entonces córrelo.
--
-- update inventario set precio_compra = 25000 where codigo = 'KNM28 LILA';


-- ---------------------------------------------------------------------
-- 12. Marcha atrás
-- ---------------------------------------------------------------------
-- alter table inventario drop constraint if exists inventario_codigo_unico;
-- alter table inventario
--   drop column if exists modelo,
--   drop column if exists color,
--   drop column if exists material,
--   drop column if exists talla;
-- update inventario set codigo = 'H1905' where codigo = 'H1905 NEGRA';
