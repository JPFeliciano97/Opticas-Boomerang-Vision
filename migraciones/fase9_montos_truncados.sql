-- =====================================================================
-- FASE 9 -- Importes que se quedaron cortos
-- =====================================================================
-- El espejo de la fase 3. Allí se corrigieron 37 filas multiplicadas por
-- mil; aquí van cuatro que llegaron DIVIDIDAS por mil -- venían anotadas
-- en miles de pesos y se importaron tal cual.
--
-- Salieron del bloque 7 de la fase 5, que busca importes demasiado
-- pequeños para su categoría. La pista definitiva son los decimales:
-- 15,6 y 136,1. No existe un gasto de quince pesos con sesenta centavos.
--
-- DE DÓNDE SALEN LAS CIFRAS, dicho con precisión: las dos grandes las
-- confirmó el dueño de memoria, con sus palabras -- "es posible que haya
-- sido 1107000" y "creería que es 1664000". No hay factura a la vista.
-- Las dos pequeñas nadie las confirmó una por una: se corrigen porque
-- comparten el mismo patrón de las otras dos, y porque su valor actual
-- es imposible. Si algún día aparece un soporte y no cuadra, que se sepa
-- que esto fue reconstrucción y no lectura de un documento.


-- ---------------------------------------------------------------------
-- 1. Cómo están ahora  [CONSULTA]
-- ---------------------------------------------------------------------
select id_gasto,
       to_char(fecha_gasto at time zone 'America/Bogota', 'YYYY-MM-DD') as dia,
       descripcion, monto, categoria_gasto
  from gastos_caja
 where id_gasto in (709, 2629, 3826, 1767)
 order by id_gasto;


-- ---------------------------------------------------------------------
-- 2. La corrección
-- ---------------------------------------------------------------------
-- Cada UPDATE lleva el monto actual en el WHERE. Si alguien ya corrigió
-- una fila, ese UPDATE no toca nada en vez de multiplicarla otra vez --
-- correr este archivo dos veces no hace daño.
update gastos_caja set monto = 15600
 where id_gasto = 709  and monto = 15.6;      -- precision lab

update gastos_caja set monto = 136100
 where id_gasto = 2629 and monto = 136.1;     -- ZEISS SE DEBE

update gastos_caja set monto = 1107000
 where id_gasto = 3826 and monto = 1107;      -- MONTURAS MAFE COMPANY

update gastos_caja set monto = 1664000
 where id_gasto = 1767 and monto = 1664;      -- SALDO ARRIENDO ENERO 2023


-- ---------------------------------------------------------------------
-- 3. Comprobación  [CONSULTA]
-- ---------------------------------------------------------------------
-- Esperado: 15.600 · 136.100 · 1.107.000 · 1.664.000
select id_gasto,
       to_char(fecha_gasto at time zone 'America/Bogota', 'YYYY-MM-DD') as dia,
       descripcion, monto, categoria_gasto
  from gastos_caja
 where id_gasto in (709, 2629, 3826, 1767)
 order by id_gasto;


-- ---------------------------------------------------------------------
-- 4. Lo que NO se toca, y por qué
-- ---------------------------------------------------------------------
-- Seis filas de exactamente $2.000 en LABORATORIO Y PROVEEDORES
-- (BISEL, BISEL GIRBRO, BISEL OMAR, AUSTRALENS, ESTUCHE DURO,
-- ONLY VISION SALDO EFECT.) salieron en la misma búsqueda. El dueño
-- confirmó que un bisel costaba de dos a cuatro mil pesos: son gastos
-- correctos, marcados por pequeños y no por estar mal. Es justo la razón
-- por la que esa consulta avisa y no corrige sola.
--
-- Quedan dos cosas SIN RESOLVER, anotadas para no perderlas:
--
--   a) Quince filas de exactamente $2.000 descritas "doc" / "DOC" /
--      "doctor", entre 2018 y 2020, clasificadas como HONORARIOS POR
--      CONSULTA. Dos mil pesos por una consulta no tiene sentido (la
--      mediana es 50.000). Sospecha: "doc" no es doctor sino DOCUMENTO
--      -- fotocopias o impresiones, que en 2018 sí costaban eso. De ser
--      así estarían mal clasificadas por el regex que buscaba
--      "doc|doctor|dra|consulta", no mal valoradas.
--
--   b) La fila 1986 (2023-05-18) descrita "TRASPASO", $2.000, en
--      LABORATORIO Y PROVEEDORES. Por el nombre parece un movimiento
--      entre cuentas, no un gasto: candidata a NO ES UN GASTO.
--
-- Las dos necesitan que alguien recuerde qué eran. Corregirlas a ojo
-- sería inventar.


-- ---------------------------------------------------------------------
-- 5. Marcha atrás
-- ---------------------------------------------------------------------
-- update gastos_caja set monto = 15.6   where id_gasto = 709  and monto = 15600;
-- update gastos_caja set monto = 136.1  where id_gasto = 2629 and monto = 136100;
-- update gastos_caja set monto = 1107   where id_gasto = 3826 and monto = 1107000;
-- update gastos_caja set monto = 1664   where id_gasto = 1767 and monto = 1664000;
