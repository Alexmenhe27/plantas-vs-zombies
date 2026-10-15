# Cambios del 14 de octubre de 2026: más rápida, más segura y con interfaz nueva

## Antes de usarla: 3 pasos que te tocan a ti (5 minutos)

1. **Aplica la migración nueva en Supabase.** Abre tu proyecto → *SQL Editor* → *New query*, pega todo el archivo
   `supabase/migrations/20261014000005_rendimiento_seguridad_privacidad.sql` y pulsa *Run*. No borra datos de nadie
   (solo el esquema temporal `tmp_imagenes`, que sobró de la carga de fotos del catálogo y ya está en `seed_imagenes.sql`).
   Yo no pude aplicarla: el permiso para cambiar tu base de datos en la nube fue rechazado las dos veces que lo intenté,
   así que todo se probó en una copia local con las mismas migraciones.
   **Sin este paso la API nueva no puede identificar** (le faltan las funciones nuevas); `python -m scripts.diagnostico` te lo avisa.
2. **Activa "entrar sin cuenta"** (modo invitado): *Authentication → Sign In / Providers → Allow anonymous sign-ins* → activar.
   Sin esto, el botón "Empezar sin cuenta" muestra un aviso y te lleva a crear una cuenta.
3. **En *Authentication → URL Configuration → Redirect URLs*** agrega `http://localhost:4200/**` si no está (el correo que confirma
   la cuenta de un invitado lleva a `/nueva-contrasena` para elegir su contraseña).

Opcional: hazte administrador para usar el panel de revisión (ver COMO_EJECUTAR.md).

## Velocidad: de ~10 s a ~4 s, con el nombre visible a los ~3 s

Medido con Claude y GBIF reales (5 fotos, base de datos local; con Supabase en la nube súmale unas décimas):

| | Antes | Ahora |
|---|---|---|
| Nombre de la especie visible | al final (~10 s en la app) | **3.2 s** (mediana) |
| Resultado guardado | ~10 s | **4.4 s** (mediana) |

Qué cambió:
- **La IA en dos pasos.** Antes Claude escribía la ficha completa (descripción, hábitat…) en cada foto, aunque la especie ya estuviera
  en el catálogo. Ahora solo identifica; la ficha se escribe aparte (sin la foto, más barata), solo para especies nuevas y después
  de mostrar el resultado.
- **Respuesta por partes (streaming).** La app muestra el nombre en cuanto Claude lo escribe.
- **La ubicación ya no hace esperar.** Se busca al tocar la cámara, mientras encuadras; si no llega a tiempo se identifica sin ella
  (antes podía detener todo hasta 12 s).
- **La pantalla de resultado ya no recarga nada** (antes volvía a pedir la observación, la foto y el catálogo completo).
- **La API valida la sesión sola** (con la clave pública ES256 de Supabase) y guarda todo en **un solo viaje** a la base de datos.
- **GBIF en paralelo:** el nombre se valida mientras Claude termina de escribir, así que no suma tiempo.
- Instrucciones en caché, miniaturas de 320 px para las listas (unas 10 veces menos datos) y catálogo por páginas.

**Precisión (sin perderla):** se midió con `python -m scripts.evaluar_ia` y 33 fotos reales de iNaturalist de especies conocidas.
Antes: 68 % de aciertos de especie (promedio de 2 corridas); ahora: 68 % (promedio de 3). La especie correcta aparece entre las
parecidas en el 84 % de los casos (antes 78 %), justo lo que aprovecha "¿Cuál de estas es?". También se probó responder **sin
razonar**: casi el doble de rápido, pero acertaba 54-58 %, así que se descartó (`IA_RAZONAMIENTO=bajo`, el valor por defecto).
Gasto total en IA de todo este trabajo (evaluaciones y pruebas reales): unos **0.13 dólares**.

## Seguridad y privacidad

- **Límite diario a prueba de trucos.** Antes, borrar una observación devolvía el cupo (identificar, borrar, repetir = IA sin límite)
  y 10 peticiones al mismo tiempo pasaban todas. Ahora se cuenta en `uso_ia`, que la app no puede leer ni borrar, y la API **reserva
  el lugar antes** de llamar a la IA, con un candado por persona. Si la IA falla, el lugar se devuelve.
