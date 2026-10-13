"""Prueba el módulo de IA contra un servidor HTTP falso que imita la API de Gemini.
Así se comprueba la petición real que se arma y cómo se lee la respuesta, sin usar la clave."""
import asyncio
import dataclasses
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from app import ia

RECIBIDO = {}
RESPUESTA = {
    "problema": "ninguno",
    "especie": {
        "nombre_cientifico": "ara  MILITARIS", "nombre_comun": "Guacamaya verde", "reino": "animal", "grupo": "ave",
        "familia": "Psittacidae", "descripcion": "Loro grande y verde.", "habitat": "Cañones", "alimentacion": "Semillas",
        "tamano": "70 cm", "categoria_nom059": "P", "introducida": False,
    },
    "confianza": 0.93,
    "explicacion": "Plumaje verde con frente roja y cola larga.",
    "candidatos": [{"nombre_cientifico": "Ara militaris", "nombre_comun": "Guacamaya verde", "confianza": 0.93},
                   {"nombre_cientifico": "Ara militaris", "nombre_comun": "Repetida", "confianza": 0.5}],
}
MODO = {"status": 200, "cuerpo": None, "secuencia": [], "por_modelo": {}, "lento": set()}
PETICIONES = []


class FalsoGemini(BaseHTTPRequestHandler):
    def do_POST(self):
        cuerpo = self.rfile.read(int(self.headers["content-length"]))
        RECIBIDO.update(path=self.path, headers=dict(self.headers), body=json.loads(cuerpo))
        PETICIONES.append(json.loads(cuerpo))
        modelo = self.path.split("/models/")[1].split(":")[0]
        RECIBIDO.setdefault("modelos", []).append(modelo)
        if modelo in MODO["lento"]:
            time.sleep(2)
        if MODO["secuencia"]:  # respuestas distintas en cada intento
            MODO["status"], MODO["cuerpo"] = MODO["secuencia"].pop(0)
        status, cuerpo = MODO["por_modelo"].get(modelo, (MODO["status"], MODO["cuerpo"]))
        respuesta = cuerpo or {
            "candidates": [{"content": {"role": "model", "parts": [{"text": json.dumps(RESPUESTA)}]}, "finishReason": "STOP"}]
        }
        datos = json.dumps(respuesta).encode()
        self.send_response(status)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(datos)))
        self.end_headers()
        self.wfile.write(datos)

    def log_message(self, *args):
        pass


@pytest.fixture
def servidor(monkeypatch):
    MODO.update(status=200, cuerpo=None, secuencia=[], por_modelo={}, lento=set())
    PETICIONES.clear()
    RECIBIDO.clear()
    srv = HTTPServer(("127.0.0.1", 0), FalsoGemini)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    monkeypatch.setattr(ia, "settings", dataclasses.replace(ia.settings, ia_url=f"http://127.0.0.1:{srv.server_port}"))
    monkeypatch.setattr(ia, "_http", None)
    yield
    srv.shutdown()


def test_peticion_y_respuesta(servidor):
    r = asyncio.run(ia.identificar(b"\xff\xd8imagen", "image/jpeg", 19.04, -98.2))
    assert r.especie.nombre_cientifico == "Ara militaris"  # nombre normalizado
    assert r.confianza == 0.93 and r.especie.categoria_nom059 == "P"
    assert [c.nombre_comun for c in r.candidatos] == ["Guacamaya verde"]  # sin repetidos

    assert RECIBIDO["path"] == "/v1beta/models/gemini-prueba:generateContent"
    assert RECIBIDO["headers"]["x-goog-api-key"] == "clave-gemini-prueba"
    body = RECIBIDO["body"]
    assert body["generationConfig"]["responseMimeType"] == "application/json"
    assert body["generationConfig"]["thinkingConfig"] == {"thinkingLevel": "low"}
    assert body["generationConfig"]["responseSchema"]["required"][0] == "problema"
    img = body["contents"][0]["parts"][0]["inlineData"]
    assert img["mimeType"] == "image/jpeg"
    assert "latitud 19.04" in body["contents"][0]["parts"][1]["text"]
    assert len(body["systemInstruction"]["parts"][0]["text"]) < 3000  # sin catálogo: petición corta y rápida


def test_cuota_agotada(servidor):
    MODO.update(status=429, cuerpo={"error": {"code": 429, "status": "RESOURCE_EXHAUSTED"}})
    with pytest.raises(ia.IAError, match="cuota"):
        asyncio.run(ia.identificar(b"x", "image/jpeg"))
    assert RECIBIDO["modelos"] == ["gemini-prueba", "gemini-respaldo"]  # la cuota es por modelo: se prueba el de respaldo


