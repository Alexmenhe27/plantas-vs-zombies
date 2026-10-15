"""Validación de nombres con GBIF (simulado: no se llama al servicio real)."""
import asyncio

import httpx
import pytest
import respx

from app import taxonomia

GBIF = "https://api.gbif.org/v1"


@pytest.fixture(autouse=True)
def cache_vacia():
    taxonomia._cache.clear()


def coincidencia(**d):
    base = {"matchType": "EXACT", "confidence": 98, "rank": "SPECIES", "status": "ACCEPTED", "kingdom": "Animalia",
            "class": "Aves", "family": "Psittacidae", "usageKey": 5959230}
    return {**base, **d}


def validar(nombre, reino=None):
    async def correr():
        async with httpx.AsyncClient() as http:
            return await taxonomia.validar(http, nombre, reino)
    return asyncio.run(correr())


def test_normalizar_nombre():
    assert taxonomia.normalizar_nombre("  ara   MILITARIS ") == "Ara militaris"
    assert taxonomia.normalizar_nombre("canis LUPUS familiaris") == "Canis lupus familiaris"
    assert taxonomia.normalizar_nombre("") == ""


@respx.mock
def test_especie_aceptada():
    ruta = respx.get(f"{GBIF}/species/match").respond(200, json=coincidencia(canonicalName="Ara militaris"))
    t = validar("Ara militaris", "animal")
    assert t == taxonomia.Taxon("Ara militaris", 5959230, "Psittacidae", "animal", "ave")
    assert ruta.calls[0].request.url.params["kingdom"] == "Animalia"
    validar("Ara militaris", "animal")
    assert ruta.call_count == 1  # la segunda vez sale de la memoria


@respx.mock
def test_sinonimo_usa_el_nombre_aceptado_completo():
    """Canis familiaris es sinónimo de la subespecie doméstica, no del lobo."""
    respx.get(f"{GBIF}/species/match").respond(200, json=coincidencia(
        canonicalName="Canis familiaris", status="SYNONYM", acceptedUsageKey=6164210, species="Canis lupus",
        family="Canidae", **{"class": "Mammalia"}))
    respx.get(f"{GBIF}/species/6164210").respond(200, json={"canonicalName": "Canis lupus familiaris"})
    t = validar("Canis familiaris", "animal")
    assert t.nombre == "Canis lupus familiaris" and t.gbif_id == 6164210 and t.grupo == "mamifero"


@pytest.mark.parametrize("respuesta", [
    coincidencia(matchType="HIGHERRANK", rank="GENUS", canonicalName="Schistocerca"),
    {"matchType": "NONE", "confidence": 100},
    coincidencia(matchType="FUZZY", confidence=70, canonicalName="Parecido raro"),
])
@respx.mock
def test_no_es_especie(respuesta):
    respx.get(f"{GBIF}/species/match").respond(200, json=respuesta)
    assert validar("Schistocerca sp.") is None


@respx.mock
def test_reino_distinto_no_cuenta():
    respx.get(f"{GBIF}/species/match").respond(200, json=coincidencia(canonicalName="Morus alba", kingdom="Plantae"))
    assert validar("Morus alba", "animal") is None


@respx.mock
def test_grupo_de_plantas():
    respx.get(f"{GBIF}/species/match").respond(200, json=coincidencia(
        canonicalName="Opuntia ficus-indica", kingdom="Plantae", family="Cactaceae"))
    assert validar("Opuntia ficus-indica", "planta").grupo == "cactacea"


@respx.mock
def test_gbif_caido():
    respx.get(f"{GBIF}/species/match").mock(side_effect=httpx.ConnectError("sin red"))
    with pytest.raises(taxonomia.GBIFNoDisponible):
        validar("Ara militaris")


def test_grupo_de():
    assert taxonomia.grupo_de({"kingdom": "Animalia", "class": "Mammalia"}) == "mamifero"
    assert taxonomia.grupo_de({"kingdom": "Animalia", "class": "Arachnida"}) == "invertebrado"
    assert taxonomia.grupo_de({"kingdom": "Plantae", "genus": "Agave"}) == "agave"
    assert taxonomia.grupo_de({"kingdom": "Fungi"}) is None