- **Invitados:** 3 al día, y como mucho 15 desde una misma red (huella anónima de la IP que se borra a los 3 días).
- **Tope global de 500 identificaciones al día** para proteger tu saldo de Claude.
- Todos los números viven en la tabla `ajustes` de Supabase (antes estaban repetidos en tres lugares).
- **Privado por defecto.** Las observaciones nuevas son privadas (las 13 que había también pasaron a privadas). Si publicas, los demás
  ven la ubicación **aproximada (~10 km)**; en especies protegidas, ninguna. La vista `observaciones_publicas`, que Supabase marcaba
  como ERROR de seguridad, se cambió por la función `avistamientos_publicos`.
- **Catálogo validado con GBIF:** una especie nueva solo entra si GBIF la reconoce; los sinónimos se guardan con el nombre aceptado
  (y las formas domésticas se respetan: *Canis familiaris* → *Canis lupus familiaris*, no el lobo).
- 5 políticas RLS más rápidas, índices nuevos y búsqueda sin acentos con índice de trigramas.
- **Eliminar mi cuenta** (obligatorio en las tiendas de apps): borra la cuenta, las fotos y las observaciones.
- En producción (`PRODUCCION=1`) la persona no ve detalles técnicos de los errores; el Dockerfile corre sin privilegios.

## Interfaz nueva

Sistema de diseño propio ("guía de campo moderna"): verde musgo y maíz, tipografía Fraunces (títulos y nombres científicos en cursiva)
y Manrope, un color por grupo, **modo oscuro** (automático o elegido) y fuentes incluidas en la app (no dependen de internet).

- **Bienvenida con "Empezar sin cuenta"**: se prueba en un toque. Después, el invitado crea su cuenta sin perder nada.
- **Botón de cámara al centro de la barra**: identificar está a un toque desde cualquier pantalla.
- **Una sola pantalla de análisis y resultado**: escaneo animado sobre tu foto, el nombre aparece en cuanto llega y la ficha se completa sola.
- **"¿Cuál de estas es?"**: si la IA duda, eliges entre las parecidas, con sus fotos (del catálogo o de Wikipedia).
- **"¿No es correcto?"** manda una observación a revisión.
- **Colección**: tus especies como tarjetas, avance por grupo, línea de tiempo y **tu mapa** (ubicación exacta, solo tú la ves).
- **Explorar**: búsqueda sin acentos, filtros, carga por páginas y **mapa de avistamientos públicos** (MapLibre + OpenStreetMap, gratis).
- **Sin señal**: la foto se guarda en el teléfono y se identifica sola al volver la conexión (o el cupo).
- **Compartir**, vibración al identificar, esqueletos de carga y accesibilidad (zoom permitido, foco visible, "reducir movimiento").
- **Panel de revisión** para administradores (confirmar especies y revisar las fichas que escribió la IA).
- **Aviso de privacidad y términos** en lenguaje claro.
- **Android**: proyecto nativo agregado (`app/android`) con permisos de cámara, galería y ubicación.

## Archivos

- **Base de datos:** `supabase/migrations/20261014000005_rendimiento_seguridad_privacidad.sql` (nueva) y `supabase/tests/*`.
- **API:** `app/ia.py`, `app/main.py`, `app/config.py`, `app/supabase_client.py` y `app/fotos_especies.py`; nuevos `app/identificacion.py`,
  `app/sesion.py`, `app/taxonomia.py`, `scripts/evaluar_ia.py` y `scripts/evaluacion/`; además `scripts/diagnostico.py`,
  `scripts/prueba_real.py`, `requirements.txt`, `Dockerfile`, `.env.example` y todas las pruebas.
- **App:** casi toda reescrita (`src/app/**`, `src/styles/`, `src/index.html`, `public/`), `angular.json`, `package.json` y `android/`.
- **Pruebas de punta a punta:** `pruebas/e2e/` (ahora corren en Windows con `levantar.py`); se borró `levantar.sh`.

