# Fauna y Flora · identificador de especies

App para identificar fauna y flora con IA (Claude Haiku de Anthropic). Empezó con un catálogo de 95 especies de Puebla y crece sola
con cada especie nueva que alguien fotografía (validada con GBIF).

| Carpeta | Qué contiene |
|---|---|
| `app/` | App Ionic 9 + Angular 21 + Capacitor 8 (web, Android en `app/android`; iOS se agrega en una Mac) |
| `api/` | API en Python (FastAPI): `POST /identificar`, `POST /observaciones/{id}/elegir`, `DELETE /cuenta`, `GET /salud` |
| `supabase/` | Migraciones SQL (tablas, RLS, Storage, límite diario), catálogo inicial (`seed.sql`) y pruebas de permisos |
| `pruebas/e2e/` | Prueba de punta a punta en navegador con un Supabase local de imitación (Windows, Mac o Linux) |

## Cómo funciona

1. La persona entra **sin cuenta** (invitado: inicio de sesión anónimo de Supabase) o con su correo. Un invitado puede crear su cuenta
   después sin perder nada.
2. Toca la cámara (botón central). Mientras encuadra, la app ya busca la ubicación (opcional). La foto se reduce a 1024 px, se
   re-codifica en JPEG (así se borran los datos EXIF) y se sube a `fotos/<su id>/` (bucket privado), con una miniatura de 320 px.
3. La app llama a la API, que responde **por partes** (NDJSON): el nombre aparece en cuanto Claude lo escribe.
4. La API valida la sesión con la clave pública de Supabase, **reserva** un lugar del límite diario en la base de datos (atómico;
   borrar observaciones no lo devuelve) y manda la foto a Claude (razonamiento corto, salida con formato fijo).
5. Mientras Claude termina, el nombre se valida en **GBIF** (sinónimos → nombre aceptado). La observación se guarda en un solo viaje
   (función `guardar_identificacion`). Si la especie es nueva, entra al catálogo (`verificada = false`) y su ficha se escribe aparte,
   después de mostrar el resultado, junto con una foto de referencia de Wikipedia o iNaturalist.
6. Estados: `identificada` (confianza ≥ 0.7), `revisar` (la IA duda: la persona elige entre las parecidas → `elegida`),
   `corregida` (por un admin) y `no_identificada` (foto borrosa o sin animal/planta).
7. **Privado por defecto.** Lo publicado se ve con ubicación aproximada (~10 km); en especies protegidas, sin ubicación.
8. Sin señal, la foto queda en el teléfono y se identifica sola al volver la conexión.

Límites (tabla `ajustes`): 10 identificaciones al día por persona, 3 por invitado, 15 de invitados por red y 500 en total al día.

## Puesta en marcha

Guía paso a paso para tu computadora: [COMO_EJECUTAR.md](COMO_EJECUTAR.md). Lo nuevo de cada versión: [CAMBIOS.md](CAMBIOS.md).

Resumen:
```bash
# Supabase: ejecuta en SQL Editor las migraciones de supabase/migrations/ que falten (en orden) y activa "anonymous sign-ins".
cd api && python -m venv .venv && .venv\Scripts\activate && python -m pip install -r requirements-dev.txt
copy .env.example .env       # y llena SUPABASE_SERVICE_KEY y ANTHROPIC_API_KEY
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
cd app && npm install && npm run start:red      # http://localhost:4200
```
Despliegue de la API: `api/Dockerfile` (Cloud Run, Railway o Render) con las mismas variables y `PRODUCCION=1`.
Después pon su dirección en `app/src/environments/environment.prod.ts`.

## Pruebas
```bash
cd api && pytest                                   # API: 89 pruebas (Claude, GBIF y Supabase simulados)
cd api && python -m scripts.diagnostico            # revisa tus claves, la migración, GBIF y Claude (no muestra las claves)
cd api && python -m scripts.prueba_real foto.jpg   # punta a punta real con un usuario temporal (lo borra al final)
cd api && python -m scripts.evaluar_ia correr      # precisión y velocidad de la IA con 33 fotos reales (~3 centavos de dólar)
cd app && npx ng test --watch=false                # App: 23 pruebas unitarias
# Base de datos (Postgres local): stub de Supabase + migraciones + seed + pruebas de RLS
psql -f supabase/tests/00_stub_supabase.sql -f supabase/migrations/*.sql -f supabase/seed.sql -f supabase/seed_imagenes.sql -f supabase/tests/01_pruebas_rls.sql
# Punta a punta en navegador: ver pruebas/e2e/levantar.py y prueba_e2e.py (26 pasos)
```

## Claves: dónde va cada una
| Clave | Dónde | ¿Secreta? |
|---|---|---|
| URL de Supabase | `api/.env` y `app/src/environments/` | No |
| Clave `anon` / publishable de Supabase | `app/src/environments/` | No (la protege RLS) |
| Clave `service_role` / secret de Supabase | Solo `api/.env` o variables del servidor | **Sí** |
| `ANTHROPIC_API_KEY` | Solo `api/.env` o variables del servidor | **Sí** |
