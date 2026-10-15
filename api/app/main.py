"""API de identificación: POST /identificar, POST /observaciones/{id}/elegir, DELETE /cuenta y GET /salud."""
import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response, StreamingResponse
from pydantic import BaseModel, Field

from . import identificacion
from .config import settings
from .identificacion import ErrorAPI
from .sesion import Usuario, ValidadorSesion
from .supabase_client import Supabase, SupabaseError

log = logging.getLogger("api")
if not logging.getLogger().handlers:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s:     %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with httpx.AsyncClient(timeout=30) as http:
        app.state.supabase = Supabase(http)
        app.state.sesiones = ValidadorSesion(app.state.supabase)
        yield


app = FastAPI(title="API de identificación de especies", version="0.2.0", lifespan=lifespan)


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
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "Accept"],
    expose_headers=["Server-Timing"],
)


def error(status: int, codigo: str, mensaje: str, **extra) -> HTTPException:
    return HTTPException(status_code=status, detail={"codigo": codigo, "mensaje": mensaje, **extra})


@app.exception_handler(ErrorAPI)
async def _error_api(request: Request, e: ErrorAPI):
    return JSONResponse(status_code=e.status, content={"detail": {"codigo": e.codigo, "mensaje": e.mensaje, **e.extra}})


@app.exception_handler(SupabaseError)
async def _error_supabase(request: Request, e: SupabaseError):
    log.warning("Supabase falló en %s: %s", request.url.path, e)
    return JSONResponse(status_code=502, content={"detail": {
        "codigo": "base_de_datos", "mensaje": "No pudimos conectar con la base de datos. Intenta de nuevo."}})


def supabase(request: Request) -> Supabase:
    return request.app.state.supabase


async def usuario_actual(request: Request, authorization: str = Header(default="")) -> Usuario:
    faltan = settings.faltantes()
    if faltan:
        # Sin esto, una URL vacía hacía fallar la petición a Supabase y el navegador lo mostraba como "sin internet".
        log.error("Faltan variables de configuración: %s", ", ".join(faltan))
        raise error(
            503, "configuracion_incompleta",
            "El servicio no está disponible en este momento." if settings.produccion else
            "La API no está configurada: faltan " + ", ".join(faltan) + " en el archivo api/.env. Agrégalas y reinicia la API.",
        )
    if not authorization.lower().startswith("bearer "):
        raise error(401, "sin_sesion", "Inicia sesión para identificar especies.")
    usuario = await request.app.state.sesiones.validar(authorization[7:].strip())
    if not usuario:
        raise error(401, "sin_sesion", "Tu sesión expiró. Vuelve a iniciar sesión.")
    return usuario


class PeticionIdentificar(BaseModel):
    ruta_foto: str = Field(min_length=3, max_length=300)
    latitud: float | None = Field(default=None, ge=-90, le=90)
    longitud: float | None = Field(default=None, ge=-180, le=180)
    observada_en: datetime | None = None


class PeticionElegir(BaseModel):
    nombre_cientifico: str = Field(min_length=3, max_length=200)


@app.get("/salud")
async def salud():
    faltan = settings.faltantes()
    return {"estado": "ok" if not faltan else "incompleto", "faltan_variables": faltan, "ia": "claude",
            "modelo": settings.ia_modelo, "razonamiento": settings.ia_razonamiento, "gbif": bool(settings.gbif_url)}


async def _ndjson(cola):
    async for evento in identificacion.eventos(cola):
        yield (json.dumps(evento, ensure_ascii=False, default=str) + "\n").encode()


@app.post("/identificar")
async def identificar(
    datos: PeticionIdentificar,
    request: Request,
    usuario: Usuario = Depends(usuario_actual),
    sb: Supabase = Depends(supabase),
):
    """Con `Accept: application/x-ndjson` responde por partes (un evento JSON por línea, ver identificacion.py).
    Sin esa cabecera espera el resultado y responde un solo JSON (scripts y versiones anteriores de la app)."""
    preparada = await identificacion.preparar(
        sb, usuario, datos.ruta_foto, datos.latitud, datos.longitud,
        datos.observada_en.isoformat() if datos.observada_en else None,
        request.client.host if request.client else None,
    )
    cola = identificacion.iniciar(sb, preparada)
    if "application/x-ndjson" in request.headers.get("accept", ""):
        return StreamingResponse(_ndjson(cola), media_type="application/x-ndjson",
                                 headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"})
    async for evento in identificacion.eventos(cola):
        if evento["tipo"] == "resultado":
            cuerpo = {k: v for k, v in evento.items() if k != "tipo"}
            return JSONResponse(cuerpo, headers={"Server-Timing": preparada.tiempos.server_timing()})
        if evento["tipo"] == "error":
            status = 500 if evento["codigo"] == "error_interno" else 502
            raise error(status, evento["codigo"], evento["mensaje"])
    raise error(500, "error_interno", "Ocurrió un error en el servidor. Intenta de nuevo.")


@app.post("/observaciones/{observacion_id}/elegir")
async def elegir(
    observacion_id: str,
    datos: PeticionElegir,
    usuario: Usuario = Depends(usuario_actual),
    sb: Supabase = Depends(supabase),
):
    """Cuando la IA no estaba segura, la persona elige cuál de las especies parecidas es la de su foto."""
    observacion = await identificacion.elegir(sb, usuario, observacion_id, datos.nombre_cientifico)
    return {"observacion": observacion}
