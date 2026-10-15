"""Identificación de especies con Claude (Anthropic), en dos pasos:

1. identificar(): mira la foto y responde solo lo necesario para decidir (nombres, grupo, confianza, especies
   parecidas y una explicación corta). La respuesta llega por partes (streaming): en cuanto Claude escribe el
   nombre se avisa, sin esperar al resto. Antes Claude escribía también la ficha completa en cada foto,
   aunque la especie ya estuviera en el catálogo: era lo más lento.
2. escribir_ficha(): descripción, hábitat, alimentación, tamaño, NOM-059... Solo para especies nuevas en el
   catálogo. No necesita la foto, así que es barato, y se hace después de mostrar el resultado.
"""
import asyncio
import base64
import json
import logging
import re
from collections.abc import Awaitable, Callable
from typing import Literal

import anthropic
from pydantic import BaseModel, Field

from .config import settings
from .taxonomia import normalizar_nombre

log = logging.getLogger("api")

TIPOS_IMAGEN = {"image/jpeg", "image/png", "image/webp", "image/gif"}
GRUPOS_ANIMAL = ["ave", "mamifero", "reptil", "anfibio", "pez", "insecto", "invertebrado"]
GRUPOS_PLANTA = ["arbol", "arbusto", "cactacea", "agave", "flor", "palma", "helecho", "planta"]

SISTEMA = """Eres un biólogo de campo experto en fauna y flora de todo el mundo, con especial conocimiento de México.
Recibes una foto tomada por una persona del público general. Identifica el organismo principal: el más grande, nítido o centrado.

1. problema: "borrosa" si no se distingue el organismo (foto muy borrosa, oscura o movida);
   "sin_organismo" si no hay ningún animal ni planta reconocible (paisaje sin un organismo claro, objetos, solo personas,
   hongos, dibujos o pantallas); en los demás casos "ninguno". Cualquier animal cuenta, también los domésticos y de granja
   (perros, gatos, gallinas, vacas...) y los insectos, arañas, peces o aves pequeñas.
2. Si la foto sirve:
   - nombre_comun: el nombre común más usado en México, en español.
   - nombre_cientifico: "Género especie" con la taxonomía vigente (la que usan GBIF e iNaturalist), sin autor ni año.
     En animales domésticos usa la forma doméstica (Canis lupus familiaris, Felis catus, Gallus gallus domesticus).
     Si solo puedes llegar al género, "Género sp.".
   - reino: "animal" o "planta". grupo: uno de la lista permitida.
3. confianza de 0 a 1, honesta: menos de 0.7 si dudas entre especies parecidas o la foto no muestra los rasgos que las distinguen.
4. candidatos: hasta 3 especies posibles (incluida la elegida), de mayor a menor confianza, cada una con su grupo.
5. explicacion: 1 o 2 frases en español sencillo con los rasgos de la foto que te llevaron a la respuesta.
   Si la foto no sirve, da un consejo concreto para tomar una mejor.
Si problema no es "ninguno", deja en null nombre_comun, nombre_cientifico, reino y grupo, y candidatos vacío."""

SISTEMA_FICHA = """Eres un biólogo que escribe fichas de especies para una app de divulgación en México, en español sencillo.
Para la especie indicada:
- descripcion: 2 frases: cómo reconocerla y un dato interesante.
- habitat: dónde vive, breve.
- alimentacion: qué come (solo animales; null en plantas).
- tamano: tamaño típico (ej. "70 a 75 cm", "3 a 5 m de altura").
- familia: familia taxonómica.
- categoria_nom059: categoría en la NOM-059-SEMARNAT-2010 ("P", "A", "Pr" o "E") SOLO si estás seguro; si no, null.
- introducida: true si no es nativa de México (las domésticas y cultivadas de origen extranjero también cuentan)."""


class Candidato(BaseModel):
    nombre_cientifico: str
    nombre_comun: str | None = None
    grupo: str | None = None
    confianza: float


class Identificacion(BaseModel):
    problema: Literal["ninguno", "borrosa", "sin_organismo"]
    nombre_comun: str | None = None
    nombre_cientifico: str | None = None
    reino: Literal["animal", "planta"] | None = None
    grupo: str | None = None
    confianza: float = 0.0
    candidatos: list[Candidato] = Field(default_factory=list)
    explicacion: str = ""
    # Tokens que usó Claude (para medir el gasto); no forma parte de la respuesta del modelo.
    uso: dict = Field(default_factory=dict, exclude=True)

    @property
    def tiene_especie(self) -> bool:
        return self.problema == "ninguno" and bool(self.nombre_cientifico)


class Ficha(BaseModel):
    """Datos para completar la especie en el catálogo."""
    familia: str | None = None
    descripcion: str | None = None
    habitat: str | None = None
    alimentacion: str | None = None
    tamano: str | None = None
    categoria_nom059: Literal["P", "A", "Pr", "E"] | None = None
    introducida: bool = False


