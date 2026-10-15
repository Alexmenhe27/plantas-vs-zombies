"""El recorrido de una identificación, de la foto guardada al resultado, como una serie de eventos.

1. preparar(): revisa que la foto sea de la persona, reserva su lugar del límite diario y descarga la foto
   (las dos cosas al mismo tiempo). Si algo falla aquí, se responde con un error HTTP normal.
2. iniciar(): hace el resto en segundo plano (sigue aunque la persona cierre la app: el resultado se guarda igual)
   y devuelve una cola de eventos:
     parcial    lo que Claude ya escribió (nombre, confianza...), para mostrarlo sin esperar al final
     resultado  la observación guardada
     ficha      la ficha de una especie nueva, cuando está lista (puede llegar dos veces: texto y luego foto)
     error      si la IA o la base de datos fallaron (el lugar del límite se devuelve)
     fin        con los tiempos de cada paso
   Mientras Claude escribe, el nombre ya se valida en GBIF, así que validar no suma tiempo.
"""
import asyncio
import hashlib
import logging
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass

from . import fotos_especies, ia, taxonomia
from .config import settings
from .sesion import Usuario
from .supabase_client import Supabase, SupabaseError

log = logging.getLogger("api")

SIN_VALIDAR = object()  # GBIF no respondió a tiempo: la especie nueva se agrega sin validar
MENSAJE_IA_GENERICO = "El servicio de identificación no está disponible en este momento. Intenta de nuevo en unos minutos."
_TAREAS: set[asyncio.Task] = set()  # trabajos en segundo plano (se guardan para que no se pierdan)
_FICHAS_EN_CURSO: set[int] = set()


class ErrorAPI(Exception):
    def __init__(self, status: int, codigo: str, mensaje: str, **extra):
        super().__init__(mensaje)
        self.status, self.codigo, self.mensaje, self.extra = status, codigo, mensaje, extra


class Cronometro:
    """Mide cada paso en milisegundos (para la terminal de la API y la cabecera Server-Timing)."""

    def __init__(self):
        self.inicio = self.ultimo = time.monotonic()
        self.pasos: dict[str, int] = {}

    def marca(self, paso: str) -> None:
        ahora = time.monotonic()
        self.pasos[paso] = round((ahora - self.ultimo) * 1000)
        self.ultimo = ahora

    def momento(self, nombre: str) -> None:
        """Tiempo desde el inicio hasta algo que pasó a la mitad de un paso (por ejemplo, cuando llegó el nombre)."""
        self.pasos.setdefault(nombre, round((time.monotonic() - self.inicio) * 1000))

    def total(self) -> int:
        return round((time.monotonic() - self.inicio) * 1000)

    def server_timing(self) -> str:
        return ", ".join(f"{k};dur={v}" for k, v in {**self.pasos, "total": self.total()}.items())

    def resumen(self) -> str:
        return " · ".join(f"{k} {v} ms" for k, v in self.pasos.items())


@dataclass
class Preparada:
    usuario: Usuario
    ruta_foto: str
    latitud: float | None
    longitud: float | None
    observada_en: str | None
    foto: bytes
    tipo: str
    reserva: int | None
    restantes: int
    limite: int
    tiempos: Cronometro


def huella_red(ip: str | None) -> str | None:
    """Huella anónima de la IP (no se puede revertir); solo para limitar a los invitados por red."""
    if not ip:
        return None
    return hashlib.sha256(settings.sal() + ip.encode()).hexdigest()[:32]


def _error_de_limite(r: dict) -> ErrorAPI:
    motivo = r.get("motivo")
    if motivo == "limite_global":
        return ErrorAPI(503, "servicio_saturado",
                        "Hoy hubo muchísimas identificaciones y el servicio se pausó para cuidar los costos. Intenta más tarde.")
    if motivo == "sin_usuario":
        return ErrorAPI(401, "sin_sesion", "Tu sesión expiró. Vuelve a iniciar sesión.")
    extra = {"disponible_en": r.get("disponible_en"), "limite": r.get("limite"), "invitado": bool(r.get("invitado"))}
    if motivo == "limite_red":
        return ErrorAPI(429, "limite_diario", "Se alcanzó el límite de identificaciones sin cuenta desde esta red. "
                                              "Crea tu cuenta gratis para seguir identificando.", **extra)
    if r.get("invitado"):
        return ErrorAPI(429, "limite_diario", f"Sin cuenta puedes hacer {r.get('limite')} identificaciones al día. "
                                              "Crea tu cuenta gratis para tener más.", **extra)
    return ErrorAPI(429, "limite_diario", f"Llegaste al límite de {r.get('limite')} identificaciones de hoy.", **extra)


