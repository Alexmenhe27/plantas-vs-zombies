"""Foto de referencia para una especie nueva: de Wikipedia (Wikimedia Commons) y, si no hay, de iNaturalist.

Ambas son gratis y sin clave, y solo se usan fotos con licencia libre. Se busca una sola vez, cuando la especie
entra al catálogo, y en segundo plano: no retrasa la respuesta.
"""
import logging
import re
from urllib.parse import quote

import httpx

log = logging.getLogger("api")
CABECERAS = {"User-Agent": "IdentificaEspecies/1.0 (app educativa de identificacion de especies)"}
# Licencias de iNaturalist que permiten reutilizar la foto (con crédito).
LICENCIAS_LIBRES = {"cc0", "cc-by", "cc-by-sa"}


def _mas_grande(url: str, ancho_original: int | None) -> str:
    """Las miniaturas de Wikipedia vienen a 320 px; se pide una de 640 px si la original es así de grande."""
    if ancho_original and ancho_original >= 640:
        return re.sub(r"/\d+px-([^/]+)$", r"/640px-\1", url)
    return url


def fuente_de(url: str) -> str | None:
    """Página del archivo en Wikimedia Commons (para dar crédito)."""
    m = re.search(r"/commons/(?:thumb/)?[0-9a-f]/[0-9a-f]{2}/([^/]+)", url)
    return f"https://commons.wikimedia.org/wiki/File:{m.group(1)}" if m else None


async def _wikipedia(http: httpx.AsyncClient, nombre_cientifico: str) -> tuple[str, str | None] | None:
    titulo = quote(nombre_cientifico.replace(" ", "_"))
    for idioma in ("es", "en"):
        r = await http.get(
            f"https://{idioma}.wikipedia.org/api/rest_v1/page/summary/{titulo}",
            headers=CABECERAS, timeout=6, follow_redirects=True,
        )
        if r.status_code != 200:
            continue
        datos = r.json()
        mini = (datos.get("thumbnail") or {}).get("source")
        if mini and "/commons/" in mini:  # solo fotos con licencia libre de Commons
            url = _mas_grande(mini, (datos.get("originalimage") or {}).get("width"))
            return url, fuente_de(url)
    return None


async def _inaturalist(http: httpx.AsyncClient, nombre_cientifico: str) -> tuple[str, str | None] | None:
    r = await http.get(
        "https://api.inaturalist.org/v1/taxa",
        params={"q": nombre_cientifico, "is_active": "true", "per_page": 3},
        headers=CABECERAS, timeout=6,
    )
    if r.status_code != 200:
        return None
    for taxon in r.json().get("results", []):
        foto = taxon.get("default_photo") or {}
        if taxon.get("name") == nombre_cientifico and foto.get("license_code") in LICENCIAS_LIBRES and foto.get("medium_url"):
            return foto["medium_url"], f"https://www.inaturalist.org/photos/{foto['id']}"
    return None


async def buscar_foto(http: httpx.AsyncClient, nombre_cientifico: str) -> tuple[str, str | None] | None:
    for buscar in (_wikipedia, _inaturalist):
        try:
            foto = await buscar(http, nombre_cientifico)
        except (httpx.HTTPError, ValueError) as e:
            log.info("No se pudo consultar %s para %s: %r", buscar.__name__.strip("_"), nombre_cientifico, e)
            continue
        if foto:
            return foto
    return None
