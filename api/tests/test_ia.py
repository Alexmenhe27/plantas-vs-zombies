"""Prueba el módulo de IA contra un servidor HTTP falso que imita la API de Claude (también por partes, con streaming).
Así se comprueba la petición real que arma el paquete anthropic y cómo se lee la respuesta, sin usar la clave."""
import asyncio
import dataclasses
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from app import ia

RECIBIDO = {}
RESPUESTA = {
    "problema": "ninguno",
    "nombre_comun": "Guacamaya verde",
    "nombre_cientifico": "ara  MILITARIS",
    "reino": "animal",
    "grupo": "ave",
    "confianza": 0.93,
    "candidatos": [{"nombre_cientifico": "Ara militaris", "nombre_comun": "Guacamaya verde", "grupo": "ave", "confianza": 0.93},
                   {"nombre_cientifico": "Ara militaris", "nombre_comun": "Repetida", "grupo": "ave", "confianza": 0.5},
                   {"nombre_cientifico": "Ara macao", "nombre_comun": "Guacamaya roja", "grupo": "liquen", "confianza": 0.04}],
    "explicacion": "Plumaje verde con frente roja y cola larga.",
}
FICHA = {"descripcion": "Loro grande y verde.", "habitat": "Cañones", "alimentacion": "Semillas", "tamano": "70 cm",
         "familia": "Psittacidae", "categoria_nom059": "P", "introducida": False}


def mensaje(texto, stop_reason="end_turn"):
    return {
        "id": "msg_prueba", "type": "message", "role": "assistant", "model": "claude-haiku-5-5",
        "content": [{"type": "thinking", "thinking": "", "signature": "firma"}, {"type": "text", "text": texto}],
        "stop_reason": stop_reason, "stop_sequence": None, "usage": {"input_tokens": 1500, "output_tokens": 300},
    }


def eventos_sse(texto, stop_reason="end_turn", trozo=12):
    """La misma respuesta, como la manda Claude por streaming: primero un bloque de razonamiento y luego el texto en trozos."""
    ev = [
        ("message_start", {"type": "message_start", "message": {
            "id": "msg_prueba", "type": "message", "role": "assistant", "model": "claude-haiku-5-5", "content": [],
            "stop_reason": None, "stop_sequence": None, "usage": {"input_tokens": 1500, "output_tokens": 1}}}),
        ("content_block_start", {"type": "content_block_start", "index": 0,
                                 "content_block": {"type": "thinking", "thinking": "", "signature": ""}}),
        ("content_block_delta", {"type": "content_block_delta", "index": 0, "delta": {"type": "signature_delta", "signature": "firma"}}),
        ("content_block_stop", {"type": "content_block_stop", "index": 0}),
        ("content_block_start", {"type": "content_block_start", "index": 1, "content_block": {"type": "text", "text": ""}}),
    ]
    for i in range(0, len(texto), trozo):
        ev.append(("content_block_delta", {"type": "content_block_delta", "index": 1,
                                           "delta": {"type": "text_delta", "text": texto[i:i + trozo]}}))
    ev += [
        ("content_block_stop", {"type": "content_block_stop", "index": 1}),
        ("message_delta", {"type": "message_delta", "delta": {"stop_reason": stop_reason, "stop_sequence": None},
                           "usage": {"output_tokens": 300}}),
        ("message_stop", {"type": "message_stop"}),
    ]
    return "".join(f"event: {e}\ndata: {json.dumps(d)}\n\n" for e, d in ev).encode()


def error(tipo, texto):
    return {"type": "error", "error": {"type": tipo, "message": texto}}


MODO = {"status": 200, "cuerpo": None, "texto": None, "stop_reason": "end_turn", "secuencia": []}
PETICIONES = []