async def _liberar(sb: Supabase, reserva: int | None) -> None:
    if reserva is None:
        return
    try:
        await sb.liberar(reserva)
    except Exception as e:  # devolver el lugar nunca debe romper la respuesta
        log.warning("No se pudo devolver el lugar del límite (reserva %s): %r", reserva, e)


async def preparar(sb: Supabase, usuario: Usuario, ruta_foto: str, latitud: float | None, longitud: float | None,
                   observada_en: str | None, ip: str | None) -> Preparada:
    tiempos = Cronometro()
    # La foto debe estar en la carpeta del propio usuario.
    if not ruta_foto.startswith(f"{usuario.id}/") or ".." in ruta_foto:
        raise ErrorAPI(403, "foto_ajena", "Esa foto no es tuya.")
    red = huella_red(ip) if usuario.es_invitado else None
    reserva, foto = await asyncio.gather(sb.reservar(usuario.id, red), sb.descargar_foto(ruta_foto), return_exceptions=True)
    tiempos.marca("preparar")
    reservada = reserva.get("reserva") if isinstance(reserva, dict) and reserva.get("ok") else None
    if isinstance(reserva, BaseException) or isinstance(foto, BaseException):
        await _liberar(sb, reservada)
        error = reserva if isinstance(reserva, BaseException) else foto
        if isinstance(error, SupabaseError):
            raise ErrorAPI(502, "base_de_datos", "No pudimos conectar con la base de datos. Intenta de nuevo.") from error
        raise error
    if reservada is None and not reserva.get("sin_limite"):
        raise _error_de_limite(reserva)
    if foto is None:
        await _liberar(sb, reservada)
        raise ErrorAPI(404, "foto_no_encontrada", "No encontramos la foto. Vuelve a subirla.")
    return Preparada(usuario, ruta_foto, latitud, longitud, observada_en, foto[0], foto[1], reservada,
                     int(reserva.get("restantes", 0)), int(reserva.get("limite", 0)), tiempos)


def iniciar(sb: Supabase, p: Preparada) -> asyncio.Queue:
    """Arranca la identificación en segundo plano y devuelve la cola de eventos (termina con None)."""
    cola: asyncio.Queue = asyncio.Queue()
    _en_segundo_plano(_procesar(sb, p, cola))
    return cola


async def eventos(cola: asyncio.Queue) -> AsyncIterator[dict]:
    while (evento := await cola.get()) is not None:
        yield evento


def _en_segundo_plano(corrutina) -> asyncio.Task:
    tarea = asyncio.create_task(corrutina)
    _TAREAS.add(tarea)
    tarea.add_done_callback(_TAREAS.discard)
    return tarea


async def _validar(sb: Supabase, nombre: str, reino: str | None):
    try:
        return await taxonomia.validar(sb.http, nombre, reino)
    except taxonomia.GBIFNoDisponible as e:
        log.info("GBIF no disponible para %s: %s", nombre, e)
        return SIN_VALIDAR


