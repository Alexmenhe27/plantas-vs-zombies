"""Llamadas a Supabase (Auth, base de datos y Storage) con la clave de servicio."""
from datetime import datetime, timedelta, timezone

import httpx

from .config import settings

BUCKET = "fotos"


class SupabaseError(Exception):
    pass


def _headers(extra: dict | None = None) -> dict:
    clave = settings.supabase_service_key
    h = {"apikey": clave}
    # Las claves nuevas de Supabase ("sb_secret_...") no son JWT: van solo en "apikey".
    # Las claves antiguas (service_role, un JWT) también van en "Authorization".
    if not clave.startswith("sb_"):
        h["Authorization"] = f"Bearer {clave}"
    if extra:
        h.update(extra)
    return h


class Supabase:
    def __init__(self, client: httpx.AsyncClient):
        self.http = client

    async def _pedir(self, metodo: str, url: str, **kwargs) -> httpx.Response:
        """Hace la petición; si Supabase no responde (red, DNS, tiempo agotado) lanza SupabaseError."""
        try:
            return await self.http.request(metodo, url, **kwargs)
        except httpx.HTTPError as e:
            raise SupabaseError(f"Supabase no responde: {e!r}") from e

    async def usuario_de_token(self, token: str) -> dict | None:
        """Valida el JWT del usuario preguntando a Supabase Auth. Devuelve el usuario o None."""
        r = await self._pedir("GET", 
            f"{settings.supabase_url}/auth/v1/user",
            headers={"apikey": settings.supabase_service_key, "Authorization": f"Bearer {token}"},
        )
        if r.status_code != 200:
            return None
        return r.json()

    async def uso_ultimas_24h(self, usuario_id: str) -> list[datetime]:
        """Fechas de las observaciones del usuario en las últimas 24 horas (la más antigua primero)."""
        desde = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
        r = await self._pedir("GET", 
            f"{settings.supabase_url}/rest/v1/observaciones",
            params={"select": "creado_en", "usuario_id": f"eq.{usuario_id}", "creado_en": f"gt.{desde}", "order": "creado_en.asc"},
            headers=_headers(),
        )
        if r.status_code != 200:
            raise SupabaseError(f"No se pudo consultar el uso: {r.status_code} {r.text}")
        return [datetime.fromisoformat(row["creado_en"]) for row in r.json()]

    async def especies_por_nombre(self, nombres: list[str]) -> dict[str, dict]:
        """Especies del catálogo con esos nombres científicos, indexadas por nombre."""
        if not nombres:
            return {}
        lista = ",".join('"' + n.replace('"', "") + '"' for n in nombres)
        r = await self._pedir("GET",
            f"{settings.supabase_url}/rest/v1/especies",
            params={"select": "id,nombre_comun,nombre_cientifico", "nombre_cientifico": f"in.({lista})"},
            headers=_headers(),
        )
        if r.status_code != 200:
            raise SupabaseError(f"No se pudo consultar el catálogo: {r.status_code} {r.text}")
        return {e["nombre_cientifico"]: e for e in r.json()}

    async def crear_especie(self, fila: dict) -> dict:
        """Agrega una especie nueva al catálogo. Si otra petición la creó al mismo tiempo, devuelve esa."""
        r = await self._pedir("POST",
            f"{settings.supabase_url}/rest/v1/especies",
            params={"select": "id,nombre_comun,nombre_cientifico"},
            json=fila,
            headers=_headers({"Prefer": "return=representation", "Content-Type": "application/json"}),
        )
        if r.status_code in (200, 201):
            return r.json()[0]
        if r.status_code == 409:
            existente = (await self.especies_por_nombre([fila["nombre_cientifico"]])).get(fila["nombre_cientifico"])
            if existente:
                return existente
        raise SupabaseError(f"No se pudo crear la especie: {r.status_code} {r.text}")

    async def poner_imagen(self, especie_id: int, url: str, fuente: str | None) -> None:
        r = await self._pedir("PATCH",
            f"{settings.supabase_url}/rest/v1/especies",
            params={"id": f"eq.{especie_id}", "imagen_url": "is.null"},
            json={"imagen_url": url, "imagen_fuente": fuente},
            headers=_headers({"Content-Type": "application/json"}),
        )
        if r.status_code not in (200, 204):
            raise SupabaseError(f"No se pudo guardar la foto de la especie: {r.status_code} {r.text}")

    async def descargar_foto(self, path: str) -> tuple[bytes, str] | None:
        r = await self._pedir("GET", f"{settings.supabase_url}/storage/v1/object/{BUCKET}/{path}", headers=_headers())
        if r.status_code in (400, 404):
            return None
        if r.status_code != 200:
            raise SupabaseError(f"No se pudo descargar la foto: {r.status_code} {r.text}")
        tipo = r.headers.get("content-type", "image/jpeg").split(";")[0]
        return r.content, tipo

    async def guardar_observacion(self, fila: dict) -> dict:
        r = await self._pedir("POST", 
            f"{settings.supabase_url}/rest/v1/observaciones",
            params={"select": "*,especie:especies(*)"},
            json=fila,
            headers=_headers({"Prefer": "return=representation", "Content-Type": "application/json"}),
        )
        if r.status_code not in (200, 201):
            raise SupabaseError(f"No se pudo guardar la observación: {r.status_code} {r.text}")
        return r.json()[0]