class FalsoClaude(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def do_POST(self):
        cuerpo = json.loads(self.rfile.read(int(self.headers["content-length"])))
        RECIBIDO.update(path=self.path, headers={k.lower(): v for k, v in self.headers.items()}, body=cuerpo)
        PETICIONES.append(cuerpo)
        if MODO["secuencia"]:  # respuestas distintas en cada intento
            MODO["status"], MODO["cuerpo"] = MODO["secuencia"].pop(0)
        if MODO["status"] != 200:
            self._enviar(MODO["status"], "application/json", json.dumps(MODO["cuerpo"]).encode())
        elif cuerpo.get("stream"):
            texto = MODO["texto"] if MODO["texto"] is not None else json.dumps(RESPUESTA)
            self._enviar(200, "text/event-stream", eventos_sse(texto, MODO["stop_reason"]))
        else:
            self._enviar(200, "application/json", json.dumps(MODO["cuerpo"] or mensaje(json.dumps(FICHA))).encode())

    def _enviar(self, status, tipo, datos):
        self.send_response(status)
        self.send_header("content-type", tipo)
        self.send_header("content-length", str(len(datos)))
        self.end_headers()
        self.wfile.write(datos)

    def log_message(self, *args):
        pass


@pytest.fixture
def servidor(monkeypatch):
    MODO.update(status=200, cuerpo=None, texto=None, stop_reason="end_turn", secuencia=[])
    PETICIONES.clear()
    srv = ThreadingHTTPServer(("127.0.0.1", 0), FalsoClaude)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    monkeypatch.setattr(ia, "settings", dataclasses.replace(ia.settings, ia_url=f"http://127.0.0.1:{srv.server_port}",
                                                            ia_razonamiento="bajo"))
    monkeypatch.setattr(ia, "_cliente", None)
    yield
    srv.shutdown()


def test_peticion_y_respuesta(servidor):
    r = asyncio.run(ia.identificar(b"\xff\xd8imagen", "image/jpeg", 19.04, -98.2))
    assert r.nombre_cientifico == "Ara militaris"  # nombre normalizado
    assert r.confianza == 0.93 and r.reino == "animal" and r.grupo == "ave"
    assert [c.nombre_comun for c in r.candidatos] == ["Guacamaya verde", "Guacamaya roja"]  # sin repetidos
    assert r.candidatos[1].grupo is None  # grupo inexistente
    assert r.uso["output_tokens"] == 300

    assert RECIBIDO["path"] == "/v1/messages"
    assert RECIBIDO["headers"]["x-api-key"] == "sk-ant-prueba" and "anthropic-version" in RECIBIDO["headers"]
    assert "anthropic-workspace-id" not in RECIBIDO["headers"]
    body = RECIBIDO["body"]
    assert body["model"] == "claude-haiku-5-5" and body["stream"] is True
    assert body["output_config"]["effort"] == "low"
    assert body["output_config"]["format"]["type"] == "json_schema"
    assert "thinking" not in body  # razonamiento "bajo": adaptativo, el que trae el modelo
    assert body["system"] == [{"type": "text", "text": ia.SISTEMA, "cache_control": {"type": "ephemeral"}}]
    assert len(ia.SISTEMA) < 3000  # instrucciones cortas: petición rápida
    img, texto = body["messages"][0]["content"]
    assert img["source"] == {"type": "base64", "media_type": "image/jpeg", "data": "/9hpbWFnZW4="}
    assert "latitud 19.04" in texto["text"]


def test_avisa_el_nombre_antes_de_terminar(servidor):
    avisos = []

    async def al_avanzar(campos):
        avisos.append(campos)

    r = asyncio.run(ia.identificar(b"x", "image/jpeg", al_avanzar=al_avanzar))
    con_nombre = next(i for i, a in enumerate(avisos) if a.get("nombre_cientifico"))
    con_explicacion = next(i for i, a in enumerate(avisos) if a.get("explicacion"))
    assert avisos[con_nombre]["nombre_cientifico"] == "Ara militaris"
    assert con_nombre < con_explicacion  # el nombre llega antes que el resto
    assert avisos[-1]["confianza"] == 0.93 and avisos[-1]["explicacion"] == r.explicacion


def test_sin_razonamiento(servidor, monkeypatch):
    monkeypatch.setattr(ia, "settings", dataclasses.replace(ia.settings, ia_razonamiento="sin"))
    asyncio.run(ia.identificar(b"x", "image/jpeg"))
    assert RECIBIDO["body"]["thinking"] == {"type": "disabled"}


def test_espacio_de_trabajo_opcional(servidor, monkeypatch):
    monkeypatch.setattr(ia, "settings", dataclasses.replace(ia.settings, anthropic_workspace_id="wrkspc_prueba"))
    asyncio.run(ia.identificar(b"x", "image/jpeg"))
    assert RECIBIDO["headers"]["anthropic-workspace-id"] == "wrkspc_prueba"


@pytest.mark.parametrize("esquema", [ia.ESQUEMA, ia.ESQUEMA_FICHA])
def test_esquema_valido_para_salidas_estructuradas(esquema):
    """Claude exige additionalProperties: false y todos los campos en required en cada objeto del esquema."""
    def objetos(e):
        if isinstance(e, dict):
            if e.get("type") == "object":
                yield e
            for v in e.values():
                yield from objetos(v)
        elif isinstance(e, list):
            for v in e:
                yield from objetos(v)
    lista = list(objetos(esquema))
    assert lista and all(o["additionalProperties"] is False for o in lista)
    assert all(set(o["required"]) == set(o["properties"]) for o in lista)


def test_los_nombres_van_primero_en_el_esquema():
    """El orden del esquema es el orden en que Claude escribe: así el nombre se muestra antes."""
    assert list(ia.ESQUEMA["properties"])[:3] == ["problema", "nombre_comun", "nombre_cientifico"]


@pytest.mark.parametrize(
    "status, tipo, texto, esperado",
    [
        (401, "authentication_error", "invalid x-api-key", "clave de Claude no es válida"),
        (400, "invalid_request_error", "This API key is not scoped to a workspace, so this request must include the "
              "anthropic-workspace-id header with the ID of the workspace to use.", "ámbito «Organización»"),
        (400, "invalid_request_error", "anthropic-workspace-id header must be a valid workspace ID.", "ANTHROPIC_WORKSPACE_ID"),
        (400, "invalid_request_error", "Your credit balance is too low to access the Anthropic API.", "no tiene saldo"),
        (402, "billing_error", "Payment required", "no tiene saldo"),
        (403, "permission_error", "Not allowed", "no tiene permiso"),
        (404, "not_found_error", "model: claude-x", "IA_MODELO"),
        (400, "invalid_request_error", "Could not process image", "no pudo leer esa imagen"),
        (400, "invalid_request_error", "image: media type not supported", "media type not supported"),
    ],
)
def test_errores_explican_la_causa(servidor, status, tipo, texto, esperado):
    MODO.update(status=status, cuerpo=error(tipo, texto))
    with pytest.raises(ia.IAError, match=esperado) as e:
        asyncio.run(ia.identificar(b"x", "image/jpeg"))
    assert str(status) in e.value.detalle  # lo técnico queda para la terminal de la API


def test_saturado_se_reintenta_una_vez(servidor):
    MODO["secuencia"] = [(529, error("overloaded_error", "Overloaded")), (200, None)]
    r = asyncio.run(ia.identificar(b"x", "image/jpeg"))
    assert r.nombre_cientifico == "Ara militaris" and len(PETICIONES) == 2


def test_saturado_dos_veces_avisa(servidor):
    MODO["secuencia"] = [(529, error("overloaded_error", "Overloaded")), (529, error("overloaded_error", "Overloaded"))]
    with pytest.raises(ia.IAError, match="saturado"):
        asyncio.run(ia.identificar(b"x", "image/jpeg"))


def test_claude_declina_la_foto(servidor):
    MODO.update(texto="", stop_reason="refusal")
    r = asyncio.run(ia.identificar(b"x", "image/jpeg"))
    assert not r.tiene_especie and r.problema == "sin_organismo"


def test_respuesta_cortada_queda_no_identificada(servidor):
    MODO.update(texto=json.dumps(RESPUESTA)[:40], stop_reason="max_tokens")
    r = asyncio.run(ia.identificar(b"x", "image/jpeg"))
    assert not r.tiene_especie and r.problema == "sin_organismo"


def test_respuesta_ilegible_queda_no_identificada(servidor):
    MODO["texto"] = "esto no es JSON"
    r = asyncio.run(ia.identificar(b"x", "image/jpeg"))
    assert not r.tiene_especie and r.problema == "sin_organismo"


def test_foto_borrosa_sin_especie(servidor):
    MODO["texto"] = json.dumps({**RESPUESTA, "problema": "borrosa"})
    r = asyncio.run(ia.identificar(b"x", "image/jpeg"))
    assert r.problema == "borrosa" and r.nombre_cientifico is None and r.candidatos == []


def test_sin_conexion(monkeypatch):
    monkeypatch.setattr(ia, "settings", dataclasses.replace(ia.settings, ia_url="http://127.0.0.1:9"))
    monkeypatch.setattr(ia, "_cliente", None)
    with pytest.raises(ia.IAError, match="no pudo conectarse a Claude"):
        asyncio.run(ia.identificar(b"x", "image/jpeg"))


def test_grupo_desconocido_se_corrige(servidor):
    MODO["texto"] = json.dumps({**RESPUESTA, "nombre_cientifico": "Quercus rugosa", "reino": "planta", "grupo": "liquen"})
    r = asyncio.run(ia.identificar(b"x", "image/jpeg"))
    assert r.grupo == "planta"


def test_sin_nombre_queda_no_identificada(servidor):
    MODO["texto"] = json.dumps({**RESPUESTA, "nombre_cientifico": "  "})
    r = asyncio.run(ia.identificar(b"x", "image/jpeg"))
    assert not r.tiene_especie


def test_tipo_de_imagen_desconocido_se_manda_como_jpeg(servidor):
    asyncio.run(ia.identificar(b"x", "application/octet-stream"))
    assert RECIBIDO["body"]["messages"][0]["content"][0]["source"]["media_type"] == "image/jpeg"


def test_el_tipo_se_toma_de_los_bytes_de_la_foto(servidor):
    """Una PNG guardada como image/jpeg haría que Claude rechace la petición."""
    asyncio.run(ia.identificar(b"\x89PNG\r\n\x1a\nresto", "image/jpeg"))
    assert RECIBIDO["body"]["messages"][0]["content"][0]["source"]["media_type"] == "image/png"


def test_ficha_de_especie_nueva(servidor):
    f = asyncio.run(ia.escribir_ficha("Ara militaris", "Guacamaya verde", "animal", "ave"))
    assert f.descripcion == "Loro grande y verde." and f.categoria_nom059 == "P" and f.familia == "Psittacidae"
    body = RECIBIDO["body"]
    assert "stream" not in body and body["system"] == ia.SISTEMA_FICHA
    assert body["messages"][0]["content"] == "Especie: Ara militaris (Guacamaya verde). Reino: animal. Grupo: ave."
    assert body["output_config"]["format"]["schema"] == ia.ESQUEMA_FICHA


def test_ficha_de_planta_sin_alimentacion(servidor):
    f = asyncio.run(ia.escribir_ficha("Quercus rugosa", "Encino", "planta", "arbol"))
    assert f.alimentacion is None


def test_ficha_que_falla_avisa(servidor):
    MODO["cuerpo"] = mensaje("no es json")
    with pytest.raises(ia.IAError):
        asyncio.run(ia.escribir_ficha("Ara militaris", "Guacamaya verde", "animal", "ave"))


@pytest.mark.parametrize("texto, esperado", [
    ('{"problema":"ninguno","nombre_comun":"Zan', {"problema": "ninguno"}),
    ('{"problema":"ninguno","nombre_comun":"Zanate","nombre_cientifico":"quiscalus  MEXICANUS"',
     {"problema": "ninguno", "nombre_comun": "Zanate", "nombre_cientifico": "Quiscalus mexicanus"}),
    ('{"problema":"ninguno","nombre_comun":"Zanate","confianza":0.8,"candidatos":[{"nombre_comun":"Otro","confianza":0.1',
     {"problema": "ninguno", "nombre_comun": "Zanate", "confianza": 0.8}),
    ('{"problema":"borrosa","nombre_comun":null', {"problema": "borrosa", "nombre_comun": None}),
    ('{"problema":"ninguno","candidatos":[],"explicacion":"Cola \\"larga\\" y pico', {"problema": "ninguno",
                                                                                   "explicacion": 'Cola "larga" y pico'}),
])
def test_campos_listos_de_un_json_a_medias(texto, esperado):
    assert ia.campos_listos(texto) == esperado
