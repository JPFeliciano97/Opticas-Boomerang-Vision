-- =====================================================================
-- FASE 13 -- Las fechas de nacimiento que no son fechas de nacimiento
-- =====================================================================
-- El formulario de Admisión traía 01/01/1995 puesto por defecto en la
-- fecha de nacimiento. Y al cargar un paciente que ya existía, su fecha
-- NO se traía al formulario: se quedaba en ese 1995. Al guardar, le
-- pisaba la real.
--
-- O sea que abrir la historia de un paciente antiguo y guardarla le
-- cambiaba la fecha de nacimiento por el 1 de enero de 1995. Eso ya está
-- corregido en la aplicación, pero las filas que quedaron mal siguen
-- ahí, y son las que hacen que Cumpleaños avise de gente que no cumple.
--
-- EJECUTAR POR BLOQUES Y EN ORDEN. Los bloques 1 y 4 solo miran.


-- ---------------------------------------------------------------------
-- 1. ¿Cuántas hay?  [CONSULTA]
-- ---------------------------------------------------------------------
-- Mira el número antes de borrar nada. Si 'sospechosas' es cero, no hay
-- que hacer nada más y el bloque 2 se puede saltar.
select count(*) filter (where fecha_nacimiento = '1995-01-01') as sospechosas,
       count(*) filter (where fecha_nacimiento is not null)    as con_fecha,
       count(*)                                                as total_pacientes
  from pacientes;

-- Y quiénes son, por si reconoces a alguno. Sin nombres: solo el
-- documento y cuándo se tocó la ficha por última vez.
select documento, modificado_por, modificado_fecha
  from pacientes
 where fecha_nacimiento = '1995-01-01'
 order by modificado_fecha desc nulls last
 limit 50;


-- ---------------------------------------------------------------------
-- 2. Vaciarlas
-- ---------------------------------------------------------------------
-- Una fecha equivocada es peor que ninguna: con ninguna, la aplicación
-- deja la edad en blanco y Cumpleaños no avisa; con la equivocada, las
-- dos cosas mienten con total seguridad.
--
-- Si alguien nació de verdad el 1 de enero de 1995, pierde su fecha y
-- hay que volver a escribirla una vez. Es un caso entre cientos, y el
-- precio de no limpiarlo es que ninguna fecha sea fiable.
update pacientes
   set fecha_nacimiento = null
 where fecha_nacimiento = '1995-01-01';

-- La edad guardada a mano tampoco vale si venía de esa fecha. Se vacía
-- solo donde además no quedó fecha: la aplicación la vuelve a calcular
-- en cuanto alguien escriba la de verdad.
update pacientes
   set edad = null
 where fecha_nacimiento is null
   and edad is not null;


-- ---------------------------------------------------------------------
-- 3. Comprobación  [CONSULTA]
-- ---------------------------------------------------------------------
-- 'sospechosas' tiene que dar cero.
select count(*) filter (where fecha_nacimiento = '1995-01-01') as sospechosas,
       count(*) filter (where fecha_nacimiento is not null)    as con_fecha_real,
       count(*)                                                as total_pacientes
  from pacientes;


-- ---------------------------------------------------------------------
-- 4. De paso: ¿quién puede escribir en la base?  [CONSULTA]
-- ---------------------------------------------------------------------
-- No cambia nada, solo mira. En su momento había dos políticas que
-- dejaban INSERTAR filas a cualquiera con la clave pública del proyecto
-- (el rol 'anon'), y quedó sin confirmar si se cerraron.
--
-- Si esto devuelve alguna fila, cualquiera con la URL del proyecto y la
-- clave pública puede escribir en esa tabla. Leer no -- eso ya está
-- cerrado -- pero escribir sí. En un sistema con historias clínicas vale
-- la pena cerrarlo, y está explicado en fase7_rls.sql, bloque 6.
select tablename, policyname, roles, cmd, qual, with_check
  from pg_policies
 where schemaname = 'public'
   and 'anon' = any(roles)
 order by tablename, policyname;


-- ---------------------------------------------------------------------
-- 5. Marcha atrás
-- ---------------------------------------------------------------------
-- No la hay para el bloque 2: las fechas que se vacían no se pueden
-- recuperar, porque la que había tampoco era la buena. Si quieres
-- guardarlas antes por si acaso, corre esto ANTES del bloque 2:
--
--   create table respaldo_fechas_1995 as
--   select documento, fecha_nacimiento, edad
--     from pacientes where fecha_nacimiento = '1995-01-01';
