---
name: boomerang-vision-streamlit-ui
description: Reglas técnicas y convenciones de diseño para trabajar en la interfaz del ERP de Boomerang Visión (óptica colombiana, app Streamlit + Supabase). Úsala SIEMPRE que se vaya a tocar la interfaz de este proyecto -- mover, reorganizar o rediseñar pestañas/botones/formularios, agregar campos nuevos a un formulario, cambiar el layout de una pantalla, o cualquier ajuste visual/de interacción. También consúltala antes de escribir cualquier st.form(), st.tabs(), st.dialog(), st.expander() o number_input con botones +/-, incluso si el pedido no menciona "interfaz" explícitamente -- estas reglas evitan errores de runtime ya confirmados en producción (StreamlitInvalidFormCallbackError, StreamlitAPIException) y varios intentos fallidos de CSS que ya se probaron y no funcionan.
---

# UI/UX para el ERP de Boomerang Visión (Streamlit + Supabase)

Este proyecto es un ERP en Streamlit para una óptica en Colombia, con Supabase como
base de datos. Esta skill resume las reglas técnicas duras y las convenciones de
diseño ya establecidas, aprendidas a lo largo de muchísimas iteraciones reales
(incluyendo errores en producción que ya se diagnosticaron y corrigieron). El
objetivo es no repetir esos mismos errores al seguir tocando la interfaz.

## Antes de tocar la interfaz: lee esto primero

Streamlit re-ejecuta el script COMPLETO en cada interacción. No es una SPA con
estado persistente en el navegador -- cualquier cambio de interfaz debe pensarse
bajo ese modelo. Las siguientes son restricciones DURAS del framework, no
preferencias de estilo -- ignorarlas produce errores reales, no solo un resultado
subóptimo.

### 1. `on_change` está PROHIBIDO en widgets dentro de un `st.form()`

Streamlit lanza `StreamlitInvalidFormCallbackError` en tiempo de ejecución (no en
el momento de escribir el código) si cualquier widget dentro de un `st.form()`
tiene `on_change=`. Esto ya rompió la app en producción una vez en este proyecto.

**Si necesitas corregir un valor mientras se escribe (ej: forzar signo negativo,
reformatear moneda) y el campo está dentro de un form:** no se puede hacer en
vivo. Aplica la corrección a la variable Python DESPUÉS del submit, justo antes
de guardar en la base de datos -- no en el widget.

```python
# ✅ Fuera de un form: on_change funciona en vivo
st.number_input("Cilindro OD", key="cil_od", on_change=force_negative_cyl, args=("cil_od",))

# ❌ Dentro de un st.form(): esto revienta en producción
with st.form("mi_form"):
    st.number_input("Cilindro OD", key="cil_od", on_change=force_negative_cyl, args=("cil_od",))

# ✅ Dentro de un form: corregir DESPUÉS del submit
with st.form("mi_form"):
    cil_od = st.number_input("Cilindro OD", key="cil_od")
    enviar = st.form_submit_button("Guardar")
if enviar:
    cil_od = -abs(cil_od) if cil_od > 0 else cil_od  # corrección aquí, no en el widget
```

Antes de agregar CUALQUIER `on_change` a un campo, confirma si está dentro de un
`with st.form(...):` recorriendo hacia arriba en la indentación. Si el proyecto ya
tiene decenas de forms, un `grep -n "st.form("` rápido contra el rango de líneas
del campo confirma esto en segundos.

### 2. No se puede asignar a `st.session_state[key]` después de que ese widget ya se renderizó en la misma ejecución

Causa `StreamlitAPIException`. El patrón seguro y ya establecido en este proyecto
es el de **trigger flags procesados en un bloque centralizado al inicio del
script**, antes de que se rendericen los módulos:

```python
# Al final de una acción de guardado, en vez de tocar los campos directamente:
st.session_state.trigger_clear_mi_formulario = True
st.rerun()

# Y en un bloque centralizado AL PRINCIPIO del archivo (antes de cualquier módulo):
if st.session_state.get("trigger_clear_mi_formulario"):
    st.session_state.campo_x = ""
    st.session_state.campo_y = 0.0
    st.session_state.trigger_clear_mi_formulario = False
```

Esto también aplica a "prellenar" un campo antes de mostrarlo (ej: cargar los
datos de un paciente en un formulario tras un clic en "Editar") -- es seguro
SIEMPRE que la asignación ocurra en el código ANTES de que ese widget específico
se declare en esa misma pasada del script.

