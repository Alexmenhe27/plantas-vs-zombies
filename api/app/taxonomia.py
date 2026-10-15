"""Nombres científicos: normalización y validación con GBIF (gratis y sin clave).

Antes de agregar una especie nueva al catálogo se comprueba en GBIF que exista. Así no entran nombres inventados
ni duplicados por sinónimos: si la IA usa un nombre antiguo (Felis concolor), se guarda el aceptado (Puma concolor).
Las formas domésticas se respetan (Canis familiaris -> Canis lupus familiaris, no el lobo).
"""
import logging
import re
from collections import OrderedDict
from dataclasses import dataclass

import httpx

from .config import settings

log = logging.getLogger("api")

RANGOS_DE_ESPECIE = {"SPECIES", "SUBSPECIES", "VARIETY", "FORM"}
REINOS = {"Animalia": "animal", "Plantae": "planta"}
CABECERAS = {"User-Agent": "IdentificaEspecies/1.0 (app educativa de identificacion de especies)"}


@dataclass(frozen=True)
class Taxon:
    nombre: str          # nombre aceptado en GBIF
    gbif_id: int | None
    familia: str | None
    reino: str | None    # "animal", "planta" o None
    grupo: str | None = None  # grupo de la app deducido de la clasificación (ave, mamifero, cactacea...)


_GRUPO_POR_CLASE = {
    "Aves": "ave", "Mammalia": "mamifero", "Reptilia": "reptil", "Squamata": "reptil", "Testudines": "reptil",
    "Crocodylia": "reptil", "Amphibia": "anfibio", "Insecta": "insecto", "Actinopterygii": "pez", "Elasmobranchii": "pez",
}


def grupo_de(d: dict) -> str | None:
    """Grupo de la app según la clasificación de GBIF (para especies elegidas que no traen grupo)."""
    if d.get("kingdom") == "Plantae":
        if d.get("family") == "Cactaceae":
            return "cactacea"
        if d.get("genus") == "Agave":
            return "agave"
        if d.get("family") == "Arecaceae":
            return "palma"
        if d.get("class") == "Polypodiopsida":
            return "helecho"
        return "planta"
    if d.get("kingdom") == "Animalia":
        return _GRUPO_POR_CLASE.get(d.get("class")) or _GRUPO_POR_CLASE.get(d.get("order")) or "invertebrado"
    return None


class GBIFNoDisponible(Exception):
    """GBIF no respondió a tiempo: la especie se agrega sin validar (como antes de existir esta validación)."""


def normalizar_nombre(nombre: str) -> str:
    """'ara  MILITARIS' -> 'Ara militaris' (para no duplicar especies por mayúsculas o espacios)."""
    partes = re.sub(r"\s+", " ", (nombre or "").strip()).split(" ")
    if not partes or not partes[0]:
        return ""
    return " ".join([partes[0].capitalize()] + [p.lower() for p in partes[1:]])


_cache: "OrderedDict[tuple[str, str | None], Taxon | None]" = OrderedDict()
_CACHE_MAXIMO = 2000


async def validar(http: httpx.AsyncClient, nombre: str, reino: str | None = None) -> Taxon | None:
    """Taxon aceptado si GBIF reconoce el nombre como especie (o subespecie); None si no (un género, un nombre inventado)."""
    if not settings.gbif_url:
        raise GBIFNoDisponible("validación desactivada (GBIF_URL vacío)")
    clave = (nombre, reino)
    if clave in _cache:
        _cache.move_to_end(clave)
        return _cache[clave]
    parametros = {"name": nombre}
    if reino in ("animal", "planta"):
        parametros["kingdom"] = "Animalia" if reino == "animal" else "Plantae"
    try:
        r = await http.get(f"{settings.gbif_url}/species/match", params=parametros, headers=CABECERAS,
                           timeout=settings.gbif_tiempo_maximo)
        r.raise_for_status()
        d = r.json()
        resultado = None
        if (d.get("matchType") in ("EXACT", "FUZZY") and (d.get("confidence") or 0) >= 90
                and d.get("rank") in RANGOS_DE_ESPECIE):
            aceptado, gbif_id = d.get("canonicalName"), d.get("usageKey")
            if d.get("status") not in ("ACCEPTED", "DOUBTFUL") and d.get("acceptedUsageKey"):
                # Sinónimo: se usa el nombre aceptado completo (en una subespecie, también la subespecie).
                a = await http.get(f"{settings.gbif_url}/species/{d['acceptedUsageKey']}", headers=CABECERAS,
                                   timeout=settings.gbif_tiempo_maximo)
                a.raise_for_status()
                aceptado, gbif_id = a.json().get("canonicalName") or d.get("species"), d["acceptedUsageKey"]
            reino_gbif = REINOS.get(d.get("kingdom"))
            if aceptado and (reino is None or reino_gbif is None or reino_gbif == reino):
                resultado = Taxon(normalizar_nombre(aceptado), gbif_id, d.get("family"), reino_gbif, grupo_de(d))
    except (httpx.HTTPError, ValueError) as e:
        raise GBIFNoDisponible(repr(e)) from e
    _cache[clave] = resultado
    while len(_cache) > _CACHE_MAXIMO:
        _cache.popitem(last=False)
    return resultado
