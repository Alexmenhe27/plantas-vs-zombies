from datetime import datetime, timedelta, timezone

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from app import ia, main
from app.ia import Candidato, Ficha, Resultado

SB = "https://prueba.supabase.co"
USER = "11111111-1111-1111-1111-111111111111"
FOTO = f"{USER}/foto1.jpg"
PUEBLA = {"latitud": 19.0414, "longitud": -98.2063}
ESPECIES = [
    {"id": 1, "nombre_comun": "Guacamaya verde", "nombre_cientifico": "Ara militaris", "reino": "animal", "grupo": "ave"},
    {"id": 2, "nombre_comun": "Teporingo", "nombre_cientifico": "Romerolagus diazi", "reino": "animal", "grupo": "mamifero"},
]
AUTH = {"Authorization": "Bearer token-bueno"}


@pytest.fixture
def sb():
    with respx.mock(base_url=SB, assert_all_called=False) as mock:
        mock.get("/auth/v1/user").mock(
            side_effect=lambda req: httpx.Response(200, json={"id": USER})
            if req.headers["authorization"] == "Bearer token-bueno"
            else httpx.Response(401, json={"msg": "invalid"})
        )
        mock.get("/rest/v1/observaciones").respond(200, json=[])
        mock.get("/rest/v1/especies").respond(200, json=ESPECIES)
        mock.post("/rest/v1/especies").mock(
            side_effect=lambda req: httpx.Response(201, json=[{"id": 50, **__import__("json").loads(req.content)}])
        )
        mock.patch("/rest/v1/especies").respond(204)
        mock.route(host="es.wikipedia.org").respond(200, json={
            "thumbnail": {"source": "https://upload.wikimedia.org/wikipedia/commons/thumb/a/ab/Ajolote.jpg/320px-Ajolote.jpg"},
            "originalimage": {"width": 2000},
        })
        mock.get(f"/storage/v1/object/fotos/{FOTO}").respond(200, content=b"\xff\xd8jpeg", headers={"content-type": "image/jpeg"})
        mock.post("/rest/v1/observaciones").mock(
            side_effect=lambda req: httpx.Response(201, json=[{"id": "obs-1", **__import__("json").loads(req.content)}])
        )
        yield mock


@pytest.fixture
def client():
    with TestClient(main.app) as c:
        yield c


def ia_responde(monkeypatch, resultado=None, error=None):
    llamadas = []

    async def falso(imagen, tipo, latitud=None, longitud=None):
        llamadas.append((imagen, tipo, latitud, longitud))
        if error:
            raise error
        return resultado

    monkeypatch.setattr(ia, "identificar", falso)
    return llamadas


def test_salud(client):
    r = client.get("/salud")
    assert r.status_code == 200
    assert r.json()["estado"] == "ok"


def test_sin_sesion(client, sb):
    r = client.post("/identificar", json={"ruta_foto": FOTO})
    assert r.status_code == 401
    assert r.json()["detail"]["codigo"] == "sin_sesion"


def test_token_invalido(client, sb):
    r = client.post("/identificar", json={"ruta_foto": FOTO}, headers={"Authorization": "Bearer malo"})
    assert r.status_code == 401


def test_foto_de_otro_usuario(client, sb):
    r = client.post("/identificar", json={"ruta_foto": "otro-usuario/x.jpg"}, headers=AUTH)
    assert r.status_code == 403
    assert r.json()["detail"]["codigo"] == "foto_ajena"


def ficha(cientifico="Ara militaris", comun="Guacamaya verde", **extra) -> Ficha:
    return Ficha(nombre_cientifico=cientifico, nombre_comun=comun, reino="animal", grupo="ave", familia="Psittacidae", **extra)


def test_fuera_de_puebla_tambien_se_identifica(client, sb, monkeypatch):
    llamadas = ia_responde(monkeypatch, Resultado(problema="ninguno", especie=ficha(), confianza=0.9, explicacion="..."))
    r = client.post("/identificar", json={"ruta_foto": FOTO, "latitud": 40.4168, "longitud": -3.7038}, headers=AUTH)
    assert r.status_code == 200, r.text
    assert llamadas[0][2:] == (40.4168, -3.7038)  # la ubicación se le pasa a la IA como pista


def test_limite_diario(client, sb, monkeypatch):
    llamadas = ia_responde(monkeypatch)
    ahora = datetime.now(timezone.utc)
    usos = [{"creado_en": (ahora - timedelta(hours=20) + timedelta(minutes=i)).isoformat()} for i in range(10)]
    sb.get("/rest/v1/observaciones").respond(200, json=usos)
    r = client.post("/identificar", json={"ruta_foto": FOTO, **PUEBLA}, headers=AUTH)
    assert r.status_code == 429
    detalle = r.json()["detail"]
    assert detalle["codigo"] == "limite_diario"
    disponible = datetime.fromisoformat(detalle["disponible_en"])
    assert timedelta(hours=3, minutes=59) < disponible - ahora < timedelta(hours=4, minutes=1)
    assert llamadas == []