class IAError(Exception):
    """Fallo al hablar con Claude. El texto es para la persona; `detalle` es lo técnico, para la terminal de la API."""

    def __init__(self, mensaje: str, detalle: str = ""):
        super().__init__(mensaje)
        self.detalle = detalle or mensaje


def _o_nulo(esquema: dict) -> dict:
    return {"anyOf": [esquema, {"type": "null"}]}


_TEXTO_O_NULO = _o_nulo({"type": "string"})
_GRUPO = {"type": "string", "enum": GRUPOS_ANIMAL + GRUPOS_PLANTA}
# El orden importa: los nombres van primero para poder mostrarlos mientras Claude escribe el resto.
# (Se probó poner la explicación antes del nombre y responder sin razonar: más rápido, pero menos preciso.)
ESQUEMA = {
    "type": "object",
    "properties": {
        "problema": {"type": "string", "enum": ["ninguno", "borrosa", "sin_organismo"]},
        "nombre_comun": _TEXTO_O_NULO,
        "nombre_cientifico": _TEXTO_O_NULO,
        "reino": _o_nulo({"type": "string", "enum": ["animal", "planta"]}),
        "grupo": _o_nulo(_GRUPO),
        "confianza": {"type": "number"},
        "candidatos": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "nombre_cientifico": {"type": "string"},
                    "nombre_comun": {"type": "string"},
                    "grupo": _GRUPO,
                    "confianza": {"type": "number"},
                },
                "required": ["nombre_cientifico", "nombre_comun", "grupo", "confianza"],
                "additionalProperties": False,
            },
        },
        "explicacion": {"type": "string"},
    },
    "required": ["problema", "nombre_comun", "nombre_cientifico", "reino", "grupo", "confianza", "candidatos", "explicacion"],
    "additionalProperties": False,
}

ESQUEMA_FICHA = {
    "type": "object",
    "properties": {
        "descripcion": {"type": "string"},
        "habitat": {"type": "string"},
        "alimentacion": _TEXTO_O_NULO,
        "tamano": {"type": "string"},
        "familia": _TEXTO_O_NULO,
        "categoria_nom059": _o_nulo({"type": "string", "enum": ["P", "A", "Pr", "E"]}),
        "introducida": {"type": "boolean"},
    },
    "required": ["descripcion", "habitat", "alimentacion", "tamano", "familia", "categoria_nom059", "introducida"],
    "additionalProperties": False,
}

_cliente: anthropic.AsyncAnthropic | None = None


def cliente() -> anthropic.AsyncAnthropic:
    global _cliente
    if _cliente is None:
        cabeceras = {"anthropic-workspace-id": settings.anthropic_workspace_id} if settings.anthropic_workspace_id else None
        _cliente = anthropic.AsyncAnthropic(
            api_key=settings.anthropic_api_key,
            base_url=settings.ia_url,
            default_headers=cabeceras,
            timeout=settings.ia_tiempo_maximo,
            max_retries=1,  # un reintento automático si Claude está saturado (429, 5xx o 529)
        )
    return _cliente


def _error(e: Exception) -> IAError:
    """Traduce cada fallo de Claude a un mensaje que diga qué hacer."""
    if isinstance(e, (anthropic.APITimeoutError, TimeoutError)):
        return IAError("Claude tardó demasiado en responder. Intenta de nuevo en un momento.",
                       f"Tiempo agotado ({settings.ia_tiempo_maximo} s por trozo, {settings.ia_tiempo_total} s en total): {e!r}")
    if isinstance(e, anthropic.APIConnectionError):
        return IAError("La API no pudo conectarse a Claude. Revisa el internet de la computadora donde corre la API.", repr(e))
    if not isinstance(e, anthropic.APIStatusError):
        return IAError("Ocurrió un error inesperado al hablar con Claude. Intenta de nuevo.", repr(e))
    detalle = f"Claude respondió {e.status_code}: {str(e)[:800]}"
    texto = str(e).lower()
    if "not scoped to a workspace" in texto:
        return IAError(
            "Tu clave de Claude es de ámbito «Organización» y no sirve sola. Crea en console.anthropic.com > API Keys una clave "
            "del espacio de trabajo «Default» y ponla en ANTHROPIC_API_KEY (api/.env), o agrega ANTHROPIC_WORKSPACE_ID.", detalle)
    if "workspace" in texto and "valid" in texto:
        return IAError("ANTHROPIC_WORKSPACE_ID en api/.env no es un ID de espacio de trabajo válido (empieza con wrkspc_).", detalle)
    if e.status_code == 402 or "credit balance" in texto or "billing" in texto:
        return IAError("Tu cuenta de Claude no tiene saldo. Carga crédito en console.anthropic.com (Billing) y vuelve a intentar.", detalle)
    if e.status_code == 401:
        return IAError("La clave de Claude no es válida. Revisa ANTHROPIC_API_KEY en api/.env (debe ser la clave completa, "
                       "de unos 100 caracteres) y reinicia la API.", detalle)
    if e.status_code == 403:
        return IAError("La clave de Claude no tiene permiso para usar este modelo. Revisa tu cuenta en console.anthropic.com.", detalle)
    if e.status_code == 404:
        return IAError(f"El modelo de Claude «{settings.ia_modelo}» no está disponible. Revisa IA_MODELO en api/.env.", detalle)
    if "could not process image" in texto:
        return IAError("Claude no pudo leer esa imagen. Intenta con otra foto (JPG o PNG).", detalle)
    if e.status_code == 413:
        return IAError("La foto es demasiado grande. Intenta con otra.", detalle)
    if e.status_code == 429:
        return IAError("Se alcanzó el límite de uso de Claude por ahora. Intenta en un momento.", detalle)
    if e.status_code >= 500:
        return IAError("Claude está saturado o fuera de servicio en este momento. Intenta en un momento.", detalle)
    # Cualquier otro rechazo: se muestra el motivo que da Claude para no esconder la causa.
    motivo = getattr(e, "message", "") or str(e)
    return IAError(f"Claude rechazó la petición: {motivo[:300]}", detalle)