## Pruebas que pasaron

- **API: 89 de 89** (antes 41). **App: 23 de 23** y compilación de producción sin errores ni avisos.
- **Base de datos: todas** las de `supabase/tests/01_pruebas_rls.sql` (límite, invitados, red, tope global, privacidad, colección, revisión).
- **Navegador de punta a punta: 26 de 26** (invitado, streaming, especie nueva con GBIF, "¿Cuál de estas es?", límite que no se salta
  borrando, invitado → cuenta, modo oscuro, mapas, privacidad entre personas, sin conexión, panel de revisión y eliminar cuenta).
- Medición real con Claude y GBIF reales (arriba).

## Lo que falta o depende de ti

- Los 3 pasos del principio (migración, invitados y enlace de correo).
- **Publicar la API** (Cloud Run, Railway o Render, con el `Dockerfile`) y poner su dirección en `app/src/environments/environment.prod.ts`
  (`apiUrl`). La app nativa la necesita: en el teléfono no existe "localhost".
- **Compilar el APK**: abre `app/android` con Android Studio, con JDK 21 (el JDK 25 que trae tu Android Studio puede no funcionar con el
  Gradle de Capacitor 8). Para iOS hace falta una Mac (`npx cap add ios`).
- La protección contra contraseñas filtradas de Supabase es del plan de pago; se puede activar ahí si algún día cambias de plan.

---

# Cambios del 13 de octubre de 2026 (madrugada del 14): solo Claude, revisión completa

## Por qué Claude rechazaba las fotos

Probé tu clave directamente contra Claude. La respuesta real fue: *"This API key is not scoped to a workspace, so this request
must include the anthropic-workspace-id header"*. Tu clave era de ámbito **"Organización"**, y ese tipo de clave no sirve
sola. La API solo mostraba "Claude rechazó la petición" y escondía el motivo. Antes de eso hubo otros dos problemas:
en `api/.env` estaba el **identificador** de la clave (`apikey_…`) y después la clave **abreviada** que muestra la consola (con "...").

**Solución:** una clave nueva del espacio de trabajo "Default" (ver COMO_EJECUTAR.md, paso 3b). Si prefieres conservar
una clave de Organización, la API ahora acepta `ANTHROPIC_WORKSPACE_ID` en `api/.env`.

## Qué cambió

- **Solo Claude.** Se quitó todo lo de Gemini (código, variables, pruebas y guía). La IA es Claude Haiku 5.5:
  razonamiento corto, respuesta con el formato exacto de la ficha y un reintento automático si Claude está saturado.
- **Mensajes con la causa real.** Clave de Organización, clave inválida o incompleta, sin saldo, sin permiso,
  modelo inexistente, límite de uso, saturado, sin internet y tiempo agotado tienen su propio mensaje.
  Cualquier otro rechazo ahora muestra el motivo que da Claude en vez de esconderlo.
- **Cualquier animal.** Antes la IA descartaba perros, gatos y otros animales domésticos; ahora los identifica.
- **Tipo de imagen verificado.** El tipo de la foto se toma de sus primeros bytes, no de lo que diga el archivo.
  Si una PNG se guardaba como JPEG, Claude rechazaba la petición.
- **`api/.env` más tolerante.** Funciona aunque el Bloc de notas lo guarde con BOM o la clave quede entre comillas.
  Si `IA_MODELO` sigue diciendo `gemini-…`, se usa `claude-haiku-5-5`.
- **Diagnóstico:** `python -m scripts.diagnostico` dice con qué empieza y cuánto mide la clave que está leyendo
  (sin mostrarla) y hace una identificación real con Claude.
- **La app espera hasta 2 minutos** (la API tarda como máximo ~95 s si Claude está saturado y reintenta).
- Se recuperaron los cambios de nombre de tu versión (sin "Plantas vs Zombies"), que la actualización anterior había revertido
  en `api/app/main.py`, y se volvió a agregar `api/.env.example`, ahora solo con Claude.
