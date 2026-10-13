"""Identificación de especies con Google Gemini (plan gratuito): visión + respuesta en JSON.

Gemini identifica cualquier animal o planta del mundo y devuelve también los datos de su ficha.
Ya no se le manda el catálogo completo: la petición es más corta y la respuesta llega más rápido.
"""
import asyncio
import base64
import logging
import re
import time
from typing import Literal

import httpx
from pydantic import BaseModel, Field

from .config import settings

log = logging.getLogger("pvz")

TIPOS_IMAGEN = {"image/jpeg", "image/png", "image/webp", "image/gif"}
GRUPOS_ANIMAL = ["ave", "mamifero", "reptil", "anfibio", "pez", "insecto", "invertebrado"]
GRUPOS_PLANTA = ["arbol", "arbusto", "cactacea", "agave", "flor", "palma", "helecho", "planta"]

SISTEMA = """Eres un biólogo de campo experto en fauna y flora de todo el mundo, con especial conocimiento de México.
Recibes una foto tomada por una persona del público general.

1. problema: "borrosa" si no se distingue el organismo (foto muy borrosa, oscura o movida);
   "sin_organismo" si no hay un animal ni una planta reconocible (paisaje, objetos, personas, mascotas domésticas
   comunes como perros o gatos, hongos); en los demás casos "ninguno".
2. Si la foto sirve, identifica la especie lo más preciso que puedas:
   - nombre_cientifico: binomial "Género especie" (sin autor ni año). Si solo puedes llegar al género, "Género sp.".
   - nombre_comun: el nombre común más usado en México, en español.
   - reino: "animal" o "planta". grupo: uno de la lista permitida.
   - familia: familia taxonómica.
   - descripcion (2 frases), habitat, alimentacion (solo animales; null en plantas) y tamano (ej. "70 a 75 cm"): breves, en español sencillo.
   - categoria_nom059: categoría en la NOM-059-SEMARNAT-2010 ("P", "A", "Pr" o "E") SOLO si estás seguro; si no, null.
   - introducida: true si la especie no es nativa de México.
3. confianza de 0 a 1, honesta: menos de 0.7 si dudas entre especies parecidas o la foto no muestra los rasgos que las distinguen.
4. candidatos: hasta 3 especies posibles (incluida la elegida), de mayor a menor confianza.
5. explicacion: 2 o 3 frases en español sencillo sobre qué rasgos de la foto te llevaron a la respuesta.
   Si la foto no sirve, da un consejo concreto para tomar una mejor.
Si problema no es "ninguno", deja en null los datos de la especie y candidatos vacío."""


class Candidato(BaseModel):
    nombre_cientifico: str
    nombre_comun: str | None = None
    confianza: float


class Ficha(BaseModel):
    """Datos para crear la especie en el catálogo si todavía no existe."""
    nombre_cientifico: str
    nombre_comun: str
    reino: Literal["animal", "planta"]
    grupo: str
    familia: str | None = None
    descripcion: str | None = None
    habitat: str | None = None
    alimentacion: str | None = None
    tamano: str | None = None
    categoria_nom059: Literal["P", "A", "Pr", "E"] | None = None
    introducida: bool = False


class Resultado(BaseModel):
    problema: Literal["ninguno", "borrosa", "sin_organismo"]
    especie: Ficha | None = None
    confianza: float = 0.0
    explicacion: str = ""
    candidatos: list[Candidato] = Field(default_factory=list)


class IAError(Exception):
    """Fallo al hablar con Gemini. El texto es para la persona; `detalle` es lo técnico, para la terminal de la API."""

    def __init__(self, mensaje: str, detalle: str = ""):
        super().__init__(mensaje)
        self.detalle = detalle or mensaje


def _error_de_gemini(status: int, cuerpo: str, modelo: str | None = None) -> IAError:
    modelo = modelo or settings.ia_modelo
    detalle = f"{modelo} respondió {status}: {cuerpo[:500]}"
    texto = cuerpo.lower()
    if status == 429:
        return IAError("Se acabó la cuota gratuita de Gemini por ahora. Intenta más tarde.", detalle)
    if status in (401, 403) or "api key" in texto or "api_key" in texto:
        return IAError(
            "La clave de Gemini no es válida o no tiene permiso. Revisa GEMINI_API_KEY en api/.env y reinicia la API.", detalle
        )
    if status == 404:
        return IAError(f"El modelo de Gemini «{modelo}» no está disponible. Revisa IA_MODELO en api/.env.", detalle)
    if status >= 500:
        return IAError("Gemini está saturado o fuera de servicio en este momento. Intenta en un momento.", detalle)
    return IAError("Gemini rechazó la petición. Intenta de nuevo con otra foto.", detalle)


