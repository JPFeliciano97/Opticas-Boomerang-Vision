-- =====================================================================
-- FASE 2 -- Categorías de gasto, tipo de venta y limpieza de fechas
-- =====================================================================
-- Ejecutar en el editor SQL de Supabase, por bloques y en orden.
--
-- Todo es ADITIVO: no borra ni reescribe ninguna columna existente.
-- La app funciona con o sin estos cambios (detecta si la columna existe),
-- así que se puede desplegar el código antes o después de correr esto.
--
-- Los bloques 3 y 4 van dentro de una transacción: revisa el resultado
-- con la consulta de control y solo entonces confirma con COMMIT.


-- ---------------------------------------------------------------------
-- 1. Categoría de gasto
-- ---------------------------------------------------------------------
-- 'tipo_gasto' (DIARIO/MENSUAL) dice CUÁNDO golpea la caja.
-- 'categoria_gasto' dice QUÉ CLASE de gasto es. Son ejes independientes:
-- en los datos reales, laboratorio y nómina aparecen en ambos tipos.
alter table gastos_caja
  add column if not exists categoria_gasto text default 'SIN CLASIFICAR';

update gastos_caja set categoria_gasto = 'SIN CLASIFICAR'
 where categoria_gasto is null;


-- ---------------------------------------------------------------------
-- 2. Tipo de venta
-- ---------------------------------------------------------------------
-- Hoy la única forma de distinguir una venta menor es que su número
-- empiece por 'MEN-'. Eso es una convención dentro de un texto, no un
-- dato. El histórico se rellena sin ambigüedad a partir del prefijo.
alter table ventas_facturacion
  add column if not exists tipo_venta text;

update ventas_facturacion
   set tipo_venta = case when numero_factura like 'MEN-%' then 'MENOR'
                         else 'GAFAS' end
 where tipo_venta is null;

-- Marca aparte lo que viene de la migración, que lleva prefijo 'LEG-'.
-- 'fecha_venta' NO sirve para esto: el histórico trae fechas futuras.
alter table ventas_facturacion
  add column if not exists origen_registro text;

update ventas_facturacion
   set origen_registro = case when numero_factura like 'LEG-%' then 'MIGRADO'
                              else 'SISTEMA' end
 where origen_registro is null;


-- ---------------------------------------------------------------------
-- 3. Clasificación automática del histórico  [REVISAR ANTES DE COMMIT]
-- ---------------------------------------------------------------------
-- PROPUESTA, no verdad absoluta: agrupa por coincidencia de texto sobre
-- las descripciones reales. El orden importa -- lo más específico va
-- primero, y cada UPDATE solo toca lo que sigue SIN CLASIFICAR, así que
-- ninguna fila se reclasifica dos veces.
begin;

-- Devoluciones a clientes. No son un gasto de operar: es dinero que
-- se regresa por una venta. Mezclarlas con lo demás infla el costo
-- operativo y ensucia el margen, por eso van aparte.
update gastos_caja set categoria_gasto = 'DEVOLUCIONES A CLIENTES'
 where categoria_gasto = 'SIN CLASIFICAR'
   and descripcion ~* '(devoluci)';

-- Arriendo y administración del local
update gastos_caja set categoria_gasto = 'ARRIENDO Y ADMINISTRACION'
 where categoria_gasto = 'SIN CLASIFICAR'
   and descripcion ~* '(arriendo|administraci)';

-- Servicios públicos
update gastos_caja set categoria_gasto = 'SERVICIOS PUBLICOS'
 where categoria_gasto = 'SIN CLASIFICAR'
   and descripcion ~* '(enel|codensa|claro|movistar|internet|acueducto|gas natural|comcel)';

-- Nómina: personal de planta (asesores). Va PRIMERO porque el nombre
-- de la persona es la señal más específica.
update gastos_caja set categoria_gasto = 'NOMINA'
 where categoria_gasto = 'SIN CLASIFICAR'
   and descripcion ~* '(nomina|rosa|nelson|ana leon|alejandra|eps|colsanitas|prestamo)';

-- Honorarios por TURNO: doctor que cubre un día completo. Tarifa fija
-- por día abierto, no dependa de cuántos pacientes entren. Va antes que
-- consulta porque "Dra turno" contiene ambas palabras y manda el turno.
update gastos_caja set categoria_gasto = 'HONORARIOS POR TURNO'
 where categoria_gasto = 'SIN CLASIFICAR'
   and descripcion ~* '(turno|p\.?\s?tur)';

