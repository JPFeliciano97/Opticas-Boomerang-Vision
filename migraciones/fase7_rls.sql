-- =====================================================================
-- FASE 7 -- Row Level Security (RLS)
-- =====================================================================
-- LEE ESTO ENTERO ANTES DE EJECUTAR NADA.
--
-- Supabase avisa de "RLS Disabled in Public" y el aviso es real, pero la
-- solución NO es activar RLS a secas. Con RLS activo y sin políticas,
-- Postgres bloquea TODO: la app se queda en blanco, sin pacientes, sin
-- ventas y sin gastos. Hay que activarlo y dar permiso en el mismo paso.
--
-- Y lo que se gana depende de UNA cosa que hay que averiguar primero.


-- ---------------------------------------------------------------------
-- 1. ¿Cómo está cada tabla ahora?  [CONSULTA]
-- ---------------------------------------------------------------------
select c.relname                                    as tabla,
       c.relrowsecurity                             as rls_activo,
       (select count(*) from pg_policies p
         where p.schemaname = 'public' and p.tablename = c.relname) as politicas
  from pg_class c
  join pg_namespace n on n.oid = c.relnamespace
 where n.nspname = 'public' and c.relkind = 'r'
 order by c.relname;


-- ---------------------------------------------------------------------
-- 2. Averigua qué llave usa la app  [NO ES SQL]
-- ---------------------------------------------------------------------
-- Ve a Supabase -> Settings -> API. Verás dos llaves:
--
--   anon public        -- pensada para navegadores. NO puede saltarse RLS.
--   service_role secret -- para servidores. SE SALTA RLS siempre.
--
-- Compara cuál de las dos es la que está en Streamlit Cloud como
-- SUPABASE_KEY. No hace falta copiarla a ningún sitio: basta comparar
-- los primeros caracteres. Según cuál sea, sigue el bloque 3a o el 3b.
--
-- POR QUÉ IMPORTA, sin rodeos:
--
--   Con service_role: activar RLS sin políticas deja la app funcionando
--   igual (la llave se salta RLS) y cierra la puerta a cualquiera que
--   tenga solo la anon. Protección de verdad.
--
--   Con anon: para que la app siga funcionando hay que darle permiso a
--   la anon sobre todo, y eso deja las cosas casi como estaban. Se gana
--   que el permiso queda escrito y se puede ir estrechando, y se calla
--   el aviso -- pero llamarlo "ya está protegido" sería mentira.
--
-- Esta app corre en un servidor, no en el navegador del cliente: la
-- llave nunca llega al visitante. Para ese caso service_role es la
-- llave correcta, SIEMPRE QUE no entre nunca en el repositorio ni en
-- una captura de pantalla. El .gitignore ya cubre lo primero.


-- ---------------------------------------------------------------------
-- 3a. LA APP USA service_role  -- ESTE ES EL BLOQUE A EJECUTAR
-- ---------------------------------------------------------------------
-- Comprobado con el dueño el 30-08-2026: SUPABASE_KEY en Streamlit Cloud
-- es la llave service_role, y siempre lo ha sido.
--
-- Activa RLS sin políticas. La app sigue funcionando igual, porque
-- service_role se salta RLS; cualquiera que tenga solo la llave anon
-- deja de ver absolutamente nada.
--
-- Recorre TODAS las tablas de public en vez de una lista escrita a mano:
-- una lista se queda vieja en cuanto se crea una tabla nueva, y una
-- tabla olvidada es justo el agujero que esto viene a tapar.
do $$
declare t text;
begin
  for t in
    select c.relname
      from pg_class c
      join pg_namespace n on n.oid = c.relnamespace
     where n.nspname = 'public'
       and c.relkind = 'r'
  loop
    execute format('alter table public.%I enable row level security', t);
  end loop;
end $$;


-- ---------------------------------------------------------------------
-- 3b. SI LA APP USARA anon  -- NO APLICA AQUÍ, se deja documentado
-- ---------------------------------------------------------------------
-- No ejecutar: esta app usa service_role (ver 3a). Queda escrito por si
-- algún día se cambia de llave.
--
-- Activa RLS y le da permiso a la llave anon sobre todo, que es lo que
-- la app necesita hoy para seguir funcionando. Es el primer paso, no el
-- último: sin cambiar de llave, la protección sigue siendo la de antes.
--
-- do $$
-- declare t text;
-- begin
--   foreach t in array array['pacientes','historias_clinicas',
--                            'ventas_facturacion','gastos_caja','inventario',
--                            'laboratorios','pagos_saldos','configuracion',
--                            'facturas_laboratorio','pagos_laboratorio']
--   loop
--     execute format('alter table %I enable row level security', t);
--     execute format('drop policy if exists app_todo on %I', t);
--     execute format($f$create policy app_todo on %I
--                        for all to anon, authenticated
--                        using (true) with check (true)$f$, t);
--   end loop;
-- end $$;


-- ---------------------------------------------------------------------
-- 4. Comprobación  [CONSULTA]
-- ---------------------------------------------------------------------
-- Corre esto DESPUÉS y luego abre la app y navega por todos los módulos.
-- Si algo sale vacío que antes tenía datos, ve directo al bloque 5.
select c.relname as tabla,
       c.relrowsecurity as rls_activo,
       coalesce(string_agg(p.policyname, ', '), '(sin políticas)') as politicas
  from pg_class c
  join pg_namespace n on n.oid = c.relnamespace
  left join pg_policies p on p.schemaname = 'public' and p.tablename = c.relname
 where n.nspname = 'public' and c.relkind = 'r'
 group by c.relname, c.relrowsecurity
 order by c.relname;


-- ---------------------------------------------------------------------
-- 5. Marcha atrás
-- ---------------------------------------------------------------------
-- Si la app se rompe, esto la devuelve a como estaba. No borra ni un
-- dato: RLS solo controla quién ve qué, no qué hay guardado.
--
-- do $$
-- declare t text;
-- begin
--   foreach t in array array['pacientes','historias_clinicas',
--                            'ventas_facturacion','gastos_caja','inventario',
--                            'laboratorios','pagos_saldos','configuracion',
--                            'facturas_laboratorio','pagos_laboratorio']
--   loop
--     execute format('alter table %I disable row level security', t);
--   end loop;
-- end $$;
