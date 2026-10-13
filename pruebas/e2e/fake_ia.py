"""Servidor falso de la API de Google Gemini para pruebas: responde con el escenario que fije la prueba.
Así se prueba la cadena completa (app -> API Python -> Gemini) sin usar claves ni cuota."""
import json

from fastapi import FastAPI, Request

app = FastAPI()
estado = {"resultado": None, "peticiones": []}


@app.post("/_escenario")
async def escenario(request: Request):
    estado["resultado"] = await request.json()
    return {"ok": True}


@app.get("/_peticiones")
async def peticiones():
    return estado["peticiones"]


@app.post("/v1beta/models/{modelo}")
async def generar(modelo: str, request: Request):
    body = await request.json()
    img = body["contents"][0]["parts"][0]["inlineData"]
    estado["peticiones"].append({
        "model": modelo.split(":")[0], "media_type": img["mimeType"], "bytes_b64": len(img["data"]),
        "largo_instrucciones": len(body["systemInstruction"]["parts"][0]["text"]),
        "razonamiento": body["generationConfig"].get("thinkingConfig"),
        "pista": body["contents"][0]["parts"][1]["text"],
    })
    return {"candidates": [{"content": {"role": "model", "parts": [{"text": json.dumps(estado["resultado"])}]}, "finishReason": "STOP"}]}
