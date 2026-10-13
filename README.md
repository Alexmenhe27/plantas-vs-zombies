# Identificador de fauna y flora

App móvil para identificar fauna y flora con IA (Google Gemini, plan gratuito). Empezó con un catálogo de 95 especies de Puebla y crece sola con cada especie nueva que se fotografía.

| Carpeta | Qué contiene |
|---|---|
| `app/` | App Ionic 9 + Angular 21 + Capacitor 8 (Android, iOS y web) |
| `api/` | API en Python (FastAPI): `POST /identificar` y `GET /salud` |
| `supabase/` | Migraciones SQL (tablas, RLS, Storage), catálogo inicial (`seed.sql`) y pruebas de permisos |
| `pruebas/e2e/` | Prueba de punta a punta en navegador con un Supabase local de imitación |

## Cómo funciona

1. La persona inicia sesión (Supabase Auth, correo y contraseña).
2. Toma o elige una foto. La app la reduce a 1024 px y la re-codifica en JPEG (así se borran los datos EXIF) y la sube a `fotos/<su id>/` (bucket privado).
3. La app llama a la API con la ruta de la foto y la ubicación.
4. La API valida la sesión, aplica el límite de 10 al día y manda la foto a Gemini (con la ubicación como pista, si la hay).
   Si el modelo configurado no existe, se quedó sin cuota, falla o tarda más de 40 s, prueba solo los modelos de respaldo.
   Gemini identifica cualquier animal o planta y devuelve también los datos de su ficha.
5. **Catálogo que crece solo:** si la especie ya está en `especies` se usa esa; si no, se agrega con `verificada = false`
   (solo si la confianza es ≥ 0.5) y la API busca en segundo plano una foto de referencia en Wikipedia.
   Así se guardan solo las especies que alguien de verdad fotografió.
6. Estados: `identificada` (confianza ≥ 0.7), `revisar` (confianza baja, muestra especies parecidas), `no_identificada` (foto borrosa o sin animal/planta).

## Puesta en marcha

Guía paso a paso para tu computadora: [COMO_EJECUTAR.md](COMO_EJECUTAR.md).

### 1. Supabase
Ya existe: tu proyecto (`https://boppdniulsvoyevhoerp.supabase.co`), con las tres migraciones,
el catálogo (95 especies) y sus fotos de referencia aplicados el 2026-10-12. La URL y la clave pública ya están en `app/src/environments/`.

Tablas (todo en español): `perfiles`, `especies`, `observaciones` y la vista `observaciones_publicas`.
Fotos: las de las personas van al bucket privado `fotos`; las de referencia del catálogo son enlaces a Wikimedia Commons
(`especies.imagen_url`, con el crédito en `especies.imagen_fuente`).

Para un proyecto nuevo: en *SQL Editor* ejecuta, en orden, los archivos de `supabase/migrations/`, luego `supabase/seed.sql`
y `supabase/seed_imagenes.sql`.
- *Authentication > URL Configuration*: agrega la URL de la app a *Redirect URLs* (para confirmar correo y recuperar contraseña).
- Para hacerte administrador: `update public.perfiles set rol = 'admin' where nombre_usuario = 'TU_USUARIO';`

### 2. API
```bash
cd api
python -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env      # y llena SUPABASE_URL, SUPABASE_SERVICE_KEY, GEMINI_API_KEY
uvicorn app.main:app --reload --port 8000
# http://localhost:8000/salud  y  http://localhost:8000/docs
```
Despliegue: `Dockerfile` listo para Google Cloud Run (o Railway/Render), con las mismas variables de entorno.

### 3. App
```bash
cd app
npm install
# environment.ts ya apunta al Supabase real; solo cambia apiUrl si la API no corre en localhost:8000
npm start                 # http://localhost:4200
```
Teléfono: `npx cap add android` / `npx cap add ios`, luego `npm run build && npx cap sync` y abre el proyecto nativo.
Para la cámara y el GPS en Android/iOS hay que añadir los textos de permiso que pide Capacitor.

## Pruebas
```bash
cd api && pytest                       # API: 35 pruebas (Gemini y Supabase simulados)
cd api && python -m scripts.diagnostico   # revisa tus claves reales de Supabase y Gemini (no las muestra)
cd api && python -m scripts.prueba_real foto.jpg   # punta a punta real con un usuario temporal (lo borra al final)
cd app && npx ng test --watch=false    # App: 14 pruebas unitarias
# Base de datos (Postgres local): stub de Supabase + migraciones + seed + pruebas de RLS
psql -f supabase/tests/00_stub_supabase.sql -f supabase/migrations/*.sql -f supabase/seed.sql -f supabase/seed_imagenes.sql -f supabase/tests/01_pruebas_rls.sql
# Punta a punta (requiere PostgREST y Chromium): ver pruebas/e2e/levantar.sh y prueba_e2e.py
```

## Claves: dónde va cada una
| Clave | Dónde | ¿Secreta? |
|---|---|---|
| URL de Supabase | `api/.env` y `app/src/environments/` | No |
| Clave `anon` / publishable de Supabase | `app/src/environments/` | No (la protege RLS) |
| Clave `service_role` / secret de Supabase | Solo `api/.env` o variables del servidor | **Sí** |
| `GEMINI_API_KEY` | Solo `api/.env` o variables del servidor | **Sí** |
