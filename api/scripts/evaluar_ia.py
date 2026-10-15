"""Mide la precisión y la velocidad de la IA con fotos reales de especies conocidas (de iNaturalist, con licencia libre).

Sirve para comprobar que un cambio en la IA (instrucciones, modelo, razonamiento) no baja la precisión.
Cada corrida gasta unas 40 identificaciones de Claude Haiku (unos 3 centavos de dólar); el script lo calcula y lo muestra.

Uso (desde api/, con el entorno activado):
    python -m scripts.evaluar_ia armar            # arma el set de fotos (gratis, solo iNaturalist)
    python -m scripts.evaluar_ia correr [nombre] [sin|bajo]  # identifica todas las fotos (razonamiento: sin o bajo)
    python -m scripts.evaluar_ia comparar a b     # compara dos corridas

Las fotos se descargan a scripts/evaluacion/fotos/ (no se suben a git: cada una tiene su propia licencia y autor,
que quedan anotados en scripts/evaluacion/set.json).
"""
import asyncio
import json
import statistics
import sys
import time
from pathlib import Path

import httpx

CARPETA = Path(__file__).parent / "evaluacion"
SET = CARPETA / "set.json"
FOTOS = CARPETA / "fotos"
CORRIDAS = CARPETA / "corridas"

# Precio de Claude Haiku 5.5 (dólares por millón de tokens), para estimar el gasto de cada corrida.
PRECIO_ENTRADA, PRECIO_SALIDA = 0.10, 0.50
PRECIO_CACHE_LECTURA, PRECIO_CACHE_ESCRITURA = 0.01, 0.125

# 30 especies del catálogo (todos los grupos) y 8 que no están en él (prueban el alta de especies nuevas).
DEL_CATALOGO = [
    "Quiscalus mexicanus", "Pyrocephalus rubinus", "Haemorhous mexicanus", "Columbina inca", "Melanotis caerulescens",
    "Buteo jamaicensis", "Cynanthus latirostris",
    "Bassariscus astutus", "Didelphis virginiana", "Nasua narica", "Sciurus aureogaster", "Urocyon cinereoargenteus",
    "Odocoileus virginianus",
    "Sceloporus grammicus", "Ctenosaura pectinata", "Crotalus molossus",
    "Rhinella horribilis", "Ambystoma velasci",
    "Danaus plexippus", "Hippodamia convergens", "Hetaerina americana", "Sphenarium purpurascens",
    "Jacaranda mimosifolia", "Schinus molle", "Taxodium mucronatum", "Opuntia ficus-indica", "Myrtillocactus geometrizans",
    "Tagetes erecta", "Agave salmiana", "Erythrina americana",
]
FUERA_DEL_CATALOGO = [
    "Turdus rufopalliatus", "Melanerpes aurifrons", "Pelecanus occidentalis", "Iguana iguana", "Sceloporus torquatus",
    "Junonia coenia", "Ricinus communis", "Leucaena leucocephala",
]
CABECERAS = {"User-Agent": "IdentificaEspecies/1.0 (evaluacion de precision; app educativa)"}


