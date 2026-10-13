"""Amplía el catálogo con especies registradas en Puebla según GBIF.

Genera un archivo SQL (insert ... on conflict do nothing) para revisar y aplicar en Supabase.
Las especies nuevas quedan sin descripción; se completan después desde el panel de admin.

Uso:
    python scripts/catalogo_gbif.py --limite 300 --salida ../supabase/catalogo_gbif.sql
"""
import argparse
import sys

import httpx

GBIF = "https://api.gbif.org/v1"

# Clases/reinos de GBIF -> (kingdom, grupo) de la app
GRUPOS = {
    "Aves": ("animal", "ave"),
    "Mammalia": ("animal", "mamifero"),
    "Squamata": ("animal", "reptil"),
    "Testudines": ("animal", "reptil"),
    "Amphibia": ("animal", "anfibio"),
    "Insecta": ("animal", "insecto"),
    "Actinopterygii": ("animal", "pez"),
}


def grupo_de(especie: dict) -> tuple[str, str] | None:
    if especie.get("kingdom") == "Plantae":
        familia = especie.get("family", "")
        if familia == "Cactaceae":
            return ("planta", "cactacea")
        if familia in ("Pinaceae", "Fagaceae", "Cupressaceae"):
            return ("planta", "arbol")
        return ("planta", "planta")
    for clave in (especie.get("class"), especie.get("order")):
        if clave in GRUPOS:
            return GRUPOS[clave]
    return None


def nombre_comun(http: httpx.Client, key: int) -> str | None:
    r = http.get(f"{GBIF}/species/{key}/vernacularNames", params={"limit": 50})
    r.raise_for_status()
    for n in r.json().get("results", []):
        if n.get("language") in ("spa", "es"):
            return n["vernacularName"].strip().capitalize()
    return None


def especies_de_puebla(http: httpx.Client, limite: int) -> list[dict]:
    r = http.get(
        f"{GBIF}/occurrence/search",
        params={"country": "MX", "stateProvince": "Puebla", "facet": "speciesKey", "speciesKey.facetLimit": limite, "limit": 0},
    )
    r.raise_for_status()
    facetas = r.json().get("facets", [])
    claves = [int(c["name"]) for f in facetas for c in f.get("counts", [])]
    salida = []
    for key in claves:
        d = http.get(f"{GBIF}/species/{key}")
        d.raise_for_status()
        especie = d.json()
        grupo = grupo_de(especie)
        nombre = nombre_comun(http, key)
        if not grupo or not nombre or not especie.get("canonicalName"):
            continue
        salida.append({
            "nombre_comun": nombre, "nombre_cientifico": especie["canonicalName"],
            "reino": grupo[0], "grupo": grupo[1], "familia": especie.get("family"),
        })
    return salida


def sql(texto: str | None) -> str:
    return "null" if texto is None else "'" + texto.replace("'", "''") + "'"


def a_sql(especies: list[dict]) -> str:
    filas = ",\n".join(
        f"({sql(e['nombre_comun'])}, {sql(e['nombre_cientifico'])}, {sql(e['reino'])}, {sql(e['grupo'])}, {sql(e['familia'])})"
        for e in especies
    )
    return (
        "-- Generado por api/scripts/catalogo_gbif.py. Revisar antes de aplicar.\n"
        "insert into public.especies (nombre_comun, nombre_cientifico, reino, grupo, familia) values\n"
        f"{filas}\non conflict (nombre_cientifico) do nothing;\n"
    )


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--limite", type=int, default=300)
    p.add_argument("--salida", default="catalogo_gbif.sql")
    args = p.parse_args()
    with httpx.Client(timeout=30) as http:
        especies = especies_de_puebla(http, args.limite)
    with open(args.salida, "w", encoding="utf-8") as fh:
        fh.write(a_sql(especies))
    print(f"{len(especies)} especies escritas en {args.salida}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
