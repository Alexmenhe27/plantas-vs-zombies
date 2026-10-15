"""Servidor falso de Claude (Anthropic) y de GBIF para las pruebas: responde con el escenario que fije la prueba.
Así se prueba la cadena completa (app -> API Python -> Claude, por partes) sin usar claves ni saldo.

- POST /v1/messages con "stream": responde por partes (SSE), con una pausa entre trozos para ver el streaming.
- POST /v1/messages sin "stream": la ficha de una especie nueva.
- GET /gbif/species/match: acepta cualquier "Género especie"; un "Género sp." no es especie.
"""
import asyncio
import json

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse

app = FastAPI()
estado = {"resultado": None, "ficha": None, "pausa": 0.05, "error": None, "peticiones": []}
FICHA = {"descripcion": "Especie de prueba con una ficha escrita por la IA falsa.", "habitat": "Bosques y ciudades",
         "alimentacion": "Insectos y frutos", "tamano": "20 a 25 cm", "familia": None, "categoria_nom059": None, "introducida": False}


@app.post("/_escenario")
async def escenario(request: Request):
    """Fija la respuesta de la IA. Opcionales: "_ficha" (respuesta de la ficha), "_pausa" (segundos entre trozos), "_error"."""
    datos = await request.json()
    estado["ficha"] = datos.pop("_ficha", None)
    estado["pausa"] = datos.pop("_pausa", 0.05)
    estado["error"] = datos.pop("_error", None)
    estado["resultado"] = datos
    return {"ok": True}


@app.get("/_peticiones")
async def peticiones():
    return estado["peticiones"]


def _sse(evento: str, datos: dict) -> bytes:
    return f"event: {evento}\ndata: {json.dumps(datos)}\n\n".encode()


@app.post("/v1/messages")
async def mensajes(request: Request):
    body = await request.json()
    contenido = body["messages"][0]["content"]
    if not body.get("stream"):  # ficha de una especie nueva (solo texto)
        estado["peticiones"].append({"tipo": "ficha", "texto": contenido, "model": body["model"]})
        texto = json.dumps(estado["ficha"] or FICHA)
        return {"id": "msg_ficha", "type": "message", "role": "assistant", "model": body["model"],
                "content": [{"type": "text", "text": texto}], "stop_reason": "end_turn", "stop_sequence": None,
                "usage": {"input_tokens": 300, "output_tokens": 150}}

    img, texto = contenido
    estado["peticiones"].append({
        "tipo": "identificar", "model": body["model"], "media_type": img["source"]["media_type"], "bytes_b64": len(img["source"]["data"]),
        "largo_instrucciones": len(json.dumps(body["system"])), "razonamiento": body.get("output_config", {}).get("effort"),
        "thinking": body.get("thinking"), "formato": body.get("output_config", {}).get("format", {}).get("type"),
        "clave": request.headers.get("x-api-key"), "pista": texto["text"], "cache": "cache_control" in json.dumps(body["system"]),
    })
    if estado["error"]:
        return JSONResponse({"type": "error", "error": {"type": "overloaded_error", "message": estado["error"]}}, status_code=529)
    respuesta = json.dumps(estado["resultado"], ensure_ascii=False)
    pausa = estado["pausa"]

    async def eventos():
        yield _sse("message_start", {"type": "message_start", "message": {
            "id": "msg_e2e", "type": "message", "role": "assistant", "model": body["model"], "content": [],
            "stop_reason": None, "stop_sequence": None, "usage": {"input_tokens": 1500, "output_tokens": 1}}})
        yield _sse("content_block_start", {"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": ""}})
        for i in range(0, len(respuesta), 18):
            await asyncio.sleep(pausa)
            yield _sse("content_block_delta", {"type": "content_block_delta", "index": 0,
                                               "delta": {"type": "text_delta", "text": respuesta[i:i + 18]}})
        yield _sse("content_block_stop", {"type": "content_block_stop", "index": 0})
        yield _sse("message_delta", {"type": "message_delta", "delta": {"stop_reason": "end_turn", "stop_sequence": None},
                                     "usage": {"output_tokens": 300}})
        yield _sse("message_stop", {"type": "message_stop"})

    return StreamingResponse(eventos(), media_type="text/event-stream")


@app.get("/gbif/species/match")
async def gbif(name: str, kingdom: str | None = None):
    if name.endswith(" sp.") or " " not in name.strip():
        return {"matchType": "HIGHERRANK", "rank": "GENUS", "confidence": 94, "canonicalName": name.split(" ")[0]}
    return {"matchType": "EXACT", "confidence": 98, "rank": "SPECIES", "status": "ACCEPTED", "canonicalName": name,
            "usageKey": abs(hash(name)) % 10_000_000, "family": "Familia de prueba", "kingdom": kingdom or "Animalia"}