### 3. `st.tabs()` no se puede cambiar de pestaña activa desde Python

No hay forma de forzar programáticamente cuál pestaña queda visible. Ya se
intentó (y se descartó) reemplazar `st.tabs()` por botones en columnas para poder
controlar la posición/selección -- funcionalmente funcionaba, pero el usuario
prefirió estéticamente las pestañas nativas y se revirtió. **No propongas
reemplazar `st.tabs()` por botones a menos que te lo pidan explícitamente
sabiendo el trade-off:** se gana control de navegación, se pierde la apariencia
plana de pestaña nativa (los botones de Streamlit se ven como botones, no como
tabs, incluso con CSS).

Si necesitas "llevar" al usuario a una pestaña específica después de una acción
(ej: un botón "Revisar" que debería abrir la pestaña de Admisión), lo máximo que
se puede hacer es: prellenar los campos de esa pestaña vía session_state (ver
regla 2) y mostrar un `st.info()` claro indicando en qué pestaña están esos datos
cargados. El usuario tiene que hacer el clic manual para verla.

### 4. Estilizar `st.tabs()` con CSS dirigido a clases internas de BaseWeb NO es confiable

Se intentó 2-3 veces en este proyecto (separar visualmente un grupo de tabs del
resto, aplanar la apariencia de botones para que parecieran tabs) apuntando a
selectores como `[data-baseweb="tab-list"] button:nth-child(...)`, y ninguno
tomó efecto de forma verificable. **El único selector CSS confirmado y
documentado que sí funciona en este framework es `.st-key-<key>`**, disponible
cuando el contenedor/widget tiene un parámetro `key=` explícito:

```python
st.markdown("""
    <style>
    .st-key-mi_contenedor button { background-color: transparent; border: none; }
    </style>
""", unsafe_allow_html=True)
with st.container(key="mi_contenedor"):
    st.button("Ejemplo")
```

Antes de escribir CSS dirigido a clases internas de Streamlit/BaseWeb que no
sean `.st-key-`, hay que verificarlo con una fuente actual (documentación oficial
o foro de la comunidad de Streamlit) -- no asumir la estructura del DOM interno.
Ya ha fallado repetidamente por esa vía.

### 5. `st.expander(expanded=...)` solo fija el estado INICIAL, no lo controla en vivo

Para forzar que un expander se abra o cierre como reacción a una acción (ej:
contraerlo automáticamente tras un clic en otro botón), hay que leer y escribir
explícitamente una key propia de session_state, referenciada en el parámetro
`expanded=`:

```python
with st.expander("Título", expanded=st.session_state.get("mi_expander_abierto", False)):
    ...
    if st.button("Acción que debe contraer el panel"):
        st.session_state.mi_expander_abierto = False  # antes del próximo render
        st.rerun()
```

**Ojo:** revisa TODOS los puntos del código que tocan esa misma key. En este
proyecto un bug tardó dos rondas en resolverse porque había otros dos lugares
(una limpieza al cambiar de módulo, y un guardado exitoso en otro flujo) que
reescribían la key a `True` sin que fuera obvio a primera vista. Antes de dar por
buena una corrección de este tipo, busca TODAS las asignaciones a esa key, no
solo el lugar donde se nota el síntoma.

### 6. Los botones +/- de `number_input` son límites duros del lado del cliente

Con `min_value=0`, el botón "-" queda deshabilitado exactamente en 0 -- y como
está deshabilitado, ningún `on_change` se dispara (el valor nunca cambia). No hay
forma de interceptar "el usuario intentó bajar de 0" directamente.

**Para lograr un comportamiento "circular" (ej: un ángulo de 0° a 175° en pasos
de 5°, donde bajar de 0 debería dar la vuelta a 175):** amplía el rango real un
paso de más en cada extremo (`min_value=-5, max_value=180` en vez de `0, 175`),
para que el botón nunca quede deshabilitado, y corrige el valor con `on_change`
en cuanto se sale del rango útil real:

```python
def wrap_valor(key):
    v = st.session_state.get(key, 0)
    if v < 0: st.session_state[key] = 175
    elif v > 175: st.session_state[key] = 0

st.number_input("Ángulo", min_value=-5, max_value=180, step=5, key="mi_angulo", on_change=wrap_valor, args=("mi_angulo",))
```

Si el campo está dentro de un `st.form()` (regla 1), esta corrección se hace
sobre el valor devuelto, después del submit -- no vía `on_change`.

