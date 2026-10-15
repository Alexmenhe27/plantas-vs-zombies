"""Validación de la sesión (el JWT de Supabase) dentro de la API, sin preguntarle a Supabase en cada foto.

Supabase firma las sesiones con una clave asimétrica (ES256) y publica la clave pública en
/auth/v1/.well-known/jwks.json. La API la descarga una vez (y cada 10 minutos) y comprueba la firma, la fecha
de vencimiento, la audiencia y el emisor. Si el proyecto todavía usa la clave secreta anterior (HS256),
se pregunta a Supabase como antes.
"""
import asyncio
import logging
import time
from dataclasses import dataclass

import httpx
import jwt

from .config import settings
from .supabase_client import Supabase

log = logging.getLogger("api")
ALGORITMOS_PUBLICOS = ("ES256", "RS256", "EdDSA")


@dataclass(frozen=True)
class Usuario:
    id: str
    es_invitado: bool = False
    email: str | None = None


class ValidadorSesion:
    def __init__(self, sb: Supabase):
        self.sb = sb
        self._claves: dict[str | None, jwt.PyJWK] = {}
        self._cargadas_en = 0.0
        self._candado = asyncio.Lock()

    async def _cargar_claves(self, forzar: bool = False) -> None:
        vigentes = self._claves and time.monotonic() - self._cargadas_en < 600
        if vigentes and not forzar:
            return
        async with self._candado:
            # Una clave desconocida obliga a recargar, pero no más de una vez cada 30 s.
            if self._cargadas_en and time.monotonic() - self._cargadas_en < (30 if forzar else 600):
                return
            try:
                r = await self.sb.http.get(f"{settings.supabase_url}/auth/v1/.well-known/jwks.json", timeout=5)
                datos = r.json() if r.status_code == 200 else {}
            except (httpx.HTTPError, ValueError) as e:
                log.info("No se pudieron leer las claves públicas de Supabase: %r", e)
                datos = {}
            claves = {}
            for k in datos.get("keys", []) if isinstance(datos, dict) else []:
                try:
                    claves[k.get("kid")] = jwt.PyJWK(k)
                except (jwt.PyJWTError, ValueError, TypeError):
                    continue
            self._claves = claves
            self._cargadas_en = time.monotonic()

    async def validar(self, token: str) -> Usuario | None:
        """El usuario de la sesión, o None si el token no es válido o ya venció."""
        try:
            cabecera = jwt.get_unverified_header(token)
        except jwt.PyJWTError:
            return None
        alg, kid = cabecera.get("alg"), cabecera.get("kid")
        if alg in ALGORITMOS_PUBLICOS:
            await self._cargar_claves()
            if kid not in self._claves:
                await self._cargar_claves(forzar=True)
            clave = self._claves.get(kid)
            if clave is not None:
                try:
                    datos = jwt.decode(
                        token, clave.key, algorithms=[alg], audience="authenticated",
                        issuer=f"{settings.supabase_url}/auth/v1", leeway=30, options={"require": ["exp", "sub"]},
                    )
                except jwt.PyJWTError:
                    return None
                if datos.get("role") != "authenticated":
                    return None
                return Usuario(str(datos["sub"]), bool(datos.get("is_anonymous")), datos.get("email"))
        # Clave secreta anterior (HS256) o sin claves públicas: se pregunta a Supabase.
        usuario = await self.sb.usuario_de_token(token)
        if not usuario or not usuario.get("id"):
            return None
        return Usuario(str(usuario["id"]), bool(usuario.get("is_anonymous")), usuario.get("email"))
