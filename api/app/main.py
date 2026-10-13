"""API de identificación: POST /identificar y GET /salud."""
import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

import httpx
from fastapi import BackgroundTasks, Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from . import fotos_especies, ia
from .config import settings
from .supabase_client import Supabase, SupabaseError

log = logging.getLogger("pvz")
if not logging.getLogger().handlers:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s:     %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with httpx.AsyncClient(timeout=30) as http:
        app.state.supabase = Supabase(http)
        yield


app = FastAPI(title="Plantas vs Zombies · API de identificación", version="0.1.0", lifespan=lifespan)


@app.middleware("http")
async def errores_inesperados(request: Request, call_next):
    """Cualquier error no previsto se responde como JSON y dentro de CORS.
    Sin esto el navegador recibe un 500 sin cabeceras CORS y la app cree que no hay internet."""
    try:
        return await call_next(request)
    except Exception:
        log.exception("Error inesperado en %s", request.url.path)
        return JSONResponse(
            status_code=500,
            content={"detail": {"codigo": "error_interno", "mensaje": "Ocurrió un error en el servidor. Intenta de nuevo."}},
        )


# CORS se agrega al final para que envuelva todo, incluido el manejador de errores de arriba.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_origin_regex=settings.cors_origin_regex,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)


def error(status: int, codigo: str, mensaje: str, **extra) -> HTTPException:
    return HTTPException(status_code=status, detail={"codigo": codigo, "mensaje": mensaje, **extra})


def supabase(request: Request) -> Supabase:
    return request.app.state.supabase


async def usuario_actual(authorization: str = Header(default=""), sb: Supabase = Depends(supabase)) -> dict:
    faltan = settings.faltantes()
    if faltan:
        # Sin esto, una URL vacía hacía fallar la petición a Supabase y el navegador lo mostraba como "sin internet".
        raise error(
            503, "configuracion_incompleta",
            "La API no está configurada: faltan " + ", ".join(faltan) + " en el archivo api/.env. Agrégalas y reinicia la API.",
        )
    if not authorization.lower().startswith("bearer "):
        raise error(401, "sin_sesion", "Inicia sesión para identificar especies.")
    try:
        usuario = await sb.usuario_de_token(authorization[7:].strip())
    except SupabaseError as e:
        raise error(502, "base_de_datos", "No pudimos conectar con la base de datos. Intenta de nuevo.") from e
    if not usuario:
        raise error(401, "sin_sesion", "Tu sesión expiró. Vuelve a iniciar sesión.")
    return usuario


class PeticionIdentificar(BaseModel):
    ruta_foto: str = Field(min_length=3, max_length=300)
    latitud: float | None = Field(default=None, ge=-90, le=90)
    longitud: float | None = Field(default=None, ge=-180, le=180)
    observada_en: datetime | None = None


@app.get("/salud")
async def salud():
    faltan = settings.faltantes()
    return {"estado": "ok" if not faltan else "incompleto", "faltan_variables": faltan, "modelo": settings.ia_modelo}


