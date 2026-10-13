#!/usr/bin/env bash
# Levanta todo el sistema en local para las pruebas de punta a punta:
# Postgres (ya corriendo en :54329) -> PostgREST :3001 -> mini Supabase :54321
# Gemini falso :54400 -> API Python :8000 -> app Angular :8100
set -euo pipefail
AQUI="$(cd "$(dirname "$0")" && pwd)"
RAIZ="$(cd "$AQUI/../.." && pwd)"
PY="${E2E_PY:-python}"
LOGS="${E2E_LOGS:-/tmp/app-e2e}"
mkdir -p "$LOGS"

P="psql -h /tmp -p 54329 -U postgres -v ON_ERROR_STOP=1 -q"
$P -c "drop database if exists app_e2e" -c "create database app_e2e"
$P -d app_e2e -f "$RAIZ/supabase/tests/00_stub_supabase.sql"
for m in "$RAIZ"/supabase/migrations/*.sql; do $P -d app_e2e -f "$m"; done
$P -d app_e2e -f "$RAIZ/supabase/seed.sql"
$P -d app_e2e -f "$RAIZ/supabase/seed_imagenes.sql"

SERVICE_KEY=$($PY "$AQUI/mini_supabase.py" | grep SERVICE_KEY | cut -d= -f2)

"${POSTGREST_BIN:-postgrest}" "$AQUI/postgrest.conf" > "$LOGS/postgrest.log" 2>&1 &
(cd "$AQUI" && $PY -m uvicorn mini_supabase:app --port 54321 > "$LOGS/supabase.log" 2>&1 &)
(cd "$AQUI" && $PY -m uvicorn fake_ia:app --port 54400 > "$LOGS/ia.log" 2>&1 &)
(cd "$RAIZ/api" && SUPABASE_URL=http://127.0.0.1:54321 SUPABASE_SERVICE_KEY="$SERVICE_KEY" \
  GEMINI_API_KEY=clave-falsa IA_URL=http://127.0.0.1:54400 \
  "${API_PY:-python}" -m uvicorn app.main:app --port 8000 > "$LOGS/api.log" 2>&1 &)
(cd "$RAIZ/app" && npx ng serve --configuration e2e --port 8100 > "$LOGS/app.log" 2>&1 &)
echo "Levantando… logs en $LOGS"
