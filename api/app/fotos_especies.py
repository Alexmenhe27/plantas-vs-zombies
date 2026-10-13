"""Foto de referencia para una especie nueva, tomada de Wikipedia (gratis y sin clave).

Se busca solo una vez, cuando la especie entra al catálogo, y en segundo plano: no retrasa la respuesta.
"""
import logging
import re
from urllib.parse import quote

import httpx

log = logging.getLogger("api")
CABECERAS = {"User-Agent": "IdentificaEspecies/1.0 (app educativa de identificacion de especies)"}


def _mas_grande(url: str, ancho_original: int | None) -> str:
    """Las miniaturas de Wikipedia vienen a 320 px; se pide una de 640 px si la original es así de grande."""
    if ancho_original and ancho_original >= 640:
        return re.sub(r"/\d+px-([^/]+)$", r"/640px-\1", url)
    return url


def fuente_de(url: str) -> str | None:
    """Página del archivo en Wikimedia Commons (para dar crédito)."""
    m = re.search(r"/commons/(?:thumb/)?[0-9a-f]/[0-9a-f]{2}/([^/]+)", url)
    return f"https://commons.wikimedia.org/wiki/File:{m.group(1)}" if m else None


async def buscar_foto(http: httpx.AsyncClient, nombre_cientifico: str) -> tuple[str, str | None] | None:
    titulo = quote(nombre_cientifico.replace(" ", "_"))
    for idioma in ("es", "en"):
        try:
            r = await http.get(
                f"https://{idioma}.wikipedia.org/api/rest_v1/page/summary/{titulo}",
                headers=CABECERAS, timeout=6, follow_redirects=True,
            )
        except httpx.HTTPError as e:
            log.info("Wikipedia no respondió para %s: %r", nombre_cientifico, e)
            return None
        if r.status_code != 200:
            continue
        datos = r.json()
        mini = (datos.get("thumbnail") or {}).get("source")
        if mini and "/commons/" in mini:  # solo fotos con licencia libre de Commons
            url = _mas_grande(mini, (datos.get("originalimage") or {}).get("width"))
            return url, fuente_de(url)
    return None
