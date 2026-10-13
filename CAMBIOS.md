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

- Componente nuevo `pvz-foto` (`app/src/app/shared/foto.component.ts`), usado por todas las imágenes de la app. Tiene una caja de tamaño fijo y recorta
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