@app.post("/identificar")
async def identificar(
    datos: PeticionIdentificar,
    tareas: BackgroundTasks,
    usuario: dict = Depends(usuario_actual),
    sb: Supabase = Depends(supabase),
):
    usuario_id = usuario["id"]

    # 1. La foto debe estar en la carpeta del propio usuario.
    if not datos.ruta_foto.startswith(f"{usuario_id}/") or ".." in datos.ruta_foto:
        raise error(403, "foto_ajena", "Esa foto no es tuya.")

    try:
        # 2. Límite diario y descarga de la foto, al mismo tiempo para ganar velocidad.
        usadas, foto = await asyncio.gather(sb.uso_ultimas_24h(usuario_id), sb.descargar_foto(datos.ruta_foto))
    except SupabaseError as e:
        raise error(502, "base_de_datos", "No pudimos conectar con la base de datos. Intenta de nuevo.") from e
    if len(usadas) >= settings.limite_diario:
        disponible = usadas[0] + timedelta(hours=24)
        raise error(
            429, "limite_diario", f"Llegaste al límite de {settings.limite_diario} identificaciones de hoy.",
            disponible_en=disponible.astimezone(timezone.utc).isoformat(), limite=settings.limite_diario,
        )
    if foto is None:
        raise error(404, "foto_no_encontrada", "No encontramos la foto. Vuelve a subirla.")

    # 3. IA (Gemini): identifica cualquier especie, sin catálogo fijo.
    try:
        resultado = await ia.identificar(foto[0], foto[1], datos.latitud, datos.longitud)
    except ia.IAError as e:
        # La causa técnica se escribe en la terminal de la API; la persona ve un mensaje claro.
        log.warning("Fallo al identificar con Gemini: %s", e.detalle)
        raise error(502, "ia_no_disponible", str(e)) from e

    # 4. Catálogo que crece solo: la especie se guarda la primera vez que alguien la fotografía.
    #    Con confianza muy baja no se crea (para no llenar el catálogo de errores); queda "en revisión" con sus candidatos.
    try:
        ficha = resultado.especie
        nombres = [c.nombre_cientifico for c in resultado.candidatos] + ([ficha.nombre_cientifico] if ficha else [])
        existentes = await sb.especies_por_nombre(list(dict.fromkeys(nombres)))
        especie_id = None
        if ficha:
            if ficha.nombre_cientifico in existentes:
                especie_id = existentes[ficha.nombre_cientifico]["id"]
            elif resultado.confianza >= settings.confianza_para_catalogo:
                nueva = await sb.crear_especie({**ficha.model_dump(), "protegida": ficha.categoria_nom059 is not None, "verificada": False})
                especie_id = nueva["id"]
                existentes[ficha.nombre_cientifico] = nueva
                tareas.add_task(buscar_foto_de_especie, sb, especie_id, ficha.nombre_cientifico)
    except SupabaseError as e:
        raise error(502, "base_de_datos", "No pudimos guardar la especie. Intenta de nuevo.") from e

    candidatos = [
        {
            "especie_id": existentes.get(c.nombre_cientifico, {}).get("id"),
            "nombre_cientifico": c.nombre_cientifico,
            "nombre_comun": c.nombre_comun,
            "confianza": c.confianza,
        }
        for c in resultado.candidatos
    ]

    if resultado.problema != "ninguno" or ficha is None:
        estado = "no_identificada"
    elif especie_id is None or resultado.confianza < settings.confianza_minima:
        estado = "revisar"
    else:
        estado = "identificada"

    # 5. Guardar (cuenta para el límite aunque la foto no haya servido, porque sí se usó la IA).
    fila = {
        "usuario_id": usuario_id,
        "ruta_foto": datos.ruta_foto,
        "latitud": datos.latitud,
        "longitud": datos.longitud,
        "observada_en": (datos.observada_en or datetime.now(timezone.utc)).isoformat(),
        "especie_id": especie_id,
        "ia_confianza": round(resultado.confianza, 3),
        "ia_explicacion": resultado.explicacion,
        "ia_nombre_sugerido": f"{ficha.nombre_comun} ({ficha.nombre_cientifico})" if ficha else None,
        "ia_candidatos": candidatos,
        "ia_problema": None if resultado.problema == "ninguno" else resultado.problema,
        "estado": estado,
        "es_publica": estado in ("identificada", "revisar"),
    }
    try:
        observacion = await sb.guardar_observacion(fila)
    except SupabaseError as e:
        raise error(502, "base_de_datos", "No pudimos guardar el resultado. Intenta de nuevo.") from e

    return {"observacion": observacion, "restantes": max(0, settings.limite_diario - len(usadas) - 1)}


async def buscar_foto_de_especie(sb: Supabase, especie_id: int, nombre_cientifico: str) -> None:
    """Se ejecuta después de responder: busca una foto de referencia para la especie nueva."""
    try:
        foto = await fotos_especies.buscar_foto(sb.http, nombre_cientifico)
        if foto:
            await sb.poner_imagen(especie_id, foto[0], foto[1])
    except Exception:  # una foto que falta nunca debe romper nada; la app muestra el icono del grupo
        log.info("No se pudo obtener foto para %s", nombre_cientifico, exc_info=True)
