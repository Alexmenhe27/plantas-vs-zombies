"""Llamadas a Supabase (Auth, base de datos y Storage) con la clave de servicio."""
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


_JSON = {"Content-Type": "application/json"}
_DEVOLVER = {"Prefer": "return=representation", "Content-Type": "application/json"}
CAMPOS_ESPECIE = ("id,nombre_comun,nombre_cientifico,reino,grupo,familia,protegida,categoria_nom059,introducida,descripcion,"
                  "habitat,alimentacion,tamano,imagen_url,imagen_fuente,verificada,gbif_id")


class Supabase:
    def __init__(self, client: httpx.AsyncClient):
        self.http = client

    async def _pedir(self, metodo: str, url: str, **kwargs) -> httpx.Response:
        """Hace la petición; si Supabase no responde (red, DNS, tiempo agotado) lanza SupabaseError."""
        try:
            return await self.http.request(metodo, url, **kwargs)
        except httpx.HTTPError as e:
            raise SupabaseError(f"Supabase no responde: {e!r}") from e

    async def _rpc(self, funcion: str, parametros: dict):
        r = await self._pedir("POST", f"{settings.supabase_url}/rest/v1/rpc/{funcion}", json=parametros, headers=_headers(_JSON))
        if r.status_code not in (200, 204):
            raise SupabaseError(f"Falló {funcion}: {r.status_code} {r.text[:500]}")
        # Las funciones que no devuelven nada responden sin cuerpo (204).
        if r.status_code == 204 or not r.content.strip():
            return None
        try:
            return r.json()
        except ValueError as e:
            raise SupabaseError(f"Respuesta ilegible de {funcion}: {r.text[:200]}") from e

    # ------------------------------------------------------------------ Auth
    async def usuario_de_token(self, token: str) -> dict | None:
        """Pregunta a Supabase Auth de quién es el token (solo si no se pudo validar en la API). Devuelve el usuario o None."""
        r = await self._pedir("GET",
            f"{settings.supabase_url}/auth/v1/user",
            headers={"apikey": settings.supabase_service_key, "Authorization": f"Bearer {token}"},
        )
        if r.status_code != 200:
            return None
        return r.json()

    async def borrar_usuario(self, usuario_id: str) -> None:
        """Borra la cuenta. Su perfil y sus observaciones se borran en cascada en la base de datos."""
        r = await self._pedir("DELETE", f"{settings.supabase_url}/auth/v1/admin/users/{usuario_id}", headers=_headers())
        if r.status_code not in (200, 204, 404):
            raise SupabaseError(f"No se pudo borrar la cuenta: {r.status_code} {r.text[:300]}")

    # ------------------------------------------------------------------ Límite diario (tabla uso_ia)
    async def reservar(self, usuario_id: str, red: str | None) -> dict:
        """Reserva un lugar del límite diario ANTES de llamar a la IA (atómico en la base de datos)."""
        r = await self._rpc("reservar_identificacion", {"p_usuario": usuario_id, "p_red": red})
        # Los administradores no tienen límite: solo se pregunta su rol cuando ya no hay lugar.
        if isinstance(r, dict) and not r.get("ok") and r.get("motivo") in ("limite_diario", "limite_global") \
                and not r.get("invitado") and await self.es_admin(usuario_id):
            return {"ok": True, "reserva": None, "sin_limite": True, "limite": 9999, "restantes": 9999, "invitado": False}
        return r

    async def es_admin(self, usuario_id: str) -> bool:
        try:
            r = await self._pedir("GET", f"{settings.supabase_url}/rest/v1/perfiles",
                                  params={"select": "rol", "id": f"eq.{usuario_id}"}, headers=_headers())
            return r.status_code == 200 and any(f.get("rol") == "admin" for f in r.json())
        except Exception:  # si no se puede saber, se aplica el límite normal
            return False

    async def liberar(self, reserva: int) -> None:
        """Devuelve el lugar si la IA falló (no es culpa de la persona)."""
        await self._rpc("liberar_identificacion", {"p_reserva": reserva})

    async def guardar_identificacion(self, reserva: int | None, datos: dict) -> dict:
        """Busca o crea la especie, guarda la observación y marca el uso, en un solo viaje."""
        return await self._rpc("guardar_identificacion", {"p_reserva": reserva, "p_datos": datos})

    # ------------------------------------------------------------------ Especies
    async def especies_por_nombre(self, nombres: list[str]) -> dict[str, dict]:
        """Especies del catálogo con esos nombres científicos, indexadas por nombre."""
        if not nombres:
            return {}
        lista = ",".join('"' + n.replace('"', "") + '"' for n in nombres)
        r = await self._pedir("GET",
            f"{settings.supabase_url}/rest/v1/especies",
            params={"select": CAMPOS_ESPECIE, "nombre_cientifico": f"in.({lista})"},
            headers=_headers(),
        )
        if r.status_code != 200:
            raise SupabaseError(f"No se pudo consultar el catálogo: {r.status_code} {r.text}")
        return {e["nombre_cientifico"]: e for e in r.json()}

    async def crear_especie(self, fila: dict) -> dict:
        """Agrega una especie nueva al catálogo. Si otra petición la creó al mismo tiempo, devuelve esa."""
        r = await self._pedir("POST",
            f"{settings.supabase_url}/rest/v1/especies",
            params={"select": CAMPOS_ESPECIE},
            json=fila,
            headers=_headers(_DEVOLVER),
        )
        if r.status_code in (200, 201):
            return r.json()[0]
        if r.status_code == 409:
            existente = (await self.especies_por_nombre([fila["nombre_cientifico"]])).get(fila["nombre_cientifico"])
            if existente:
                return existente
        raise SupabaseError(f"No se pudo crear la especie: {r.status_code} {r.text}")

    async def completar_especie(self, especie_id: int, campos: dict) -> dict | None:
        """Escribe la ficha de una especie que todavía no tiene descripción. Devuelve la especie (o None si ya la tenía)."""
        r = await self._pedir("PATCH",
            f"{settings.supabase_url}/rest/v1/especies",
            params={"id": f"eq.{especie_id}", "descripcion": "is.null", "select": CAMPOS_ESPECIE},
            json=campos,
            headers=_headers(_DEVOLVER),
        )
        if r.status_code not in (200, 201):
            raise SupabaseError(f"No se pudo guardar la ficha: {r.status_code} {r.text}")
        filas = r.json()
        return filas[0] if filas else None

    async def poner_imagen(self, especie_id: int, url: str, fuente: str | None) -> None:
        r = await self._pedir("PATCH",
            f"{settings.supabase_url}/rest/v1/especies",
            params={"id": f"eq.{especie_id}", "imagen_url": "is.null"},
            json={"imagen_url": url, "imagen_fuente": fuente},
            headers=_headers(_JSON),
        )
        if r.status_code not in (200, 204):
            raise SupabaseError(f"No se pudo guardar la foto de la especie: {r.status_code} {r.text}")

    # ------------------------------------------------------------------ Observaciones
    async def observacion(self, observacion_id: str) -> dict | None:
        r = await self._pedir("GET",
            f"{settings.supabase_url}/rest/v1/observaciones",
            params={"select": "*", "id": f"eq.{observacion_id}"},
            headers=_headers(),
        )
        if r.status_code != 200:
            raise SupabaseError(f"No se pudo leer la observación: {r.status_code} {r.text}")
        filas = r.json()
        return filas[0] if filas else None

    async def actualizar_observacion(self, observacion_id: str, campos: dict) -> dict:
        r = await self._pedir("PATCH",
            f"{settings.supabase_url}/rest/v1/observaciones",
            params={"id": f"eq.{observacion_id}", "select": f"*,especie:especies({CAMPOS_ESPECIE})"},
            json=campos,
            headers=_headers(_DEVOLVER),
        )
        if r.status_code not in (200, 201) or not r.json():
            raise SupabaseError(f"No se pudo actualizar la observación: {r.status_code} {r.text}")
        return r.json()[0]

    # ------------------------------------------------------------------ Storage
    async def descargar_foto(self, path: str) -> tuple[bytes, str] | None:
        r = await self._pedir("GET", f"{settings.supabase_url}/storage/v1/object/{BUCKET}/{path}", headers=_headers())
        if r.status_code in (400, 404):
            return None
        if r.status_code != 200:
            raise SupabaseError(f"No se pudo descargar la foto: {r.status_code} {r.text}")
        tipo = r.headers.get("content-type", "image/jpeg").split(";")[0]
        return r.content, tipo

    async def fotos_de(self, usuario_id: str) -> list[str]:
        """Rutas de todas las fotos de una persona (para borrar su cuenta)."""
        rutas: list[str] = []
        while True:
            r = await self._pedir("POST",
                f"{settings.supabase_url}/storage/v1/object/list/{BUCKET}",
                json={"prefix": f"{usuario_id}/", "limit": 1000, "offset": len(rutas)},
                headers=_headers(_JSON),
            )
            if r.status_code != 200:
                raise SupabaseError(f"No se pudieron listar las fotos: {r.status_code} {r.text}")
            nombres = [f"{usuario_id}/{x['name']}" for x in r.json() if x.get("name")]
            rutas += nombres
            if len(nombres) < 1000:
                return rutas

    async def borrar_fotos(self, rutas: list[str]) -> None:
        for i in range(0, len(rutas), 500):
            r = await self._pedir("DELETE",
                f"{settings.supabase_url}/storage/v1/object/{BUCKET}",
                json={"prefixes": rutas[i:i + 500]},
                headers=_headers(_JSON),
            )
            if r.status_code not in (200, 204):
                raise SupabaseError(f"No se pudieron borrar las fotos: {r.status_code} {r.text}")