### 7. `st.dialog()` funciona en el navegador real, pero `AppTest` (testing) no ejecuta los botones internos

Confirmado como bug conocido del propio framework de Streamlit, no del código de
este proyecto: si estás escribiendo pruebas automatizadas con `streamlit.testing.v1.AppTest`
para un flujo que usa `st.dialog()`, los clics en botones DENTRO del diálogo no
disparan su callback en el entorno de pruebas (sí funcionan en producción). No
pierdas tiempo depurando "por qué mi código no se ejecuta" si el síntoma es
específicamente eso -- es una limitación externa conocida, verifica el resto del
flujo (que el diálogo se abra/cierre en las condiciones correctas) y sigue
adelante.

## Convenciones de diseño ya establecidas en este proyecto

- **Paleta**: negro / blanco / rojo (`#e57373` como acento). Reutiliza ese color
  para cualquier elemento nuevo que necesite destacar (botones primarios,
  bordes de alerta, etc.), no introduzcas colores nuevos sin que te lo pidan.
- **Idioma**: todo en español (Colombia), incluyendo mensajes de error,
  `st.warning`/`st.error`/`st.success`, labels de campos y nombres de columnas
  mostradas al usuario.
- **Encabezados de sección**: usa la función auxiliar `styled_header(texto, emoji)`
  ya existente en vez de un `st.markdown("# ...")` suelto, para mantener el
  estilo consistente entre módulos.
- **Formato de moneda**: usa siempre `format_currency_co(valor)` para mostrar
  pesos colombianos -- separador de miles con punto, nunca coma ni apóstrofe, y
  preserva el signo negativo (una "ganancia neta" en pérdida debe poder verse
  como negativa, no perder el signo).
- **Hora/fecha**: usa siempre `now_co()` para la hora actual (Colombia, GMT-5) en
  vez de `datetime.now()` puro. Postgres/Supabase normaliza `timestamptz` a UTC al
  devolverlo -- cualquier comparación de fecha/mes/hora sobre un valor leído de
  la base de datos necesita convertirse explícitamente a hora Colombia antes de
  comparar (`hora_co(valor, formato)` ya existe para esto).
- **Limpiar un formulario tras guardar**: usa el patrón de trigger flag (regla 2),
  nunca asignación directa a los campos después del botón de guardado.
- **Auditoría en acciones sensibles**: cualquier UPDATE que modifique datos ya
  guardados (anular, editar, corregir un dato) debe incluir
  `**sello_auditoria()` en el diccionario del update -- ya existe esta función
  auxiliar y registra quién hizo el cambio y cuándo.
- **Validar antes de guardar, no después**: los campos de documento de
  identificación deben pasar por `documento_parece_valido()` (Consultorio, admite
  alfanumérico) o `es_documento_numerico()` (Facturación, solo dígitos) antes de
  persistir -- ya existe este patrón para evitar que se repita el bug real de un
  nombre tecleado por error en el campo de documento.

## Proceso recomendado para cambios de interfaz

1. **Antes de proponer una solución con CSS o un hack de layout**, revisa si hay
   una forma NATIVA/documentada de lograrlo (parámetro nativo del widget, `key=`
   + `.st-key-`, `st.container(horizontal=...)` si la versión de Streamlit lo
   soporta). Preferir lo documentado sobre lo inferido reduce a cero el riesgo de
   repetir un intento fallido.
2. **Si el cambio toca un campo dentro de un formulario**, revisa primero si ese
   campo ya está envuelto en `st.form()` antes de decidir el mecanismo de
   validación/corrección (reglas 1 y 6).
3. **Si el cambio requiere "recordar" un estado entre interacciones** (qué está
   seleccionado, si un panel debe estar abierto, si hay una edición en curso),
   usa una key de session_state explícita y verifica CADA punto del código que
   la lea o escriba antes de dar el cambio por terminado (regla 5).
4. **Después de implementar, valida sintaxis** con `python3 -m py_compile` como
   mínimo. Si vas a levantar un entorno de pruebas con `AppTest`, recuerda la
   limitación de `st.dialog()` (regla 7) para no perseguir un falso bug.
5. **No repitas un intento de CSS/layout que ya falló.** Si ya se intentó algo
   parecido antes en este proyecto (ver reglas 3-4), no lo reintentes con una
   variación menor esperando un resultado distinto -- cambia de enfoque o
   pregunta directamente qué trade-off prefiere el usuario.