_TEXTO = {"type": "STRING", "nullable": True}
# Mismo formato que Resultado, en el dialecto de esquemas que acepta Gemini.
ESQUEMA = {
    "type": "OBJECT",
    "properties": {
        "problema": {"type": "STRING", "enum": ["ninguno", "borrosa", "sin_organismo"]},
        "especie": {
            "type": "OBJECT",
            "nullable": True,
            "properties": {
                "nombre_cientifico": {"type": "STRING"},
                "nombre_comun": {"type": "STRING"},
                "reino": {"type": "STRING", "enum": ["animal", "planta"]},
                "grupo": {"type": "STRING", "enum": GRUPOS_ANIMAL + GRUPOS_PLANTA},
                "familia": _TEXTO,
                "descripcion": _TEXTO,
                "habitat": _TEXTO,
                "alimentacion": _TEXTO,
                "tamano": _TEXTO,
                "categoria_nom059": {"type": "STRING", "enum": ["P", "A", "Pr", "E"], "nullable": True},
                "introducida": {"type": "BOOLEAN"},
            },
            "required": ["nombre_cientifico", "nombre_comun", "reino", "grupo", "familia", "descripcion", "habitat",
                         "alimentacion", "tamano", "categoria_nom059", "introducida"],
        },
        "confianza": {"type": "NUMBER"},
        "explicacion": {"type": "STRING"},
        "candidatos": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "nombre_cientifico": {"type": "STRING"},
                    "nombre_comun": {"type": "STRING"},
                    "confianza": {"type": "NUMBER"},
                },
                "required": ["nombre_cientifico", "nombre_comun", "confianza"],
            },
        },
    },
    "required": ["problema", "especie", "confianza", "explicacion", "candidatos"],
    "propertyOrdering": ["problema", "especie", "confianza", "explicacion", "candidatos"],
}

_http: httpx.AsyncClient | None = None


def http() -> httpx.AsyncClient:
    global _http
    if _http is None:
        _http = httpx.AsyncClient(timeout=httpx.Timeout(settings.ia_tiempo_maximo, connect=10))
    return _http


def modelos_a_probar() -> list[str]:
    """El modelo de IA_MODELO y después los de respaldo, sin repetir."""
    return list(dict.fromkeys([settings.ia_modelo, *settings.ia_modelos_respaldo]))


def _ajuste_de_razonamiento(modelo: str) -> dict | None:
    """Pide razonamiento corto: es la mayor ganancia de velocidad. Cada familia de modelos lo pide distinto."""
    if modelo.startswith(("gemini-1.", "gemini-2.0")):
        return None
    if modelo.startswith("gemini-2.5"):
        return {"thinkingBudget": 0 if "pro" not in modelo else 128}
    return {"thinkingLevel": "low"}


SIN_RESULTADO = Resultado(
    problema="sin_organismo",
    explicacion="No pudimos identificar esta foto. Intenta con otra en la que el animal o la planta se vea más de cerca.",
)


def normalizar_nombre(nombre: str) -> str:
    """'ara  MILITARIS' -> 'Ara militaris' (para no duplicar especies por mayúsculas o espacios)."""
    partes = re.sub(r"\s+", " ", nombre.strip()).split(" ")
    if not partes or not partes[0]:
        return ""
    return " ".join([partes[0].capitalize()] + [p.lower() for p in partes[1:]])


def _limpiar(r: Resultado) -> Resultado:
    r.confianza = max(0.0, min(1.0, r.confianza))
    if r.problema != "ninguno":
        r.especie, r.candidatos = None, []
        return r
    if r.especie:
        r.especie.nombre_cientifico = normalizar_nombre(r.especie.nombre_cientifico)
        if r.especie.grupo not in (GRUPOS_ANIMAL if r.especie.reino == "animal" else GRUPOS_PLANTA):
            r.especie.grupo = "invertebrado" if r.especie.reino == "animal" else "planta"
        if r.especie.reino == "planta":
            r.especie.alimentacion = None
    if not r.especie or not r.especie.nombre_cientifico:
        return SIN_RESULTADO.model_copy()
    vistos, candidatos = set(), []
    for c in r.candidatos:
        c.nombre_cientifico = normalizar_nombre(c.nombre_cientifico)
        c.confianza = round(max(0.0, min(1.0, c.confianza)), 3)
        if c.nombre_cientifico and c.nombre_cientifico not in vistos:
            vistos.add(c.nombre_cientifico)
            candidatos.append(c)
    r.candidatos = candidatos[:3]
    return r