async def _procesar(sb: Supabase, p: Preparada, cola: asyncio.Queue) -> None:
    t = p.tiempos
    validacion: dict = {}  # {"clave": (nombre, reino), "tarea": Task}

    def validar_en_paralelo(nombre: str, reino: str | None) -> asyncio.Task:
        if validacion.get("clave") != (nombre, reino):
            validacion.update(clave=(nombre, reino), tarea=asyncio.create_task(_validar(sb, nombre, reino)))
        return validacion["tarea"]

    async def al_avanzar(campos: dict) -> None:
        if campos.get("nombre_comun"):
            t.momento("nombre_visible")
        await cola.put({"tipo": "parcial", **campos})
        if campos.get("problema") == "ninguno" and campos.get("nombre_cientifico") and campos.get("reino"):
            validar_en_paralelo(campos["nombre_cientifico"], campos["reino"])

    guardado = False
    try:
        try:
            r = await ia.identificar(p.foto, p.tipo, p.latitud, p.longitud, al_avanzar)
        except ia.IAError as e:
            # La causa técnica se escribe en la terminal de la API; la persona ve un mensaje claro.
            log.warning("Fallo al identificar con Claude: %s", e.detalle)
            await _liberar(sb, p.reserva)
            # En producción no se le muestran a la persona pistas técnicas (claves, api/.env...): solo en la terminal.
            mensaje = MENSAJE_IA_GENERICO if settings.produccion else str(e)
            await cola.put({"tipo": "error", "codigo": "ia_no_disponible", "mensaje": mensaje})
            return
        t.marca("ia")

        datos = {
            "usuario_id": p.usuario.id, "ruta_foto": p.ruta_foto, "latitud": p.latitud, "longitud": p.longitud,
            "observada_en": p.observada_en, "problema": r.problema, "confianza": r.confianza, "explicacion": r.explicacion,
            "candidatos": [c.model_dump() for c in r.candidatos], "nombres": [], "nombre_sugerido": None, "nueva_especie": None,
            "confianza_minima": settings.confianza_minima, "confianza_para_catalogo": settings.confianza_para_catalogo,
        }
        if r.tiene_especie:
            nombre = r.nombre_cientifico
            try:
                taxon = await asyncio.wait_for(asyncio.shield(validar_en_paralelo(nombre, r.reino)), settings.gbif_tiempo_maximo)
            except TimeoutError:
                taxon = SIN_VALIDAR
            datos["nombres"] = [nombre]
            nueva = {"nombre_cientifico": nombre, "nombre_comun": r.nombre_comun, "reino": r.reino, "grupo": r.grupo,
                     "familia": None, "gbif_id": None}
            if taxon is None:
                nueva = None  # GBIF no la reconoce como especie (un género, un nombre inventado): no entra al catálogo
            elif taxon is not SIN_VALIDAR:
                nueva.update(nombre_cientifico=taxon.nombre, familia=taxon.familia, gbif_id=taxon.gbif_id)
                if taxon.nombre != nombre:  # sinónimo: se busca y se guarda con el nombre aceptado
                    datos["nombres"].append(taxon.nombre)
                    for c in datos["candidatos"]:
                        if c["nombre_cientifico"] == nombre:
                            c["nombre_cientifico"] = taxon.nombre
                    nombre = taxon.nombre
            datos["nueva_especie"] = nueva
            datos["nombre_sugerido"] = f"{r.nombre_comun} ({nombre})"
        t.marca("validar")

        try:
            g = await sb.guardar_identificacion(p.reserva, datos)
        except SupabaseError as e:
            log.warning("No se pudo guardar la identificación: %s", e)
            await _liberar(sb, p.reserva)
            await cola.put({"tipo": "error", "codigo": "base_de_datos", "mensaje": "No pudimos guardar el resultado. Intenta de nuevo."})
            return
        guardado = True
        t.marca("guardar")

        obs = g["observacion"]
        especie = obs.get("especie")
        falta_texto = bool(especie) and not especie.get("descripcion")
        falta_algo = falta_texto or (bool(especie) and not especie.get("imagen_url"))
        await cola.put({
            "tipo": "resultado", "observacion": obs, "restantes": p.restantes, "limite": p.limite,
            "candidatos_especies": g.get("candidatos_especies") or [], "ficha_pendiente": falta_texto,
        })
        if falta_algo:
            async for completa in completar_especie(sb, especie):
                await cola.put({"tipo": "ficha", "especie": completa})
            t.marca("ficha")
        log.info("Identificación de %s en %.1f s · %s", obs.get("ia_nombre_sugerido") or obs.get("estado"),
                 t.total() / 1000, t.resumen())
        await cola.put({"tipo": "fin", "tiempos": {**t.pasos, "total": t.total()}})
    except Exception:
        log.exception("Error inesperado al identificar")
        if not guardado:
            await _liberar(sb, p.reserva)
        await cola.put({"tipo": "error", "codigo": "error_interno", "mensaje": "Ocurrió un error en el servidor. Intenta de nuevo."})
    finally:
        tarea = validacion.get("tarea")
        if tarea and not tarea.done():
            tarea.cancel()
        await cola.put(None)