def test_foto_no_encontrada(client, sb, monkeypatch):
    ia_responde(monkeypatch)
    sb.get(f"/storage/v1/object/fotos/{FOTO}").respond(404)
    r = client.post("/identificar", json={"ruta_foto": FOTO, **PUEBLA}, headers=AUTH)
    assert r.status_code == 404


def test_identificada_con_especie_del_catalogo(client, sb, monkeypatch):
    llamadas = ia_responde(monkeypatch, Resultado(
        problema="ninguno", especie=ficha(), confianza=0.94, explicacion="Plumaje verde y frente roja.",
        candidatos=[Candidato(nombre_cientifico="Ara militaris", nombre_comun="Guacamaya verde", confianza=0.94),
                    Candidato(nombre_cientifico="Ara macao", nombre_comun="Guacamaya roja", confianza=0.1)],
    ))
    sb.get("/rest/v1/observaciones").respond(200, json=[{"creado_en": datetime.now(timezone.utc).isoformat()}] * 3)
    r = client.post("/identificar", json={"ruta_foto": FOTO, **PUEBLA}, headers=AUTH)
    assert r.status_code == 200, r.text
    obs = r.json()["observacion"]
    assert obs["estado"] == "identificada"
    assert obs["especie_id"] == 1
    assert obs["es_publica"] is True
    assert obs["usuario_id"] == USER
    assert obs["ia_candidatos"] == [
        {"especie_id": 1, "nombre_cientifico": "Ara militaris", "nombre_comun": "Guacamaya verde", "confianza": 0.94},
        {"especie_id": None, "nombre_cientifico": "Ara macao", "nombre_comun": "Guacamaya roja", "confianza": 0.1},
    ]
    assert r.json()["restantes"] == 6
    assert llamadas[0][0] == b"\xff\xd8jpeg"
    assert not [c for c in sb.calls if c.request.method == "POST" and c.request.url.path == "/rest/v1/especies"]  # ya existía


def test_especie_nueva_se_agrega_al_catalogo_con_foto(client, sb, monkeypatch):
    ia_responde(monkeypatch, Resultado(
        problema="ninguno", confianza=0.91, explicacion="Branquias externas.",
        especie=ficha("Ambystoma mexicanum", "Ajolote", categoria_nom059="P", descripcion="Salamandra que no hace metamorfosis."),
    ))
    r = client.post("/identificar", json={"ruta_foto": FOTO}, headers=AUTH)
    assert r.status_code == 200, r.text
    assert r.json()["observacion"]["especie_id"] == 50 and r.json()["observacion"]["estado"] == "identificada"
    creada = __import__("json").loads([c for c in sb.calls if c.request.method == "POST" and c.request.url.path == "/rest/v1/especies"][0].request.content)
    assert creada["nombre_cientifico"] == "Ambystoma mexicanum" and creada["verificada"] is False and creada["protegida"] is True
    foto = [c for c in sb.calls if c.request.method == "PATCH"][0].request
    assert __import__("json").loads(foto.content) == {
        "imagen_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/a/ab/Ajolote.jpg/640px-Ajolote.jpg",
        "imagen_fuente": "https://commons.wikimedia.org/wiki/File:Ajolote.jpg",
    }


def test_confianza_muy_baja_no_llena_el_catalogo(client, sb, monkeypatch):
    ia_responde(monkeypatch, Resultado(
        problema="ninguno", especie=ficha("Sylvilagus nuevo", "Conejo"), confianza=0.3, explicacion="Se ve lejos.",
        candidatos=[Candidato(nombre_cientifico="Romerolagus diazi", nombre_comun="Teporingo", confianza=0.3)],
    ))
    r = client.post("/identificar", json={"ruta_foto": FOTO, **PUEBLA}, headers=AUTH)
    obs = r.json()["observacion"]
    assert obs["estado"] == "revisar" and obs["especie_id"] is None
    assert obs["ia_candidatos"][0]["especie_id"] == 2  # el candidato que sí existe se puede abrir
    assert not [c for c in sb.calls if c.request.method == "POST" and c.request.url.path == "/rest/v1/especies"]