- `.gitattributes`: los scripts `.sh` se guardan con saltos de línea de Linux (con los de Windows no corrían).

## Archivos

`api/app/ia.py`, `api/app/config.py`, `api/app/main.py`, `api/.env.example` (nuevo), `api/scripts/diagnostico.py`,
`api/scripts/prueba_real.py`, `api/tests/conftest.py`, `api/tests/test_ia.py`, `api/tests/test_api.py`,
`app/src/app/core/api.service.ts`, `app/src/app/core/api.service.spec.ts`, `pruebas/e2e/fake_ia.py`, `pruebas/e2e/levantar.sh`,
`pruebas/e2e/prueba_e2e.py`, `.gitattributes` (nuevo), `COMO_EJECUTAR.md`, `README.md`, `CAMBIOS.md`.
No cambia nada en la base de datos.

## Pruebas

- API: 40 de 40 (Claude simulado). App: 14 de 14 y la compilación de producción sin errores.
- Navegador de punta a punta: 21 de 21 (registro, identificación, catálogo, límite diario, permisos), con Claude simulado.
- Tu base de datos real en Supabase: las 4 migraciones aplicadas, 99 especies (95 verificadas), 10 observaciones guardadas,
  bucket de fotos privado. No hizo falta cambiarla.
- **Con Claude real:** tu clave llega a Claude y la respuesta confirmó la causa de arriba. La identificación con Claude real
  queda pendiente de tu clave nueva: córrela con `python -m scripts.diagnostico C:\ruta\a\foto.jpg`.

---

# Cambios del 13 de octubre de 2026 (noche): la identificación ya funciona de punta a punta

## Qué estaba fallando

En los registros de Supabase se veía lo mismo en cada intento: la API validaba la sesión, revisaba el límite y descargaba
la foto, pero **nunca guardaba el resultado**. La falla estaba en Gemini: en varios intentos tardó más de los 45 s que la API
esperaba (la app borraba la foto unos 46 s después), y en otros lo rechazó al instante. Nunca se había guardado ni una observación.

## Qué cambió

- **Modelos de respaldo:** si el modelo de `IA_MODELO` no existe, se quedó sin cuota (la cuota gratuita es por modelo),
  da error o tarda más de 40 s, la API prueba sola `gemini-flash-latest`, `gemini-flash-lite-latest` y `gemini-2.5-flash`
  (configurable con `IA_MODELOS_RESPALDO`). Si la clave es inválida, no pierde tiempo probando otros.
- **Tiempos:** 40 s por modelo (`IA_TIEMPO_MAXIMO`) y 110 s en total (`IA_TIEMPO_TOTAL`). La app espera hasta 150 s.
- **Razonamiento corto según el modelo:** `thinkingLevel: low` en Gemini 3 y `thinkingBudget: 0` en Gemini 2.5.
- **Ubicación:** en el navegador, si nadie respondía al aviso de permiso de ubicación, la app podía quedarse esperando para siempre.
  Ahora espera como máximo 12 s y la pide mientras sube la foto, no después.
- **Diagnóstico:** `python -m scripts.diagnostico` revisa Supabase, el bucket, la clave de Gemini y los modelos, y hace una identificación de prueba.
  `python -m scripts.prueba_real foto.jpg` hace el recorrido completo de la app con un usuario temporal y lo borra al final.
- **Limpieza:** se borraron `api/app/ia (1).py` (copia vieja), `api/app/puebla.py`, `api/app/data/puebla.geojson` y `api/tests/test_puebla.py`,
  que la versión anterior decía haber eliminado. Se agregó `api/.env.example`, que la guía mencionaba pero no existía.
- **Pruebas:** ya no dependen del modelo escrito en tu `api/.env`. Se agregaron pruebas de los modelos de respaldo.

## Pruebas que pasaron

- API: 35 de 35. App: 14 de 14 y la compilación de producción sale sin errores.
- **Con tus servicios reales:** diagnóstico completo en verde y prueba de punta a punta: usuario temporal → foto subida al bucket → `POST /identificar`
  → *Guacamaya verde (Ara militaris)*, confianza 0.95, en 20.6 s → observación guardada y legible por la app. Todo lo de la prueba se borró al final.

