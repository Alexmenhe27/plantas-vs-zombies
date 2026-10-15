"""Prueba de punta a punta contra tu Supabase y Claude reales, igual que lo hace la app.

Crea un usuario temporal, inicia sesión, sube una foto, llama a POST /identificar de la API
(que debe estar corriendo) y al final borra todo lo que creó. Gasta 1 identificación de Claude (menos de un centavo de dólar).

Uso (desde api/, con la API corriendo en otra terminal):
    python -m scripts.prueba_real ruta/a/foto.jpg [http://localhost:8000]
"""
import asyncio
import json
import re
import secrets
import sys
import time
from pathlib import Path

import httpx

from app.config import settings
from app.supabase_client import BUCKET, _headers

ENTORNO_APP = Path(__file__).resolve().parents[2] / "app" / "src" / "environments" / "environment.ts"


def clave_publica() -> str:
    """La clave pública (publishable/anon) es la misma que usa la app."""
    m = re.search(r"supabaseAnonKey:\s*'([^']+)'", ENTORNO_APP.read_text(encoding="utf-8"))
    if not m:
        raise SystemExit(f"No encontré supabaseAnonKey en {ENTORNO_APP}")
    return m.group(1)


async def main(foto: str, api: str) -> int:
    sb = settings.supabase_url
    publica = clave_publica()
    correo = f"prueba-{secrets.token_hex(4)}@ejemplo.com"
    contrasena = secrets.token_urlsafe(16)
    usuario_id = ruta = obs_id = especie_nueva = None
    async with httpx.AsyncClient(timeout=60) as http:
        try:
            r = await http.post(f"{sb}/auth/v1/admin/users", headers=_headers({"Content-Type": "application/json"}),
                                json={"email": correo, "password": contrasena, "email_confirm": True,
                                      "user_metadata": {"nombre_usuario": f"prueba_{secrets.token_hex(3)}"}})
            r.raise_for_status()
            usuario_id = r.json()["id"]
            print("1. Usuario temporal creado")

            r = await http.post(f"{sb}/auth/v1/token", params={"grant_type": "password"}, headers={"apikey": publica},
                                json={"email": correo, "password": contrasena})
            r.raise_for_status()
            token = r.json()["access_token"]
            print("2. Sesión iniciada con la clave pública (como la app)")

            ruta = f"{usuario_id}/{secrets.token_hex(8)}.jpg"
            r = await http.post(f"{sb}/storage/v1/object/{BUCKET}/{ruta}", content=Path(foto).read_bytes(),
                                headers={"apikey": publica, "Authorization": f"Bearer {token}", "Content-Type": "image/jpeg"})
            r.raise_for_status()
            print("3. Foto subida al bucket privado")

            inicio = time.monotonic()
            resultado, momentos = None, {}
            async with http.stream("POST", f"{api}/identificar", timeout=180,
                                   headers={"Authorization": f"Bearer {token}", "Origin": "http://localhost:4200",
                                            "Accept": "application/x-ndjson"},
                                   json={"ruta_foto": ruta, "latitud": 19.04, "longitud": -98.2}) as r:
                print(f"4. POST /identificar -> {r.status_code} (CORS: {r.headers.get('access-control-allow-origin')})")
                if r.status_code != 200:
                    print("   Respuesta:", (await r.aread()).decode()[:500])
                    return 1
                async for linea in r.aiter_lines():
                    if not linea.strip():
                        continue
                    evento = json.loads(linea)
                    ahora = time.monotonic() - inicio
                    if evento["tipo"] == "parcial" and evento.get("nombre_comun"):
                        momentos.setdefault("nombre visible", ahora)
                    elif evento["tipo"] == "resultado":
                        momentos["resultado guardado"], resultado = ahora, evento
                    elif evento["tipo"] == "ficha":
                        momentos["ficha de especie nueva"] = ahora
                    elif evento["tipo"] == "error":
                        print("   Error:", evento["mensaje"])
                        return 1
                    elif evento["tipo"] == "fin":
                        print("   Tiempos en la API (ms):", evento["tiempos"])
            print("   " + " · ".join(f"{k} a los {v:.1f} s" for k, v in momentos.items()))
            if not resultado:
                return 1
            obs = resultado["observacion"]
            obs_id = obs["id"]
            esp = obs.get("especie") or {}
            if esp and not esp.get("verificada", True):
                especie_nueva = esp["id"]
            print(f"   Estado: {obs['estado']} · {obs['ia_nombre_sugerido']} · confianza {obs['ia_confianza']}")
            print(f"   Restantes hoy: {resultado['restantes']} de {resultado['limite']}")

            r = await http.get(f"{sb}/rest/v1/observaciones", params={"select": "id", "id": f"eq.{obs_id}"},
                               headers={"apikey": publica, "Authorization": f"Bearer {token}"})
            print("5. La app puede leer la observación guardada:", "sí" if r.json() else "NO")
            return 0 if r.json() else 1
        finally:
            if obs_id:
                await http.delete(f"{sb}/rest/v1/observaciones", params={"id": f"eq.{obs_id}"}, headers=_headers())
            if especie_nueva:
                await http.delete(f"{sb}/rest/v1/especies", params={"id": f"eq.{especie_nueva}", "verificada": "is.false"},
                                  headers=_headers())
            if ruta:
                await http.request("DELETE", f"{sb}/storage/v1/object/{BUCKET}",
                                   headers=_headers({"Content-Type": "application/json"}), json={"prefixes": [ruta]})
            if usuario_id:
                await http.delete(f"{sb}/auth/v1/admin/users/{usuario_id}", headers=_headers())
            print("6. Limpieza: se borró el usuario temporal, su foto y su observación")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    sys.exit(asyncio.run(main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "http://localhost:8000")))