SIN_RESULTADO = Identificacion(
    problema="sin_organismo",
    explicacion="No pudimos identificar esta foto. Intenta con otra en la que el animal o la planta se vea más de cerca.",
)


def _limpiar(r: Identificacion) -> Identificacion:
    r.confianza = max(0.0, min(1.0, r.confianza))
    if r.problema != "ninguno":
        r.nombre_comun = r.nombre_cientifico = r.reino = r.grupo = None
        r.candidatos = []
        return r
    r.nombre_cientifico = normalizar_nombre(r.nombre_cientifico or "")
    if not r.nombre_cientifico or not r.reino:
        return SIN_RESULTADO.model_copy(update={"uso": r.uso})
    r.nombre_comun = (r.nombre_comun or "").strip() or r.nombre_cientifico
    if r.grupo not in (GRUPOS_ANIMAL if r.reino == "animal" else GRUPOS_PLANTA):
        r.grupo = "invertebrado" if r.reino == "animal" else "planta"
    vistos, candidatos = set(), []
    for c in r.candidatos:
        c.nombre_cientifico = normalizar_nombre(c.nombre_cientifico)
        c.confianza = round(max(0.0, min(1.0, c.confianza)), 3)
        if c.grupo not in GRUPOS_ANIMAL + GRUPOS_PLANTA:
            c.grupo = None
        if c.nombre_cientifico and c.nombre_cientifico not in vistos:
            vistos.add(c.nombre_cientifico)
            candidatos.append(c)
    r.candidatos = candidatos[:3]
    return r


def reino_de(grupo: str | None) -> str | None:
    if grupo in GRUPOS_ANIMAL:
        return "animal"
    if grupo in GRUPOS_PLANTA:
        return "planta"
    return None