---

# Cambios del 13 de octubre de 2026: más rápida y sin límite a Puebla

## Por qué tardaba y fallaba

1. **Gemini tardaba más de 60 segundos** y la API se rendía ("Gemini tardó demasiado en responder"). Había tres causas:
   - **Razonamiento largo:** los modelos Gemini 3 "piensan" a fondo por defecto, y eso es lo más lento.
   - **Petición pesada:** en cada foto se le mandaba el catálogo completo de 95 especies.
   - **Fotos grandes:** se mandaban a 1600 px.
2. **`gemini-2.5-flash` ya no está disponible** para claves nuevas (corregido el mismo día: ahora se usa `gemini-3.8-flash`).
3. **Fuera de Puebla la app rechazaba la foto.**

## Qué cambió

**Velocidad**
- Se le pide a Gemini razonamiento corto (`thinkingLevel: low`). Si el modelo no acepta ese ajuste, la API repite sola sin él.
- Ya no se manda el catálogo: la petición bajó de unos 6 000 a unos 1 600 caracteres.
- Las fotos se reducen a 1024 px: pesan unas 4 veces menos y se suben y analizan más rápido.
- La API revisa el límite diario y descarga la foto al mismo tiempo, no una después de otra.
- Si Gemini responde "saturado", la API reintenta una vez sola.
- Hay un tiempo máximo claro: la API espera a Gemini 45 s (`IA_TIEMPO_MAXIMO`) y la app 2 minutos. Después avisa en vez de quedarse cargando.

**Especies de cualquier lugar, sin guardar de más ("catálogo que crece solo")**
- Gemini identifica cualquier animal o planta y devuelve también su ficha: nombre común y científico, grupo, familia,
  descripción, hábitat, alimentación, tamaño, si está en la NOM-059 y si es introducida.
- Si la especie ya está en el catálogo, se usa la que existe y no se duplica.
- Si es nueva, se agrega **una sola vez**, marcada como "generada por la IA" (`verificada = false`) para revisarla después.
  Solo se agrega con confianza de 0.5 o más, para no llenar el catálogo de errores. La foto de referencia se busca en Wikipedia
  en segundo plano, sin retrasar la respuesta.
- Así **solo se guardan las especies que alguien de verdad fotografió**, en vez de miles de especies que nadie va a ver.
- Las 95 especies de Puebla se quedan como base revisada (`verificada = true`).
- Se quitó el bloqueo por ubicación. La ubicación sigue siendo opcional y ahora se le pasa a Gemini como pista para acertar mejor.
- Las especies protegidas (NOM-059) siguen mostrando su ubicación aproximada en lo público.

**Pantallas**
- La ficha de una especie creada por la IA dice *"Ficha generada por la IA… puede tener errores"*.
- En "No estamos seguros" se ven también especies parecidas que todavía no están en el catálogo.
- Los textos ya no dicen "Puebla" (inicio de sesión, catálogo, ficha, perfil, pasos de la identificación).

**Base de datos:** migración `supabase/migrations/20261013000004_catalogo_abierto.sql`, **ya aplicada** en tu Supabase.
Solo agrega la columna `especies.verificada` y no borra nada.

**Se eliminaron** (ya no se usan): `api/app/puebla.py`, `api/app/data/puebla.geojson`, `api/tests/test_puebla.py`.

**Pruebas:** API 31 de 31, app 14 de 14, base de datos completa y navegador 21 de 21. Las pruebas del navegador incluyen
una especie nueva fotografiada en la CDMX que se agrega sola al catálogo.
**Sin probar todavía:** con tu clave real de Gemini y la búsqueda de fotos en Wikipedia, porque desde aquí no hay acceso a esos servicios.

---

# Cambios del 12 de octubre de 2026: correcciones y mejoras

## 1. Error al subir imágenes ("no tienes internet")

