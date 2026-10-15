"""Revisa que la API pueda hablar con Supabase y con Claude. Nunca muestra las claves completas.

Uso (desde la carpeta api/, con el entorno activado):
    python -m scripts.diagnostico
    python -m scripts.diagnostico ruta/a/una/foto.jpg     # además prueba con una foto real
"""
import asyncio
import logging
import sys
import struct
import time
import zlib
from pathlib import Path

import httpx

from app import ia
from app.config import settings
from app.supabase_client import BUCKET, _headers

def imagen_de_prueba() -> bytes:
    """PNG de 256x256 (un degradado) hecha aquí mismo. Una imagen de 1x1 px Claude la rechaza ("Could not process image")."""
    lado = 256
    filas = b"".join(b"\x00" + bytes(v for x in range(lado) for v in (x, y, 120)) for y in range(lado))

    def bloque(tipo: bytes, datos: bytes) -> bytes:
        return struct.pack(">I", len(datos)) + tipo + datos + struct.pack(">I", zlib.crc32(tipo + datos))

    cabecera = struct.pack(">IIBBBBB", lado, lado, 8, 2, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + bloque(b"IHDR", cabecera) + bloque(b"IDAT", zlib.compress(filas)) + bloque(b"IEND", b"")


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
    r = await http.get(f"{settings.supabase_url}/rest/v1/ajustes", params={"select": "clave,valor"}, headers=_headers())
    if r.status_code != 200:
        mal("Falta aplicar en Supabase la migración 20261014000005_rendimiento_seguridad_privacidad.sql "
            "(ver COMO_EJECUTAR.md, paso 1).")
        return False
    ajustes = {a["clave"]: a["valor"] for a in r.json()}
    ok(f"Migración aplicada. Límite diario: {ajustes.get('limite_diario')} (invitados: {ajustes.get('limite_diario_invitado')}), "
       f"tope global: {ajustes.get('limite_global_diario')} al día")
    r = await http.get(f"{settings.supabase_url}/auth/v1/.well-known/jwks.json")
    claves = r.json().get("keys", []) if r.status_code == 200 else []
    if claves:
        ok(f"Sesiones: la API las valida sola con la clave pública de Supabase ({claves[0].get('alg')}), sin consultas extra")
    else:
        print("  [AVISO] Tu proyecto usa la clave secreta anterior: la API preguntará a Supabase en cada foto (funciona, pero es más lento).")
    return True


async def revisar_gbif(http: httpx.AsyncClient) -> bool:
    print("\nGBIF (validación de especies nuevas)")
    if not settings.gbif_url:
        print("  [AVISO] GBIF_URL está vacío: las especies nuevas se agregarán sin validar.")
        return True
    try:
        r = await http.get(f"{settings.gbif_url}/species/match", params={"name": "Ara militaris"}, timeout=10)
        r.raise_for_status()
    except httpx.HTTPError as e:
        print(f"  [AVISO] GBIF no responde ({e!r}). La app funciona igual, pero las especies nuevas se agregarán sin validar.")
        return True
    ok("GBIF responde: los nombres de especies nuevas se validan antes de entrar al catálogo")
    return True


async def revisar_claude(foto: str | None) -> bool:
    print("\nClaude")
    k = settings.anthropic_api_key
    print(f"  Clave cargada: empieza con {k[:10]}… y mide {len(k)} caracteres (una clave completa mide unos 100).")
    print(f"  Modelo: {settings.ia_modelo} · razonamiento: {settings.ia_razonamiento}"
          + (f" · espacio de trabajo: {settings.anthropic_workspace_id}" if settings.anthropic_workspace_id else ""))
    inicio = time.monotonic()
    try:
        resultado = await ia.identificar(imagen_de_prueba(), "image/png")
    except ia.IAError as e:
        mal(f"Identificación de prueba: {e}\n          Detalle: {e.detalle}")
        return False
    ok(f"La clave funciona. Identificación de prueba en {time.monotonic() - inicio:.1f} s (respuesta: problema={resultado.problema})")
    if foto:
        if not Path(foto).is_file():
            mal(f"No encontré la foto {foto}. Escribe la ruta de una foto que exista en tu computadora.")
            return False
        datos = Path(foto).read_bytes()
        inicio, visto = time.monotonic(), {}

        async def al_avanzar(campos: dict) -> None:
            if campos.get("nombre_comun"):
                visto.setdefault("nombre", time.monotonic() - inicio)

        try:
            resultado = await ia.identificar(datos, "image/png" if foto.lower().endswith(".png") else "image/jpeg",
                                             al_avanzar=al_avanzar)
        except ia.IAError as e:
            mal(f"Foto real: {e}\n          Detalle: {e.detalle}")
            return False
        nombre = f"{resultado.nombre_comun} ({resultado.nombre_cientifico})" if resultado.tiene_especie else resultado.problema
        total = time.monotonic() - inicio
        ok(f"Foto real: {nombre}, confianza {resultado.confianza:.2f}. "
           f"El nombre apareció a los {visto.get('nombre', total):.1f} s y la respuesta completa a los {total:.1f} s")
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
        await revisar_gbif(http)
        ia_ok = await revisar_claude(sys.argv[1] if len(sys.argv) > 1 else None)
    print("\nTodo listo: la API puede identificar fotos." if sb and ia_ok else "\nHay problemas: corrige lo marcado con [FALLA].")


if __name__ == "__main__":
    asyncio.run(main())