async def _pedir(modelo: str, cuerpo: dict, segundos: float) -> httpx.Response:
    url = f"{settings.ia_url}/v1beta/models/{modelo}:generateContent"
    try:
        return await http().post(
            url, json=cuerpo, headers={"x-goog-api-key": settings.gemini_api_key},
            timeout=httpx.Timeout(segundos, connect=min(10, segundos)),
        )
    except httpx.TimeoutException as e:
        raise IAError(
            "Gemini tardó demasiado en responder. Intenta de nuevo en un momento.", f"{modelo}: tiempo agotado ({segundos:.0f} s): {e!r}"
        ) from e
    except httpx.HTTPError as e:
        raise IAError("La API no pudo conectarse a Gemini. Revisa el internet de la computadora donde corre la API.", repr(e)) from e


def _cuerpo(imagen: bytes, tipo: str, pista: str, modelo: str) -> dict:
    config: dict = {"responseMimeType": "application/json", "responseSchema": ESQUEMA}
    razonamiento = _ajuste_de_razonamiento(modelo)
    if razonamiento:
        config["thinkingConfig"] = razonamiento
    return {
        "systemInstruction": {"parts": [{"text": SISTEMA}]},
        "contents": [{
            "role": "user",
            "parts": [{"inlineData": {"mimeType": tipo, "data": base64.b64encode(imagen).decode()}}, {"text": pista}],
        }],
        "generationConfig": config,
    }


async def _con_modelo(modelo: str, imagen: bytes, tipo: str, pista: str, limite: float) -> httpx.Response:
    """Pide la identificación a un modelo. Devuelve la respuesta (aunque sea un error) o lanza IAError (tiempo / red)."""
    cuerpo = _cuerpo(imagen, tipo, pista, modelo)
    r = await _pedir(modelo, cuerpo, max(1.0, min(settings.ia_tiempo_maximo, limite - time.monotonic())))
    if r.status_code == 400 and "thinking" in r.text.lower() and "thinkingConfig" in cuerpo["generationConfig"]:
        # El modelo no acepta ese ajuste de razonamiento: se repite sin él.
        log.info("El modelo %s no acepta thinkingConfig; se repite sin ese ajuste.", modelo)
        del cuerpo["generationConfig"]["thinkingConfig"]
        r = await _pedir(modelo, cuerpo, max(1.0, min(settings.ia_tiempo_maximo, limite - time.monotonic())))
    if r.status_code in (500, 502, 503, 504) and limite - time.monotonic() > 10:
        # Gemini a veces responde "saturado" un instante; un segundo intento suele funcionar.
        await asyncio.sleep(1)
        r = await _pedir(modelo, cuerpo, max(1.0, min(settings.ia_tiempo_maximo, limite - time.monotonic())))
    return r


def _leer(r: httpx.Response) -> Resultado:
    # Si Gemini bloquea la foto o la respuesta no trae el JSON esperado, se guarda como "no identificada".
    try:
        partes = r.json()["candidates"][0]["content"]["parts"]
        texto = "".join(p.get("text", "") for p in partes if not p.get("thought"))
        return _limpiar(Resultado.model_validate_json(texto))
    except (KeyError, IndexError, TypeError, ValueError) as e:
        log.warning("Respuesta de Gemini que no se pudo leer: %r · %s", e, r.text[:300])
        return SIN_RESULTADO.model_copy()


async def identificar(imagen: bytes, tipo: str, latitud: float | None = None, longitud: float | None = None) -> Resultado:
    """Prueba el modelo configurado y, si no existe, no tiene cuota, falla o tarda demasiado, los de respaldo."""
    if tipo not in TIPOS_IMAGEN:
        tipo = "image/jpeg"
    pista = "Identifica el animal o la planta de esta foto."
    if latitud is not None and longitud is not None:
        pista += f" La foto se tomó cerca de latitud {latitud:.2f}, longitud {longitud:.2f}."

    limite = time.monotonic() + settings.ia_tiempo_total
    ultimo: IAError | None = None
    for modelo in modelos_a_probar():
        if limite - time.monotonic() < 3:
            break
        inicio = time.monotonic()
        try:
            r = await _con_modelo(modelo, imagen, tipo, pista, limite)
        except IAError as e:
            log.warning("Gemini (%s) falló: %s", modelo, e.detalle)
            ultimo = e
            continue
        if r.status_code == 200:
            log.info("Identificado con %s en %.1f s", modelo, time.monotonic() - inicio)
            return _leer(r)
        ultimo = _error_de_gemini(r.status_code, r.text, modelo)
        log.warning("Gemini (%s) falló: %s", modelo, ultimo.detalle)
        if r.status_code in (401, 403) or (r.status_code == 400 and "api key" in r.text.lower()):
            break  # la clave no sirve: ningún otro modelo va a funcionar
    raise ultimo or IAError("Gemini tardó demasiado en responder. Intenta de nuevo en un momento.", "Sin tiempo para probar modelos")