def test_modelo_inexistente_usa_el_de_respaldo(servidor):
    MODO["por_modelo"] = {"gemini-prueba": (404, {"error": {"code": 404, "message": "models/gemini-prueba is not found"}})}
    r = asyncio.run(ia.identificar(b"x", "image/jpeg"))
    assert r.especie.nombre_cientifico == "Ara militaris"
    assert RECIBIDO["modelos"] == ["gemini-prueba", "gemini-respaldo"]


def test_modelo_lento_usa_el_de_respaldo(servidor, monkeypatch):
    monkeypatch.setattr(ia, "settings", dataclasses.replace(ia.settings, ia_tiempo_maximo=1, ia_tiempo_total=20))
    MODO["lento"] = {"gemini-prueba"}
    r = asyncio.run(ia.identificar(b"x", "image/jpeg"))
    assert r.especie.nombre_cientifico == "Ara militaris"
    assert RECIBIDO["modelos"] == ["gemini-prueba", "gemini-respaldo"]


def test_clave_invalida_no_prueba_mas_modelos(servidor):
    MODO.update(status=400, cuerpo={"error": {"code": 400, "message": "API key not valid. Please pass a valid API key."}})
    with pytest.raises(ia.IAError, match="clave de Gemini"):
        asyncio.run(ia.identificar(b"x", "image/jpeg"))
    assert RECIBIDO["modelos"] == ["gemini-prueba"]


def test_razonamiento_segun_el_modelo():
    assert ia._ajuste_de_razonamiento("gemini-3.8-flash") == {"thinkingLevel": "low"}
    assert ia._ajuste_de_razonamiento("gemini-2.5-flash") == {"thinkingBudget": 0}
    assert ia._ajuste_de_razonamiento("gemini-2.0-flash") is None


def test_foto_bloqueada_se_guarda_como_no_identificada(servidor):
    MODO.update(cuerpo={"promptFeedback": {"blockReason": "SAFETY"}})
    r = asyncio.run(ia.identificar(b"x", "image/jpeg"))
    assert r.especie is None and r.problema == "sin_organismo"


@pytest.mark.parametrize(
    "status, cuerpo, esperado",
    [
        (400, {"error": {"code": 400, "message": "API key not valid. Please pass a valid API key.", "status": "INVALID_ARGUMENT"}}, "clave de Gemini"),
        (403, {"error": {"code": 403, "message": "Permission denied", "status": "PERMISSION_DENIED"}}, "clave de Gemini"),
        (404, {"error": {"code": 404, "message": "models/x is not found", "status": "NOT_FOUND"}}, "IA_MODELO"),
        (503, {"error": {"code": 503, "message": "The model is overloaded.", "status": "UNAVAILABLE"}}, "saturado"),
    ],
)
def test_errores_de_gemini_explican_la_causa(servidor, status, cuerpo, esperado):
    MODO.update(status=status, cuerpo=cuerpo)
    with pytest.raises(ia.IAError, match=esperado) as e:
        asyncio.run(ia.identificar(b"x", "image/jpeg"))
    assert str(status) in e.value.detalle  # lo técnico queda para la terminal de la API


def test_sin_conexion_a_gemini(monkeypatch):
    monkeypatch.setattr(ia, "settings", dataclasses.replace(ia.settings, ia_url="http://127.0.0.1:9"))
    monkeypatch.setattr(ia, "_http", None)
    with pytest.raises(ia.IAError, match="no pudo conectarse a Gemini"):
        asyncio.run(ia.identificar(b"x", "image/jpeg"))


def test_si_el_modelo_no_acepta_thinking_se_repite_sin_el(servidor):
    MODO["secuencia"] = [(400, {"error": {"code": 400, "message": "thinking_level is not supported for this model"}}), (200, None)]
    r = asyncio.run(ia.identificar(b"x", "image/jpeg"))
    assert r.especie.nombre_cientifico == "Ara militaris"
    assert "thinkingConfig" in PETICIONES[0]["generationConfig"] and "thinkingConfig" not in PETICIONES[1]["generationConfig"]


def test_gemini_saturado_se_reintenta_una_vez(servidor):
    MODO["secuencia"] = [(503, {"error": {"code": 503, "message": "overloaded"}}), (200, None)]
    r = asyncio.run(ia.identificar(b"x", "image/jpeg"))
    assert r.especie is not None and len(PETICIONES) == 2


def test_grupo_desconocido_y_planta_sin_alimentacion(servidor):
    MODO["cuerpo"] = {"candidates": [{"content": {"parts": [{"text": json.dumps({**RESPUESTA, "especie": {
        **RESPUESTA["especie"], "nombre_cientifico": "Quercus rugosa", "reino": "planta", "grupo": "liquen", "alimentacion": "sol"}})}]}}]}
    r = asyncio.run(ia.identificar(b"x", "image/jpeg"))
    assert r.especie.grupo == "planta" and r.especie.alimentacion is None