**Causa real:** la foto sí se subía a Supabase (se ve en los registros de Storage a las 22:06). Lo que fallaba era el paso siguiente: la API de Python
no tenía su configuración (archivo `api/.env` ausente o incompleto). Al intentar hablar con Supabase con una URL vacía se caía
con un error 500 **sin los encabezados CORS**. Por eso el navegador no podía leer la respuesta y la app lo mostraba como "sin internet".

**Corrección:**
- La API revisa su configuración y, si falta algo, responde con un mensaje claro: *"La API no está configurada: faltan … en api/.env"*.
- Cualquier error inesperado de la API ahora sale como mensaje legible y con CORS, así el navegador siempre lo puede leer.
- Si Supabase no responde, la API lo dice (*"No pudimos conectar con la base de datos"*) en vez de caerse.
- La app solo dice "sin conexión" cuando el equipo de verdad no tiene internet. Para los demás casos hay mensajes propios:
  servidor apagado (con la dirección que intentó), foto rechazada por Supabase (con la causa en español) o API sin configurar.
- Si la foto se subió pero la identificación falló, la app la borra para no dejar archivos sueltos.
- La API acepta conexiones desde el cel en la misma red Wi-Fi (CORS para IPs privadas como 192.168.x.x).

## 2. Base de datos en español

Migración `supabase/migrations/20261012000003_base_en_espanol.sql`, **ya aplicada** en tu proyecto de Supabase.
Solo renombra objetos, no borra nada. Se conservaron tu perfil, las 95 especies y todo lo que ya existía.

| Antes | Ahora |
|---|---|
| `profiles` (username, role, created_at) | `perfiles` (nombre_usuario, rol, creado_en). Valores de rol: `usuario` / `admin` |
| `species` (common_name, scientific_name, kingdom, is_protected, …) | `especies` (nombre_comun, nombre_cientifico, reino, protegida, categoria_nom059, introducida, familia, descripcion, imagen_url, **imagen_fuente** nueva, …) |
| `observations` (user_id, photo_path, species_id, ai_confidence, status, is_public, …) | `observaciones` (usuario_id, ruta_foto, especie_id, ia_confianza, estado, es_publica, …) |
| vista `public_observations` | vista `observaciones_publicas` |
| funciones `is_admin`, `handle_new_user`, `username_disponible` | `es_admin`, `crear_perfil`, `nombre_usuario_disponible` |

También se renombraron índices, restricciones y disparadores. La app, la API, el catálogo, las pruebas y la guía usan los nombres nuevos.

## 3. Imágenes que no cargaban

**Causa:** ninguna especie del catálogo tenía foto (`imagen_url` vacía), y la app no tenía qué mostrar cuando una imagen fallaba.

**Corrección:**
- Las 95 especies tienen ahora una foto real de Wikimedia Commons (fotos con licencia libre). Comprobé una por una que cada enlace devuelve una imagen.
  Revisé a mano las que no mostraban al animal o la planta (un dibujo y dos mapas) y las cambié por fotos.
- El crédito de cada foto queda en `especies.imagen_fuente` y se muestra en la ficha ("Foto de referencia: Wikimedia Commons").
- Script reproducible: `supabase/seed_imagenes.sql` (ya aplicado; sirve para un proyecto nuevo).
- Las fotos se ven en: catálogo (miniatura), ficha (portada), resultado de la identificación (foto de referencia para comparar con la tuya)
  y "especies parecidas" cuando la IA no está segura. Las fotos de las personas siguen viéndose en Inicio, Historial y la ficha.
- Si un enlace falla, en su lugar aparece el icono del grupo (ave, mamífero, planta…), nunca un hueco roto.

## 4. Tamaño y proporciones de las imágenes

- Componente nuevo `app-foto` (`app/src/app/shared/foto.component.ts`), usado por todas las imágenes de la app. Tiene una caja de tamaño fijo y recorta
  la foto sin deformarla (`object-fit: cover`). Muestra un fondo con icono mientras carga y una transición suave al aparecer.