# ---------------------------------------------------------------- armar el set (gratis)
async def armar() -> None:
    FOTOS.mkdir(parents=True, exist_ok=True)
    salida = []
    async with httpx.AsyncClient(timeout=30, headers=CABECERAS, follow_redirects=True) as http:
        for nombre in DEL_CATALOGO + FUERA_DEL_CATALOGO:
            r = await http.get("https://api.inaturalist.org/v1/observations", params={
                "taxon_name": nombre, "quality_grade": "research", "photos": "true", "place_id": 6793,  # México
                "photo_license": "cc-by,cc-by-nc,cc0", "order_by": "votes", "per_page": 5,
            })
            r.raise_for_status()
            obs = next((o for o in r.json()["results"] if o.get("photos") and o["taxon"]["name"] == nombre), None)
            if not obs:
                print(f"  sin foto con licencia libre: {nombre}")
                continue
            foto = obs["photos"][0]
            url = foto["url"].replace("/square.", "/large.")  # 1024 px, como las que manda la app
            archivo = FOTOS / f"{nombre.replace(' ', '_')}.jpg"
            if not archivo.exists():
                archivo.write_bytes((await http.get(url)).content)
            lat, lon = (float(x) for x in obs["location"].split(",")) if obs.get("location") else (None, None)
            salida.append({
                "esperado": nombre, "en_catalogo": nombre in DEL_CATALOGO, "archivo": archivo.name,
                "latitud": lat, "longitud": lon, "url": url, "licencia": foto.get("license_code"),
                "atribucion": foto.get("attribution"), "observacion": f"https://www.inaturalist.org/observations/{obs['id']}",
            })
            print(f"  {nombre}: {foto.get('license_code')}")
            await asyncio.sleep(1)  # iNaturalist pide no más de una consulta por segundo
    SET.write_text(json.dumps(salida, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Set listo: {len(salida)} fotos en {SET}")


# ---------------------------------------------------------------- correr
async def aceptado(http: httpx.AsyncClient, nombre: str, cache: dict[str, str]) -> str:
    """Nombre aceptado según GBIF (así un sinónimo cuenta como acierto)."""
    if nombre not in cache:
        try:
            r = await http.get("https://api.gbif.org/v1/species/match", params={"name": nombre}, timeout=10)
            d = r.json()
            cache[nombre] = d.get("species") or d.get("canonicalName") or nombre
        except httpx.HTTPError:
            cache[nombre] = nombre
    return cache[nombre]


def costo(uso: dict) -> float:
    return (uso.get("input_tokens", 0) * PRECIO_ENTRADA + uso.get("output_tokens", 0) * PRECIO_SALIDA
            + uso.get("cache_read_input_tokens", 0) * PRECIO_CACHE_LECTURA
            + uso.get("cache_creation_input_tokens", 0) * PRECIO_CACHE_ESCRITURA) / 1_000_000


async def correr(nombre_corrida: str, razonamiento: str | None = None, limite_gasto: float = 0.10) -> None:
    import dataclasses

    from app import ia  # noqa: E402  (carga api/.env)

    if razonamiento:
        ia.settings = dataclasses.replace(ia.settings, ia_razonamiento=razonamiento)
    print(f"Modelo {ia.settings.ia_modelo}, razonamiento: {ia.settings.ia_razonamiento}")
    # Las fotos marcadas con "excluir" no sirven para medir (el motivo queda anotado en set.json).
    fotos = [f for f in json.loads(SET.read_text(encoding="utf-8")) if not f.get("excluir")]
    CORRIDAS.mkdir(parents=True, exist_ok=True)
    resultados, gasto, cache = [], 0.0, {}
    async with httpx.AsyncClient(headers=CABECERAS) as http:
        for f in fotos:
            imagen = (FOTOS / f["archivo"]).read_bytes()
            inicio = time.monotonic()
            primer_nombre = {}

            async def al_avanzar(campos: dict) -> None:
                if campos.get("nombre_comun") and "t" not in primer_nombre:
                    primer_nombre["t"] = time.monotonic() - inicio

            r = await ia.identificar(imagen, "image/jpeg", f["latitud"], f["longitud"], al_avanzar)
            segundos = time.monotonic() - inicio
            gasto += costo(r.uso)
            predicho = r.nombre_cientifico or ""
            esperado = await aceptado(http, f["esperado"], cache)
            acierto = bool(predicho) and (predicho == f["esperado"] or await aceptado(http, predicho, cache) == esperado)
            genero = bool(predicho) and predicho.split(" ")[0] == f["esperado"].split(" ")[0]
            resultados.append({
                "esperado": f["esperado"], "predicho": predicho, "acierto": acierto, "genero": acierto or genero,
                "confianza": r.confianza, "problema": r.problema, "segundos": round(segundos, 2),
                "segundos_al_nombre": round(primer_nombre.get("t", segundos), 2),
                "uso": r.uso, "candidatos": [c.nombre_cientifico for c in r.candidatos],
                "en_candidatos": acierto or f["esperado"] in [c.nombre_cientifico for c in r.candidatos],
            })
            print(f"  {'OK ' if acierto else 'MAL'} {segundos:5.1f} s (nombre a {primer_nombre.get('t', segundos):4.1f} s)  "
                  f"{f['esperado']:<28} -> {predicho} ({r.confianza:.2f})")
            if gasto > limite_gasto:
                print(f"Se detuvo: el gasto llegó a US${gasto:.4f} (límite US${limite_gasto})")
                break
    resumen = resumir(resultados)
    resumen["gasto_usd"] = round(gasto, 5)
    (CORRIDAS / f"{nombre_corrida}.json").write_text(
        json.dumps({"resumen": resumen, "resultados": resultados}, ensure_ascii=False, indent=1), encoding="utf-8")
    imprimir(nombre_corrida, resumen)


def resumir(resultados: list[dict]) -> dict:
    n = len(resultados) or 1
    tiempos = [x["segundos"] for x in resultados] or [0]
    return {
        "fotos": len(resultados),
        "aciertos_especie": round(sum(x["acierto"] for x in resultados) / n, 3),
        "aciertos_genero": round(sum(x["genero"] for x in resultados) / n, 3),
        "correcta_entre_candidatos": round(sum(x["en_candidatos"] for x in resultados) / n, 3),
        "segundos_mediana": round(statistics.median(tiempos), 2),
        "segundos_p90": round(sorted(tiempos)[int(0.9 * (len(tiempos) - 1))], 2),
        "segundos_al_nombre_mediana": round(statistics.median(x.get("segundos_al_nombre", x["segundos"]) for x in resultados), 2)
        if resultados else 0,
        "tokens_salida_promedio": round(statistics.mean(x["uso"].get("output_tokens", 0) for x in resultados), 1) if resultados else 0,
    }


def imprimir(nombre: str, r: dict) -> None:
    print(f"\n{nombre}: {r['fotos']} fotos · especie {r['aciertos_especie']:.0%} · género {r['aciertos_genero']:.0%} · "
          f"correcta entre candidatos {r['correcta_entre_candidatos']:.0%} · mediana {r['segundos_mediana']} s · "
          f"p90 {r['segundos_p90']} s · nombre visible (mediana) {r.get('segundos_al_nombre_mediana', '-')} s · "
          f"{r['tokens_salida_promedio']} tokens de salida · US${r.get('gasto_usd', 0):.4f}")


def comparar(a: str, b: str) -> None:
    for nombre in (a, b):
        imprimir(nombre, json.loads((CORRIDAS / f"{nombre}.json").read_text(encoding="utf-8"))["resumen"])


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in ("armar", "correr", "comparar"):
        raise SystemExit(__doc__)
    if sys.argv[1] == "armar":
        asyncio.run(armar())
    elif sys.argv[1] == "correr":
        asyncio.run(correr(sys.argv[2] if len(sys.argv) > 2 else time.strftime("%Y%m%d-%H%M"),
                           sys.argv[3] if len(sys.argv) > 3 else None))
    else:
        comparar(sys.argv[2], sys.argv[3])