def _tipo_real(imagen: bytes, tipo: str) -> str:
    """El tipo según los primeros bytes de la foto: Claude rechaza la petición si no coincide con el declarado."""
    if imagen[:2] == b"\xff\xd8":
        return "image/jpeg"
    if imagen[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if imagen[:4] == b"GIF8":
        return "image/gif"
    if imagen[:4] == b"RIFF" and imagen[8:12] == b"WEBP":
        return "image/webp"
    return tipo if tipo in TIPOS_IMAGEN else "image/jpeg"


def _pista(latitud: float | None, longitud: float | None) -> str:
    pista = "Identifica el animal o la planta de esta foto."
    if latitud is not None and longitud is not None:
        pista += f" La foto se tomó cerca de latitud {latitud:.2f}, longitud {longitud:.2f}."
    return pista


def _razonamiento() -> dict:
    """Con "sin", Claude responde sin razonar antes (más rápido). Con "bajo", razona un poco (adaptativo)."""
    return {"thinking": {"type": "disabled"}} if settings.ia_razonamiento == "sin" else {}


# ------------------------------------------------------------------ lectura de la respuesta parcial
_CAMPO_TEXTO = re.compile(r'"(problema|explicacion|nombre_comun|nombre_cientifico|reino|grupo)"\s*:\s*(null|"((?:[^"\\]|\\.)*)")')
_CAMPO_CONFIANZA = re.compile(r'"confianza"\s*:\s*(-?\d+(?:\.\d+)?)\s*[,}]')
# La explicación se muestra mientras se escribe (todavía sin las comillas de cierre).
_EXPLICACION_A_MEDIAS = re.compile(r'"explicacion"\s*:\s*"((?:[^"\\]|\\.)*)$')


def campos_listos(texto: str) -> dict:
    """Campos ya completos en un JSON que todavía se está escribiendo (los de antes de "candidatos" y la explicación)."""
    corte = texto.find('"candidatos"')
    fin = texto.find('"explicacion"')
    parte = texto if corte < 0 else texto[:corte] + (texto[fin:] if fin > corte else "")
    datos: dict = {}
    for m in _CAMPO_TEXTO.finditer(parte):
        datos[m.group(1)] = None if m.group(2) == "null" else json.loads('"' + m.group(3) + '"')
    m = _CAMPO_CONFIANZA.search(parte)
    if m:
        datos["confianza"] = max(0.0, min(1.0, float(m.group(1))))
    if "explicacion" not in datos:
        m = _EXPLICACION_A_MEDIAS.search(parte.rstrip("\\"))
        if m:
            try:
                datos["explicacion"] = json.loads('"' + m.group(1) + '"')
            except ValueError:
                pass
    if datos.get("nombre_cientifico"):
        datos["nombre_cientifico"] = normalizar_nombre(datos["nombre_cientifico"])
    return datos


AlAvanzar = Callable[[dict], Awaitable[None]]


async def identificar(imagen: bytes, tipo: str, latitud: float | None = None, longitud: float | None = None,
                      al_avanzar: AlAvanzar | None = None) -> Identificacion:
    """Identifica la foto. Si se pasa `al_avanzar`, se le avisa cada vez que hay campos nuevos completos."""
    tipo = _tipo_real(imagen, tipo)
    texto, avisado = "", {}
    try:
        async with asyncio.timeout(settings.ia_tiempo_total):
            async with cliente().messages.stream(
                model=settings.ia_modelo,
                max_tokens=6000,
                # Las instrucciones son siempre iguales: se guardan en caché (más barato y un poco más rápido).
                system=[{"type": "text", "text": SISTEMA, "cache_control": {"type": "ephemeral"}}],
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "image", "source": {"type": "base64", "media_type": tipo,
                                                     "data": base64.b64encode(imagen).decode()}},
                        {"type": "text", "text": _pista(latitud, longitud)},
                    ],
                }],
                output_config={"effort": "low", "format": {"type": "json_schema", "schema": ESQUEMA}},
                **_razonamiento(),
            ) as stream:
                async for trozo in stream.text_stream:
                    texto += trozo
                    if al_avanzar is not None:
                        listos = campos_listos(texto)
                        if listos != avisado:
                            avisado = listos
                            await al_avanzar(dict(listos))
                final = await stream.get_final_message()
    except (anthropic.APIError, TimeoutError) as e:
        raise _error(e) from e

    uso = final.usage.model_dump(exclude_none=True) if final.usage else {}
    # Si Claude declina la foto o la respuesta queda incompleta, se guarda como "no identificada".
    if final.stop_reason in ("refusal", "max_tokens"):
        log.warning("Claude terminó con stop_reason=%s; la foto queda como no identificada.", final.stop_reason)
        return SIN_RESULTADO.model_copy(update={"uso": uso})
    try:
        completo = "".join(b.text for b in final.content if b.type == "text")
        resultado = Identificacion.model_validate_json(completo)
    except ValueError as e:
        log.warning("Respuesta de Claude que no se pudo leer: %r", e)
        return SIN_RESULTADO.model_copy(update={"uso": uso})
    resultado.uso = uso
    return _limpiar(resultado)


async def escribir_ficha(nombre_cientifico: str, nombre_comun: str, reino: str, grupo: str) -> Ficha:
    """Ficha de una especie nueva en el catálogo (sin foto: solo con su nombre)."""
    try:
        r = await cliente().messages.create(
            model=settings.ia_modelo,
            max_tokens=3000,
            system=SISTEMA_FICHA,
            messages=[{"role": "user", "content": f"Especie: {nombre_cientifico} ({nombre_comun}). Reino: {reino}. Grupo: {grupo}."}],
            output_config={"effort": "low", "format": {"type": "json_schema", "schema": ESQUEMA_FICHA}},
            **_razonamiento(),
        )
    except anthropic.APIError as e:
        raise _error(e) from e
    if r.stop_reason in ("refusal", "max_tokens"):
        raise IAError("Claude no escribió la ficha.", f"stop_reason={r.stop_reason}")
    try:
        ficha = Ficha.model_validate_json("".join(b.text for b in r.content if b.type == "text"))
    except ValueError as e:
        raise IAError("La ficha de Claude no se pudo leer.", repr(e)) from e
    if reino == "planta":
        ficha.alimentacion = None
    return ficha