- Tamaños: catálogo 64×64, historial 56×56, inicio 132×92, ficha cuadrada (máx. 440 px de alto), resultado 320 px de alto.
- En la computadora la app se muestra como una columna de teléfono de 480 px. Antes las fotos se estiraban a todo el ancho de la pantalla y quedaban muy recortadas.
- Las listas largas cargan las fotos solo cuando se acercan a la pantalla, lo que ahorra datos en el cel.

## 5. Revisión general

- **Errores de Gemini con causa clara (13 de octubre):** antes cualquier fallo de Gemini decía "El servicio de identificación no responde".
  Ahora la app dice si es la clave, la cuota gratuita, el modelo, Gemini saturado o falta de internet, y la terminal de la API
  escribe el detalle técnico (línea `WARNING: Fallo al identificar con Gemini: …`). Archivos: `api/app/ia.py`, `api/app/main.py`.
- **Modelo de Gemini:** `gemini-2.5-flash` ya no está disponible para claves nuevas. El modelo por defecto ahora es `gemini-3.8-flash` (plan gratuito). Archivos: `api/app/config.py`, `api/.env.example`.

- Fotos HEIC (iPhone) en un navegador de computadora: antes daban un error genérico, ahora el mensaje es *"No pudimos leer esa imagen. Usa una foto JPG o PNG."*.
- La instrucción para hacerte administrador en la guía usaba los nombres viejos; está corregida.
- La guía tiene una tabla de errores actualizada con los mensajes nuevos y una sección **"Actualizar a una versión nueva"**.

## Archivos modificados

**API (Python):** `api/app/main.py`, `api/app/config.py`, `api/app/supabase_client.py`, `api/app/ia.py`, `api/.env.example`, `api/requirements.txt`,
`api/scripts/catalogo_gbif.py`, `api/tests/conftest.py`, `api/tests/test_api.py`, `api/tests/test_ia.py`, `api/tests/test_catalogo_gbif.py`

**App (Angular/Ionic):**
- `core/modelos.ts`, `core/api.service.ts`, `core/api.service.spec.ts`, `core/fotos.service.ts`, `core/fotos.service.spec.ts`,
  `core/supabase.service.ts`, `core/observaciones.service.ts`, `core/catalogo.service.ts`, `core/grupos.ts`, `core/grupos.spec.ts`, `core/ubicacion.service.ts`
- `identificar/inicio.page.*`, `identificar/analizando.page.*`, `especies/catalogo.page.*`, `especies/ficha.page.*`,
  `observaciones/historial.page.*`, `observaciones/observacion.page.*`, `perfil/perfil.page.*`
- `shared/foto.component.ts` y `shared/foto.component.spec.ts` (nuevos)
- `src/styles.scss`, `src/environments/environment.ts`, `src/environments/environment.prod.ts`, `package.json` (script `start:red`)

**Base de datos:** `supabase/migrations/20261012000003_base_en_espanol.sql` (nuevo), `supabase/seed_imagenes.sql` (nuevo), `supabase/seed.sql`,
`supabase/tests/01_pruebas_rls.sql`

**Pruebas y documentación:** `pruebas/e2e/levantar.sh`, `pruebas/e2e/prueba_e2e.py`, `pruebas/e2e/fake_ia.py`, `COMO_EJECUTAR.md`, `README.md`, `CAMBIOS.md`

## Pruebas que pasaron

- API: 29 de 29 (incluye los casos nuevos: falta configuración, Supabase caído, error inesperado con CORS, conexión desde el cel y cada tipo de error de Gemini).
- App: 14 de 14 pruebas unitarias, y la compilación sale sin errores.
- Base de datos: todas las pruebas de permisos (RLS) con los nombres en español.
- Prueba completa en navegador simulando un teléfono: 21 de 21 pasos. Incluye que las fotos del catálogo y de la ficha no se deformen
  (una foto vertical de 600×900 se recorta en una caja cuadrada sin estirarse) y que un enlace roto muestre el icono.

**Sin probar todavía:** la app conectada a tu Supabase real con Gemini real. Desde aquí no hay acceso de red a Supabase, así que esa prueba la haces tú.