def test_baja_confianza_va_a_revision(client, sb, monkeypatch):
    ia_responde(monkeypatch, Resultado(
        problema="ninguno", especie=ficha("Romerolagus diazi", "Teporingo"), confianza=0.6, explicacion="Se ve lejos.",
    ))
    r = client.post("/identificar", json={"ruta_foto": FOTO, **PUEBLA}, headers=AUTH)
    assert r.json()["observacion"]["estado"] == "revisar"
    assert r.json()["observacion"]["especie_id"] == 2


def test_foto_borrosa(client, sb, monkeypatch):
    ia_responde(monkeypatch, Resultado(problema="borrosa", explicacion="Sostén el teléfono firme."))
    r = client.post("/identificar", json={"ruta_foto": FOTO, **PUEBLA}, headers=AUTH)
    obs = r.json()["observacion"]
    assert obs["estado"] == "no_identificada"
    assert obs["ia_problema"] == "borrosa"
    assert obs["es_publica"] is False


def test_sin_ubicacion_se_permite(client, sb, monkeypatch):
    ia_responde(monkeypatch, Resultado(problema="ninguno", especie=ficha(), confianza=0.9, explicacion="..."))
    r = client.post("/identificar", json={"ruta_foto": FOTO}, headers=AUTH)
    assert r.status_code == 200


def test_ia_caida(client, sb, monkeypatch):
    ia_responde(monkeypatch, error=ia.IAError("La clave de Gemini no es válida", "Gemini respondió 400: API key not valid"))
    r = client.post("/identificar", json={"ruta_foto": FOTO, **PUEBLA}, headers=AUTH)
    assert r.status_code == 502
    assert r.json()["detail"]["codigo"] == "ia_no_disponible"
    assert r.json()["detail"]["mensaje"] == "La clave de Gemini no es válida"  # la causa llega a la app


def test_cors_permite_el_cel_en_la_red_local(client):
    r = client.options("/identificar", headers={"Origin": "http://192.168.1.50:4200", "Access-Control-Request-Method": "POST"})
    assert r.headers.get("access-control-allow-origin") == "http://192.168.1.50:4200"
    r = client.options("/identificar", headers={"Origin": "https://sitio-ajeno.com", "Access-Control-Request-Method": "POST"})
    assert "access-control-allow-origin" not in r.headers


ORIGEN = {"Origin": "http://localhost:4200"}


def test_supabase_caido_responde_502_con_cors(client, sb, monkeypatch):
    # Antes: un error de red hacia Supabase acababa en un 500 sin CORS y la app decía "sin internet".
    sb.get("/rest/v1/observaciones").mock(side_effect=httpx.ConnectError("sin red"))
    ia_responde(monkeypatch)
    r = client.post("/identificar", json={"ruta_foto": FOTO, **PUEBLA}, headers={**AUTH, **ORIGEN})
    assert r.status_code == 502 and r.json()["detail"]["codigo"] == "base_de_datos"
    assert r.headers["access-control-allow-origin"] == "http://localhost:4200"


def test_error_inesperado_responde_json_con_cors(client, sb, monkeypatch):
    async def explota(*_):
        raise RuntimeError("bug")
    monkeypatch.setattr(ia, "identificar", explota)
    with TestClient(main.app, raise_server_exceptions=False) as c:
        r = c.post("/identificar", json={"ruta_foto": FOTO, **PUEBLA}, headers={**AUTH, **ORIGEN})
    assert r.status_code == 500 and r.json()["detail"]["codigo"] == "error_interno"
    assert r.headers["access-control-allow-origin"] == "http://localhost:4200"


def test_clave_secreta_nueva_va_solo_en_apikey(monkeypatch):
    from app import supabase_client
    monkeypatch.setattr(supabase_client, "settings", __import__("dataclasses").replace(supabase_client.settings, supabase_service_key="sb_secret_abc"))
    assert supabase_client._headers() == {"apikey": "sb_secret_abc"}
    monkeypatch.setattr(supabase_client, "settings", __import__("dataclasses").replace(supabase_client.settings, supabase_service_key="eyJ.jwt"))
    assert supabase_client._headers()["Authorization"] == "Bearer eyJ.jwt"


def test_sin_configuracion_avisa_que_falta(client, monkeypatch):
    # Causa del "sin internet" al subir fotos: sin api/.env la URL de Supabase quedaba vacía y la API se caía sin CORS.
    monkeypatch.setattr(main, "settings", __import__("dataclasses").replace(main.settings, supabase_url=""))
    r = client.post("/identificar", json={"ruta_foto": FOTO}, headers={**AUTH, **ORIGEN})
    assert r.status_code == 503
    assert r.json()["detail"]["codigo"] == "configuracion_incompleta" and "SUPABASE_URL" in r.json()["detail"]["mensaje"]
    assert r.headers["access-control-allow-origin"] == "http://localhost:4200"
