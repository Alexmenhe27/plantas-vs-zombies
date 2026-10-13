"""Revisa que la API pueda hablar con Supabase y con Gemini. Nunca muestra las claves.

Uso (desde la carpeta api/, con el entorno activado):
    python -m scripts.diagnostico
    python -m scripts.diagnostico ruta/a/una/foto.jpg     # además prueba con una foto real
"""
import asyncio
import base64
import logging
import sys
import time

import httpx

from app import ia
from app.config import settings
from app.supabase_client import BUCKET, _headers

# JPEG de 1x1 px: basta para comprobar que el modelo acepta imágenes.
JPEG_MINIMO = base64.b64decode(
    "/9j/4AAQSkZJRgABAQEASABIAAD/2wBDAP//////////////////////////////////////////////////////////////////////////////////////"
    "2wBDAf//////////////////////////////////////////////////////////////////////////////////////wAARCAABAAEDASIAAhEBAxEB/8QAFAAB"
    "AAAAAAAAAAAAAAAAAAAACv/EABQQAQAAAAAAAAAAAAAAAAAAAAD/xAAUAQEAAAAAAAAAAAAAAAAAAAAA/8QAFBEBAAAAAAAAAAAAAAAAAAAAAP/aAAwDAQAC"
    "EQMRAD8AAH//2Q=="
)


def ok(texto: str) -> None:
    print(f"  [OK]    {texto}")


def mal(texto: str) -> None:
    print(f"  [FALLA] {texto}")


async def revisar_supabase(http: httpx.AsyncClient) -> bool:
    print("\nSupabase")
    try:
        r = await http.get(f"{settings.supabase_url}/rest/v1/especies", params={"select": "id", "limit": "1"}, headers=_headers())
    except httpx.HTTPError as e:
        mal(f"No responde ({settings.supabase_url}): {e!r}")
        return False
    if r.status_code != 200:
        mal(f"La clave SUPABASE_SERVICE_KEY no funciona: {r.status_code} {r.text[:200]}")
        return False
    ok("Base de datos: conecta y la clave secreta es válida")
    r = await http.get(f"{settings.supabase_url}/storage/v1/bucket/{BUCKET}", headers=_headers())
    if r.status_code != 200:
        mal(f'No se encontró el bucket "{BUCKET}": {r.status_code} {r.text[:200]}')
        return False
    ok(f'Storage: existe el bucket "{BUCKET}"')
    return True


async def revisar_gemini(http: httpx.AsyncClient, foto: str | None) -> bool:
    print("\nGemini")
    r = await http.get(
        f"{settings.ia_url}/v1beta/models", params={"pageSize": 1000}, headers={"x-goog-api-key": settings.gemini_api_key}
    )
    if r.status_code != 200:
        mal(f"La clave GEMINI_API_KEY no funciona: {r.status_code} {r.text[:300]}")
        return False
    disponibles = sorted(
        m["name"].removeprefix("models/")
        for m in r.json().get("models", [])
        if "generateContent" in m.get("supportedGenerationMethods", []) and "gemini" in m["name"]
    )
    ok(f"La clave es válida ({len(disponibles)} modelos Gemini disponibles)")
    modelos = ia.modelos_a_probar()
    print("  Modelos que usará la API, en orden:", ", ".join(modelos))
    for m in modelos:
        print(f"    {'sí' if m in disponibles else 'NO'} disponible: {m}")

    inicio = time.monotonic()
    try:
        resultado = await ia.identificar(JPEG_MINIMO, "image/jpeg")
    except ia.IAError as e:
        mal(f"Identificación de prueba: {e}\n          Detalle: {e.detalle}")
        print("  Modelos con generateContent:", ", ".join(disponibles))
        return False
    ok(f"Identificación de prueba en {time.monotonic() - inicio:.1f} s (respuesta: problema={resultado.problema})")
    if foto:
        with open(foto, "rb") as fh:
            datos = fh.read()
        inicio = time.monotonic()
        try:
            resultado = await ia.identificar(datos, "image/png" if foto.lower().endswith(".png") else "image/jpeg")
        except ia.IAError as e:
            mal(f"Foto real: {e}\n          Detalle: {e.detalle}")
            return False
        nombre = f"{resultado.especie.nombre_comun} ({resultado.especie.nombre_cientifico})" if resultado.especie else resultado.problema
        ok(f"Foto real en {time.monotonic() - inicio:.1f} s: {nombre}, confianza {resultado.confianza:.2f}")
    return True


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="          %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    faltan = settings.faltantes()
    if faltan:
        mal("Faltan en api/.env: " + ", ".join(faltan))
        return
    async with httpx.AsyncClient(timeout=30) as http:
        sb = await revisar_supabase(http)
        gm = await revisar_gemini(http, sys.argv[1] if len(sys.argv) > 1 else None)
    print("\nTodo listo: la API puede identificar fotos." if sb and gm else "\nHay problemas: corrige lo marcado con [FALLA].")


if __name__ == "__main__":
    asyncio.run(main())