async def completar_especie(sb: Supabase, especie: dict) -> AsyncIterator[dict]:
    """Escribe la ficha (con la IA) y busca la foto de referencia de una especie que no las tiene.
    Devuelve la especie actualizada después de cada paso. Nunca lanza errores: lo que falte se intentará otra vez."""
    eid = especie["id"]
    if eid in _FICHAS_EN_CURSO:
        return
    _FICHAS_EN_CURSO.add(eid)
    actual = dict(especie)
    try:
        if not actual.get("descripcion"):
            try:
                ficha = await ia.escribir_ficha(actual["nombre_cientifico"], actual["nombre_comun"], actual["reino"], actual["grupo"])
                campos = ficha.model_dump()
                if actual.get("familia"):  # la de GBIF es más confiable
                    campos["familia"] = actual["familia"]
                campos["protegida"] = ficha.categoria_nom059 is not None
                guardada = await sb.completar_especie(eid, campos)
                if guardada:
                    actual = {**actual, **guardada}
                    yield actual
            except ia.IAError as e:
                log.warning("No se pudo escribir la ficha de %s: %s", actual["nombre_cientifico"], e.detalle)
        if not actual.get("imagen_url"):
            foto = await fotos_especies.buscar_foto(sb.http, actual["nombre_cientifico"])
            if foto:
                await sb.poner_imagen(eid, foto[0], foto[1])
                actual = {**actual, "imagen_url": foto[0], "imagen_fuente": foto[1]}
                yield actual
    except SupabaseError as e:
        log.warning("No se pudo completar la especie %s: %s", actual.get("nombre_cientifico"), e)
    finally:
        _FICHAS_EN_CURSO.discard(eid)


async def _completar_en_segundo_plano(sb: Supabase, especie: dict) -> None:
    async for _ in completar_especie(sb, especie):
        pass


async def elegir(sb: Supabase, usuario: Usuario, observacion_id: str, nombre_cientifico: str) -> dict:
    """La persona elige cuál de las especies parecidas es la de su foto (solo si la IA no estaba segura)."""
    obs = await sb.observacion(observacion_id)
    if not obs or obs["usuario_id"] != usuario.id:
        raise ErrorAPI(404, "no_encontrada", "No encontramos esa observación.")
    if obs["estado"] != "revisar":
        raise ErrorAPI(409, "no_en_revision", "Esta observación ya no está en revisión.")
    nombre = taxonomia.normalizar_nombre(nombre_cientifico)
    candidato = next((c for c in obs.get("ia_candidatos") or []
                      if taxonomia.normalizar_nombre(c.get("nombre_cientifico") or "") == nombre), None)
    if candidato is None:
        raise ErrorAPI(400, "candidato_invalido", "Solo puedes elegir entre las especies parecidas que sugirió la IA.")

    especie_id = candidato.get("especie_id")
    if not especie_id:
        existentes = await sb.especies_por_nombre([nombre])
        especie = existentes.get(nombre)
        if especie is None:
            grupo = candidato.get("grupo")
            taxon = await _validar(sb, nombre, ia.reino_de(grupo))
            if taxon is None:
                raise ErrorAPI(400, "especie_desconocida",
                               "Esa especie no aparece en GBIF, así que no se puede agregar. Tu foto queda en revisión.")
            if taxon is not SIN_VALIDAR and taxon.nombre != nombre:
                especie = (await sb.especies_por_nombre([taxon.nombre])).get(taxon.nombre)
            if especie is None:
                validado = taxon if taxon is not SIN_VALIDAR else None
                grupo = grupo or (validado.grupo if validado else None) or "invertebrado"
                especie = await sb.crear_especie({
                    "nombre_cientifico": validado.nombre if validado else nombre,
                    "nombre_comun": candidato.get("nombre_comun") or nombre,
                    "reino": ia.reino_de(grupo) or (validado.reino if validado else None) or "animal",
                    "grupo": grupo, "familia": validado.familia if validado else None,
                    "gbif_id": validado.gbif_id if validado else None, "verificada": False,
                })
                _en_segundo_plano(_completar_en_segundo_plano(sb, especie))
        especie_id = especie["id"]
    return await sb.actualizar_observacion(observacion_id, {"especie_id": especie_id, "estado": "elegida"})