-- Honorarios por CONSULTA: la optómetra cobra por paciente atendido.
-- Es un costo variable que sube y baja con la demanda, a diferencia
-- del turno. Separarlos permite comparar costo por consulta contra
-- costo por día cubierto.
update gastos_caja set categoria_gasto = 'HONORARIOS POR CONSULTA'
 where categoria_gasto = 'SIN CLASIFICAR'
   and descripcion ~* '(dra astrid|consulta|optometra|\ydra\y|\ydr\y|\ydoctora\y|\ydoctara\y|^doc|doctor)';

-- Laboratorio y proveedores (costo de lo vendido)
update gastos_caja set categoria_gasto = 'LABORATORIO Y PROVEEDORES'
 where categoria_gasto = 'SIN CLASIFICAR'
   and descripcion ~* '(laboratorio|lab |cerlent|falcon|zeiss|qarzo|girbro|j\+n|damilu|danmilu|australens|cysolutions|precision|next vision|zafiro|aliens|mf company|bisel|montura|lente|trabajos|consig|paris|pa.o|osmotears|estuche|cremallera|soldadura)';

-- Transporte y mensajería (PICAP)
update gastos_caja set categoria_gasto = 'TRANSPORTE'
 where categoria_gasto = 'SIN CLASIFICAR'
   and descripcion ~* '(picap|picuk|buses|transmilenio|trasnmilenio|moto|patineta|alineacion|carro|domicilio|mensajer)';

-- Alimentación
update gastos_caja set categoria_gasto = 'ALIMENTACION'
 where categoria_gasto = 'SIN CLASIFICAR'
   and descripcion ~* '(almuerzo|onces|pan |cafe|nescafe|gaseosa|empanada|sandw|pizza|agua)';

-- Aseo, papelería e insumos
update gastos_caja set categoria_gasto = 'ASEO E INSUMOS'
 where categoria_gasto = 'SIN CLASIFICAR'
   and descripcion ~* '(jabon|blanqueador|limpiapiso|fabuloso|papel|guantes|alcohol|vasos|escoba|impresion|copias|tinta|sharpie|folder|bolsa)';

-- OJO con MATEO: en el histórico aparece como "DOC MATEO" (¿un doctor?)
-- y en lo reciente como persona a la que se le paga nómina, almuerzos y
-- transporte. Se deja SIN CLASIFICAR a propósito para que decidas:
--   select descripcion, count(*), sum(monto) from gastos_caja
--    where categoria_gasto = 'SIN CLASIFICAR' and descripcion ~* 'mateo'
--    group by 1 order by 3 desc;

-- CONTROL: revisa este resultado ANTES de confirmar.
select categoria_gasto, count(*) as filas, sum(monto) as total
  from gastos_caja group by 1 order by 3 desc;

-- Si el reparto tiene sentido:      commit;
-- Si prefieres deshacerlo todo:     rollback;


-- ---------------------------------------------------------------------
-- 4. Fechas futuras en el histórico  [REVISAR ANTES DE COMMIT]
-- ---------------------------------------------------------------------
-- Hay facturas migradas fechadas DESPUÉS de hoy. Una venta no puede ser
-- de un día que no ha llegado. La app ya las excluye de la analítica,
-- pero conviene arreglar el dato.
select numero_factura, fecha_venta, total, titular_nombre
  from ventas_facturacion
 where fecha_venta > now()
 order by fecha_venta;

-- HIPÓTESIS a verificar contra el Excel original, no aplicar a ciegas:
-- las dos vistas (nov. y dic. de 2026) encajan en el histórico si el año
-- correcto es 2025. Si lo confirmas, este UPDATE les resta un año:
--
-- begin;
-- update ventas_facturacion
--    set fecha_venta = fecha_venta - interval '1 year'
--  where fecha_venta > now()
--    and numero_factura like 'LEG-%';
-- select numero_factura, fecha_venta from ventas_facturacion
--  where numero_factura in ('LEG-TR03207','LEG-TR03239');
-- commit;   -- o rollback


-- ---------------------------------------------------------------------
-- 5. Comprobaciones finales
-- ---------------------------------------------------------------------
-- Lo que quedó sin clasificar, de mayor a menor: son los conceptos que
-- hay que revisar a mano o añadir a los patrones de arriba.
select descripcion, count(*) as veces, sum(monto) as total
  from gastos_caja
 where categoria_gasto = 'SIN CLASIFICAR'
 group by 1 order by 3 desc limit 30;

-- Los dos ejes juntos: confirma que categoría y tipo son independientes.
select categoria_gasto,
       sum(monto) filter (where tipo_gasto = 'DIARIO')  as diario,
       sum(monto) filter (where tipo_gasto = 'MENSUAL') as mensual
  from gastos_caja group by 1 order by 1;
