import httpx
import respx

from scripts.catalogo_gbif import GBIF, a_sql, especies_de_puebla


@respx.mock
def test_genera_especies_y_sql():
    respx.get(f"{GBIF}/occurrence/search").respond(200, json={"facets": [{"counts": [{"name": "1"}, {"name": "2"}]}]})
    respx.get(f"{GBIF}/species/1").respond(200, json={"canonicalName": "Quiscalus mexicanus", "kingdom": "Animalia", "class": "Aves", "family": "Icteridae"})
    respx.get(f"{GBIF}/species/1/vernacularNames").respond(200, json={"results": [{"language": "spa", "vernacularName": "zanate mayor"}]})
    respx.get(f"{GBIF}/species/2").respond(200, json={"canonicalName": "Opuntia sp", "kingdom": "Plantae", "family": "Cactaceae"})
    respx.get(f"{GBIF}/species/2/vernacularNames").respond(200, json={"results": []})  # sin nombre en español: se omite
    with httpx.Client() as http:
        especies = especies_de_puebla(http, 10)
    assert especies == [{"nombre_comun": "Zanate mayor", "nombre_cientifico": "Quiscalus mexicanus", "reino": "animal", "grupo": "ave", "familia": "Icteridae"}]
    texto = a_sql(especies + [{"nombre_comun": "Pino d'prueba", "nombre_cientifico": "X y", "reino": "planta", "grupo": "arbol", "familia": None}])
    assert "'Pino d''prueba'" in texto and "on conflict (nombre_cientifico) do nothing" in texto
