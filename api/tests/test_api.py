"""Pruebas de los endpoints con Supabase, Claude y GBIF simulados (no se llama a ningún servicio real)."""
import json

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from app import ia, identificacion, main, taxonomia
from app.ia import Candidato, Ficha, Identificacion
from app.sesion import Usuario

SB = "https://prueba.supabase.co"
GBIF = "https://api.gbif.org/v1"
USER = "11111111-1111-1111-1111-111111111111"
INVITADO = "33333333-3333-3333-3333-333333333333"
FOTO = f"{USER}/foto1.jpg"
PUEBLA = {"latitud": 19.0414, "longitud": -98.2063}
AUTH = {"Authorization": "Bearer token-bueno"}
NDJSON = {**AUTH, "Accept": "application/x-ndjson"}


def especie(id_, comun, cientifico, grupo="ave", reino="animal", **extra):
    return {"id": id_, "nombre_comun": comun, "nombre_cientifico": cientifico, "reino": reino, "grupo": grupo,
            "descripcion": "Ficha revisada.", "imagen_url": "https://upload.wikimedia.org/x.jpg", "verificada": True, **extra}


class FalsoSupabase:
    """Imita las funciones SQL (reservar_identificacion, guardar_identificacion...) y guarda lo que recibe."""

    def __init__(self):
        self.catalogo = {e["nombre_cientifico"]: e for e in (
            especie(1, "Guacamaya verde", "Ara militaris", protegida=True, categoria_nom059="P"),
            especie(2, "Teporingo", "Romerolagus diazi", grupo="mamifero"),
        )}
        self.reserva = {"ok": True, "reserva": 7, "restantes": 9, "limite": 10, "invitado": False}
        self.reservas, self.liberadas, self.guardados = [], [], []
        self.observaciones = {}
        self.parches_especie, self.parches_obs, self.borrados = [], [], []

    def reservar(self, req):
        self.reservas.append(json.loads(req.content))
        return httpx.Response(200, json=self.reserva)

    def liberar(self, req):
        self.liberadas.append(json.loads(req.content)["p_reserva"])
        return httpx.Response(200, json=None)

    def guardar(self, req):
        cuerpo = json.loads(req.content)
        datos = cuerpo["p_datos"]
        self.guardados.append(cuerpo)
        esp, creada = None, False
        if datos["problema"] == "ninguno":
            esp = next((self.catalogo[n] for n in datos["nombres"] if n in self.catalogo), None)
            nueva = datos.get("nueva_especie")
            if esp is None and nueva and datos["confianza"] >= datos["confianza_para_catalogo"]:
                esp = {"id": 50, **nueva, "descripcion": None, "imagen_url": None, "verificada": False}
                self.catalogo[nueva["nombre_cientifico"]] = esp
                creada = True
        if datos["problema"] != "ninguno":
            estado = "no_identificada"
        elif esp is None or datos["confianza"] < datos["confianza_minima"]:
            estado = "revisar"
        else:
            estado = "identificada"
        candidatos = [{**c, "especie_id": (self.catalogo.get(c["nombre_cientifico"]) or {}).get("id")} for c in datos["candidatos"]]
        obs = {"id": "obs-1", "usuario_id": datos["usuario_id"], "ruta_foto": datos["ruta_foto"], "estado": estado,
               "especie_id": esp and esp["id"], "especie": esp, "ia_confianza": datos["confianza"], "ia_candidatos": candidatos,
               "ia_explicacion": datos["explicacion"], "ia_nombre_sugerido": datos["nombre_sugerido"], "es_publica": False,
               "ia_problema": None if datos["problema"] == "ninguno" else datos["problema"]}
        self.observaciones["obs-1"] = obs
        return httpx.Response(200, json={"observacion": obs, "especie_creada": creada, "candidatos_especies": [
            self.catalogo[c["nombre_cientifico"]] for c in candidatos if c["especie_id"]]})

    def especies(self, req):
        valor = req.url.params.get("nombre_cientifico", "")
        nombres = [n.strip('"') for n in valor[len("in.("):-1].split(",")] if valor.startswith("in.(") else []
        return httpx.Response(200, json=[self.catalogo[n] for n in nombres if n in self.catalogo])

    def crear_especie(self, req):
        fila = {"id": 60, **json.loads(req.content)}
        self.catalogo[fila["nombre_cientifico"]] = fila
        return httpx.Response(201, json=[fila])

    def parchar_especie(self, req):
        campos = json.loads(req.content)
        self.parches_especie.append(campos)
        eid = int(req.url.params["id"][3:])
        esp = next(e for e in self.catalogo.values() if e["id"] == eid)
        esp.update(campos)
        return httpx.Response(200, json=[esp])

    def leer_observacion(self, req):
        o = self.observaciones.get(req.url.params["id"][3:])
        return httpx.Response(200, json=[o] if o else [])

    def parchar_observacion(self, req):
        campos = json.loads(req.content)
        self.parches_obs.append(campos)
        o = self.observaciones[req.url.params["id"][3:]]
        o.update(campos)
        o["especie"] = next((e for e in self.catalogo.values() if e["id"] == o.get("especie_id")), None)
        return httpx.Response(200, json=[o])


@pytest.fixture
def falso():
    return FalsoSupabase()


@pytest.fixture
def sb(falso):
    taxonomia._cache.clear()
    with respx.mock(base_url=SB, assert_all_called=False) as mock:
        mock.post("/rest/v1/rpc/reservar_identificacion").mock(side_effect=falso.reservar)
        mock.post("/rest/v1/rpc/liberar_identificacion").mock(side_effect=falso.liberar)
        mock.post("/rest/v1/rpc/guardar_identificacion").mock(side_effect=falso.guardar)
        mock.get(f"/storage/v1/object/fotos/{FOTO}").respond(200, content=b"\xff\xd8jpeg", headers={"content-type": "image/jpeg"})
        mock.get("/rest/v1/especies").mock(side_effect=falso.especies)
        mock.post("/rest/v1/especies").mock(side_effect=falso.crear_especie)
        mock.patch("/rest/v1/especies").mock(side_effect=falso.parchar_especie)
        mock.get("/rest/v1/observaciones").mock(side_effect=falso.leer_observacion)
        mock.patch("/rest/v1/observaciones").mock(side_effect=falso.parchar_observacion)
        mock.route(host="api.gbif.org").respond(200, json={"matchType": "NONE"})
        mock.route(host="es.wikipedia.org").respond(200, json={
            "thumbnail": {"source": "https://upload.wikimedia.org/wikipedia/commons/thumb/a/ab/Mirlo.jpg/320px-Mirlo.jpg"},
            "originalimage": {"width": 2000},
        })
        yield mock


class FalsoValidador:
    async def validar(self, token):
        return {"token-bueno": Usuario(USER, False, "ana@ejemplo.mx"), "token-invitado": Usuario(INVITADO, True)}.get(token)


@pytest.fixture
def client():
    with TestClient(main.app) as c:
        c.app.state.sesiones = FalsoValidador()
        yield c


def ia_responde(monkeypatch, resultado=None, error=None, parciales=()):
    llamadas = []

    async def falso(imagen, tipo, latitud=None, longitud=None, al_avanzar=None):
        llamadas.append((imagen, tipo, latitud, longitud))
        for p in parciales:
            if al_avanzar:
                await al_avanzar(p)
        if error:
            raise error
        return resultado

    async def ficha(nombre_cientifico, nombre_comun, reino, grupo):
        return Ficha(descripcion="Mirlo de dorso rojizo.", habitat="Ciudades", alimentacion="Insectos", tamano="24 cm",
                     familia="Turdidae", categoria_nom059=None, introducida=False)

    monkeypatch.setattr(ia, "identificar", falso)
    monkeypatch.setattr(ia, "escribir_ficha", ficha)
    return llamadas


def identificado(cientifico="Ara militaris", comun="Guacamaya verde", confianza=0.94, reino="animal", grupo="ave", candidatos=None):
    return Identificacion(problema="ninguno", nombre_comun=comun, nombre_cientifico=cientifico, reino=reino, grupo=grupo,
                          confianza=confianza, explicacion="Rasgos claros.",
                          candidatos=candidatos or [Candidato(nombre_cientifico=cientifico, nombre_comun=comun, grupo=grupo,
                                                              confianza=confianza)])


def eventos(r):
    return [json.loads(linea) for linea in r.text.splitlines() if linea.strip()]


# ------------------------------------------------------------------ básicos
def test_salud(client):
    r = client.get("/salud")
    assert r.status_code == 200
    assert r.json()["estado"] == "ok" and r.json()["ia"] == "claude" and r.json()["razonamiento"] in ("bajo", "sin")


def test_sin_sesion(client, sb):
    r = client.post("/identificar", json={"ruta_foto": FOTO})
    assert r.status_code == 401 and r.json()["detail"]["codigo"] == "sin_sesion"


def test_token_invalido(client, sb):
    r = client.post("/identificar", json={"ruta_foto": FOTO}, headers={"Authorization": "Bearer malo"})
    assert r.status_code == 401


def test_foto_de_otro_usuario(client, sb, falso):
    r = client.post("/identificar", json={"ruta_foto": "22222222-2222-2222-2222-222222222222/x.jpg"}, headers=AUTH)
    assert r.status_code == 403 and r.json()["detail"]["codigo"] == "foto_ajena"
    r = client.post("/identificar", json={"ruta_foto": f"{USER}/../otro/x.jpg"}, headers=AUTH)
    assert r.status_code == 403
    assert falso.reservas == []  # ni siquiera se reservó cupo


# ------------------------------------------------------------------ límite diario
def test_limite_diario(client, sb, falso, monkeypatch):
    llamadas = ia_responde(monkeypatch, identificado())
    falso.reserva = {"ok": False, "motivo": "limite_diario", "limite": 10, "invitado": False,
                     "disponible_en": "2026-10-15T10:00:00+00:00"}
    r = client.post("/identificar", json={"ruta_foto": FOTO}, headers=AUTH)
    assert r.status_code == 429
    d = r.json()["detail"]
    assert d["codigo"] == "limite_diario" and d["limite"] == 10 and d["disponible_en"] == "2026-10-15T10:00:00+00:00"
    assert "límite de 10" in d["mensaje"]
    assert llamadas == []  # no se gastó IA


def test_admin_no_tiene_limite(client, sb, falso, monkeypatch):
    llamadas = ia_responde(monkeypatch, identificado())
    falso.reserva = {"ok": False, "motivo": "limite_diario", "limite": 10, "invitado": False}
    sb.get("/rest/v1/perfiles").respond(200, json=[{"rol": "admin"}])
    r = client.post("/identificar", json={"ruta_foto": FOTO}, headers=AUTH)
    assert r.status_code == 200, r.text
    assert len(llamadas) == 1


def test_invitado_invita_a_crear_cuenta(client, sb, falso, monkeypatch):
    ia_responde(monkeypatch, identificado())
    falso.reserva = {"ok": False, "motivo": "limite_diario", "limite": 3, "invitado": True, "disponible_en": "2026-10-15T10:00:00+00:00"}
    sb.get(f"/storage/v1/object/fotos/{INVITADO}/a.jpg").respond(200, content=b"\xff\xd8", headers={"content-type": "image/jpeg"})
    r = client.post("/identificar", json={"ruta_foto": f"{INVITADO}/a.jpg"}, headers={"Authorization": "Bearer token-invitado"})
    assert r.status_code == 429 and "Crea tu cuenta" in r.json()["detail"]["mensaje"] and r.json()["detail"]["invitado"] is True
    # a los invitados se les manda la huella anónima de su red (para el límite por red), nunca la IP
    red = falso.reservas[0]["p_red"]
    assert red and len(red) == 32 and "." not in red


def test_usuario_registrado_no_manda_huella_de_red(client, sb, falso, monkeypatch):
    ia_responde(monkeypatch, identificado())
    client.post("/identificar", json={"ruta_foto": FOTO}, headers=AUTH)
    assert falso.reservas[0] == {"p_usuario": USER, "p_red": None}


def test_limite_por_red_y_global(client, sb, falso, monkeypatch):
    ia_responde(monkeypatch, identificado())
    falso.reserva = {"ok": False, "motivo": "limite_red", "limite": 3, "invitado": True}
    r = client.post("/identificar", json={"ruta_foto": FOTO}, headers=AUTH)
    assert r.status_code == 429 and "esta red" in r.json()["detail"]["mensaje"]
    falso.reserva = {"ok": False, "motivo": "limite_global"}
    r = client.post("/identificar", json={"ruta_foto": FOTO}, headers=AUTH)
    assert r.status_code == 503 and r.json()["detail"]["codigo"] == "servicio_saturado"


def test_foto_no_encontrada_devuelve_el_cupo(client, sb, falso, monkeypatch):
    ia_responde(monkeypatch, identificado())
    sb.get(f"/storage/v1/object/fotos/{USER}/no-existe.jpg").respond(404)
    r = client.post("/identificar", json={"ruta_foto": f"{USER}/no-existe.jpg"}, headers=AUTH)
    assert r.status_code == 404 and r.json()["detail"]["codigo"] == "foto_no_encontrada"
    assert falso.liberadas == [7]


def test_ia_caida_devuelve_el_cupo(client, sb, falso, monkeypatch):
    ia_responde(monkeypatch, error=ia.IAError("Claude no responde ahora."))
    r = client.post("/identificar", json={"ruta_foto": FOTO, **PUEBLA}, headers=AUTH)
    assert r.status_code == 502
    assert r.json()["detail"] == {"codigo": "ia_no_disponible", "mensaje": "Claude no responde ahora."}
    assert falso.liberadas == [7] and falso.guardados == []


# ------------------------------------------------------------------ identificación
def test_identificada_con_especie_del_catalogo(client, sb, falso, monkeypatch):
    llamadas = ia_responde(monkeypatch, identificado())
    r = client.post("/identificar", json={"ruta_foto": FOTO, **PUEBLA, "observada_en": "2026-10-14T10:00:00Z"}, headers=AUTH)
    assert r.status_code == 200
    cuerpo = r.json()
    assert cuerpo["observacion"]["estado"] == "identificada" and cuerpo["observacion"]["especie"]["id"] == 1
    assert cuerpo["restantes"] == 9 and cuerpo["limite"] == 10 and cuerpo["ficha_pendiente"] is False
    assert [e["id"] for e in cuerpo["candidatos_especies"]] == [1]
    assert "ia;dur=" in r.headers["server-timing"] and "total;dur=" in r.headers["server-timing"]
    assert llamadas == [(b"\xff\xd8jpeg", "image/jpeg", 19.0414, -98.2063)]  # la ubicación va como pista
    p = falso.guardados[0]
    assert p["p_reserva"] == 7
    d = p["p_datos"]
    assert d["usuario_id"] == USER and d["ruta_foto"] == FOTO and d["observada_en"].startswith("2026-10-14T10:00:00")
    assert d["nombres"] == ["Ara militaris"] and d["nombre_sugerido"] == "Guacamaya verde (Ara militaris)"
    assert d["confianza_minima"] == 0.7 and d["confianza_para_catalogo"] == 0.5


def test_especie_nueva_validada_en_gbif_con_su_ficha_y_foto(client, sb, falso, monkeypatch):
    ia_responde(monkeypatch, identificado("Turdus rufopaliatus", "Mirlo dorso rufo", 0.9))
    sb.route(host="api.gbif.org").respond(200, json={
        "matchType": "FUZZY", "confidence": 96, "rank": "SPECIES", "status": "ACCEPTED", "canonicalName": "Turdus rufopalliatus",
        "usageKey": 2490718, "family": "Turdidae", "kingdom": "Animalia", "class": "Aves"})
    r = client.post("/identificar", json={"ruta_foto": FOTO}, headers=NDJSON)
    assert r.status_code == 200 and r.headers["content-type"].startswith("application/x-ndjson")
    ev = eventos(r)
    tipos = [e["tipo"] for e in ev]
    assert tipos[-1] == "fin" and "resultado" in tipos
    resultado = next(e for e in ev if e["tipo"] == "resultado")
    assert resultado["ficha_pendiente"] is True and resultado["observacion"]["especie"]["verificada"] is False
    d = falso.guardados[0]["p_datos"]
    # se busca con los dos nombres y se crea con el aceptado por GBIF (corrige la falta de ortografía)
    assert d["nombres"] == ["Turdus rufopaliatus", "Turdus rufopalliatus"]
    assert d["nueva_especie"] == {"nombre_cientifico": "Turdus rufopalliatus", "nombre_comun": "Mirlo dorso rufo", "reino": "animal",
                                  "grupo": "ave", "familia": "Turdidae", "gbif_id": 2490718}
    assert d["candidatos"][0]["nombre_cientifico"] == "Turdus rufopalliatus"
    fichas = [e for e in ev if e["tipo"] == "ficha"]
    assert fichas[0]["especie"]["descripcion"] == "Mirlo de dorso rojizo." and fichas[0]["especie"]["familia"] == "Turdidae"
    assert fichas[-1]["especie"]["imagen_url"].endswith("/640px-Mirlo.jpg")
    assert falso.parches_especie[0]["protegida"] is False
    assert ev.index(resultado) < ev.index(fichas[0])  # el resultado no espera a la ficha


def test_nombre_que_gbif_no_reconoce_no_entra_al_catalogo(client, sb, falso, monkeypatch):
    ia_responde(monkeypatch, identificado("Schistocerca sp.", "Chapulín", 0.6, grupo="insecto"))
    sb.route(host="api.gbif.org").respond(200, json={"matchType": "HIGHERRANK", "rank": "GENUS", "confidence": 94})
    r = client.post("/identificar", json={"ruta_foto": FOTO}, headers=AUTH)
    assert r.json()["observacion"]["estado"] == "revisar"
    assert falso.guardados[0]["p_datos"]["nueva_especie"] is None


def test_gbif_caido_agrega_sin_validar(client, sb, falso, monkeypatch):
    ia_responde(monkeypatch, identificado("Turdus rufopalliatus", "Mirlo dorso rufo", 0.9))
    sb.route(host="api.gbif.org").mock(side_effect=httpx.ConnectError("sin red"))
    r = client.post("/identificar", json={"ruta_foto": FOTO}, headers=AUTH)
    assert r.json()["observacion"]["estado"] == "identificada"
    assert falso.guardados[0]["p_datos"]["nueva_especie"]["gbif_id"] is None


def test_streaming_avisa_el_nombre_antes_del_resultado(client, sb, monkeypatch):
    parciales = [{"problema": "ninguno"},
                 {"problema": "ninguno", "nombre_comun": "Guacamaya verde", "nombre_cientifico": "Ara militaris", "reino": "animal"}]
    ia_responde(monkeypatch, identificado(), parciales=parciales)
    ev = eventos(client.post("/identificar", json={"ruta_foto": FOTO}, headers=NDJSON))
    assert [e["tipo"] for e in ev] == ["parcial", "parcial", "resultado", "fin"]
    assert ev[1]["nombre_comun"] == "Guacamaya verde"
    assert "nombre_visible" in ev[-1]["tiempos"] and "total" in ev[-1]["tiempos"]


def test_streaming_con_error_de_ia(client, sb, falso, monkeypatch):
    ia_responde(monkeypatch, error=ia.IAError("Claude está saturado."))
    ev = eventos(client.post("/identificar", json={"ruta_foto": FOTO}, headers=NDJSON))
    assert ev == [{"tipo": "error", "codigo": "ia_no_disponible", "mensaje": "Claude está saturado."}]
    assert falso.liberadas == [7]


def test_confianza_muy_baja_no_llena_el_catalogo(client, sb, falso, monkeypatch):
    ia_responde(monkeypatch, identificado("Ambystoma velasci", "Ajolote", 0.3, grupo="anfibio"))
    r = client.post("/identificar", json={"ruta_foto": FOTO}, headers=AUTH)
    assert r.json()["observacion"]["estado"] == "revisar" and r.json()["observacion"]["especie"] is None


def test_baja_confianza_va_a_revision(client, sb, monkeypatch):
    cands = [Candidato(nombre_cientifico="Romerolagus diazi", nombre_comun="Teporingo", grupo="mamifero", confianza=0.55),
             Candidato(nombre_cientifico="Sylvilagus floridanus", nombre_comun="Conejo", grupo="mamifero", confianza=0.3)]
    ia_responde(monkeypatch, identificado("Romerolagus diazi", "Teporingo", 0.55, grupo="mamifero", candidatos=cands))
    o = client.post("/identificar", json={"ruta_foto": FOTO}, headers=AUTH).json()["observacion"]
    assert o["estado"] == "revisar" and [c["especie_id"] for c in o["ia_candidatos"]] == [2, None]


def test_foto_borrosa(client, sb, falso, monkeypatch):
    ia_responde(monkeypatch, Identificacion(problema="borrosa", explicacion="Acércate más."))
    o = client.post("/identificar", json={"ruta_foto": FOTO}, headers=AUTH).json()["observacion"]
    assert o["estado"] == "no_identificada" and o["ia_problema"] == "borrosa"
    assert falso.liberadas == []  # sí cuenta: se usó la IA


def test_sin_ubicacion_se_permite(client, sb, monkeypatch):
    llamadas = ia_responde(monkeypatch, identificado())
    assert client.post("/identificar", json={"ruta_foto": FOTO}, headers=AUTH).status_code == 200
    assert llamadas[0][2:] == (None, None)


# ------------------------------------------------------------------ elegir entre las parecidas
def preparar_revision(falso, candidatos):
    falso.observaciones["obs-9"] = {"id": "obs-9", "usuario_id": USER, "estado": "revisar", "especie_id": None,
                                    "ia_candidatos": candidatos}


def test_elegir_especie_del_catalogo(client, sb, falso):
    preparar_revision(falso, [{"nombre_cientifico": "Romerolagus diazi", "especie_id": 2, "confianza": 0.5}])
    r = client.post("/observaciones/obs-9/elegir", json={"nombre_cientifico": "romerolagus DIAZI"}, headers=AUTH)
    assert r.status_code == 200
    assert falso.parches_obs == [{"especie_id": 2, "estado": "elegida"}]
    assert r.json()["observacion"]["especie"]["nombre_comun"] == "Teporingo"


def test_elegir_especie_nueva_la_valida_y_crea(client, sb, falso):
    preparar_revision(falso, [{"nombre_cientifico": "Sylvilagus floridanus", "nombre_comun": "Conejo serrano", "grupo": "mamifero",
                               "especie_id": None, "confianza": 0.4}])
    sb.route(host="api.gbif.org").respond(200, json={
        "matchType": "EXACT", "confidence": 99, "rank": "SPECIES", "status": "ACCEPTED", "canonicalName": "Sylvilagus floridanus",
        "usageKey": 2436691, "family": "Leporidae", "kingdom": "Animalia", "class": "Mammalia"})
    r = client.post("/observaciones/obs-9/elegir", json={"nombre_cientifico": "Sylvilagus floridanus"}, headers=AUTH)
    assert r.status_code == 200
    creada = falso.catalogo["Sylvilagus floridanus"]
    assert creada["verificada"] is False and creada["gbif_id"] == 2436691 and creada["reino"] == "animal"
    assert falso.parches_obs == [{"especie_id": 60, "estado": "elegida"}]


def test_elegir_solo_entre_las_parecidas(client, sb, falso):
    preparar_revision(falso, [{"nombre_cientifico": "Romerolagus diazi", "especie_id": 2, "confianza": 0.5}])
    r = client.post("/observaciones/obs-9/elegir", json={"nombre_cientifico": "Panthera onca"}, headers=AUTH)
    assert r.status_code == 400 and r.json()["detail"]["codigo"] == "candidato_invalido"


def test_elegir_en_observacion_ajena_o_ya_revisada(client, sb, falso):
    preparar_revision(falso, [{"nombre_cientifico": "Romerolagus diazi", "especie_id": 2, "confianza": 0.5}])
    falso.observaciones["obs-9"]["usuario_id"] = "otra-persona"
    r = client.post("/observaciones/obs-9/elegir", json={"nombre_cientifico": "Romerolagus diazi"}, headers=AUTH)
    assert r.status_code == 404
    falso.observaciones["obs-9"].update(usuario_id=USER, estado="identificada")
    r = client.post("/observaciones/obs-9/elegir", json={"nombre_cientifico": "Romerolagus diazi"}, headers=AUTH)
    assert r.status_code == 409


# ------------------------------------------------------------------ red, CORS y configuración
def test_cors_permite_el_cel_en_la_red_local(client):
    r = client.options("/identificar", headers={
        "Origin": "http://192.168.1.70:4200", "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "authorization,content-type,accept"})
    assert r.status_code == 200 and r.headers["access-control-allow-origin"] == "http://192.168.1.70:4200"
    r = client.options("/cuenta", headers={"Origin": "http://localhost:4200", "Access-Control-Request-Method": "DELETE"})
    assert r.status_code == 200


def test_supabase_caido_responde_502_con_cors(client, sb, monkeypatch):
    ia_responde(monkeypatch, identificado())
    sb.post("/rest/v1/rpc/reservar_identificacion").mock(side_effect=httpx.ConnectError("sin red"))
    r = client.post("/identificar", json={"ruta_foto": FOTO}, headers={**AUTH, "Origin": "http://localhost:4200"})
    assert r.status_code == 502 and r.json()["detail"]["codigo"] == "base_de_datos"
    assert r.headers["access-control-allow-origin"] == "http://localhost:4200"


def test_error_inesperado_responde_json_con_cors(client, sb, monkeypatch):
    async def explota(*a, **k):
        raise RuntimeError("bug")
    monkeypatch.setattr(identificacion, "preparar", explota)
    r = client.post("/identificar", json={"ruta_foto": FOTO}, headers={**AUTH, "Origin": "http://localhost:4200"})
    assert r.status_code == 500 and r.json()["detail"]["codigo"] == "error_interno"
    assert r.headers["access-control-allow-origin"] == "http://localhost:4200"


def test_clave_secreta_nueva_va_solo_en_apikey(monkeypatch):
    from app import supabase_client
    monkeypatch.setattr(supabase_client, "settings", type("S", (), {"supabase_service_key": "sb_secret_abc"})())
    assert supabase_client._headers() == {"apikey": "sb_secret_abc"}
    monkeypatch.setattr(supabase_client, "settings", type("S", (), {"supabase_service_key": "eyJ.jwt"})())
    assert supabase_client._headers()["Authorization"] == "Bearer eyJ.jwt"


def test_sin_configuracion_avisa_que_falta(client, monkeypatch):
    import dataclasses
    monkeypatch.setattr(main, "settings", dataclasses.replace(main.settings, supabase_url="", anthropic_api_key=""))
    r = client.post("/identificar", json={"ruta_foto": FOTO}, headers=AUTH)
    assert r.status_code == 503 and r.json()["detail"]["codigo"] == "configuracion_incompleta"
    assert "SUPABASE_URL" in r.json()["detail"]["mensaje"] and "ANTHROPIC_API_KEY" in r.json()["detail"]["mensaje"]


def test_en_produccion_no_se_muestran_detalles_tecnicos(client, sb, monkeypatch):
    import dataclasses
    monkeypatch.setattr(identificacion, "settings", dataclasses.replace(identificacion.settings, produccion=True))
    ia_responde(monkeypatch, error=ia.IAError("La clave de Claude no es válida. Revisa ANTHROPIC_API_KEY en api/.env"))
    r = client.post("/identificar", json={"ruta_foto": FOTO}, headers=AUTH)
    assert r.status_code == 502 and "api/.env" not in r.json()["detail"]["mensaje"]
    assert r.json()["detail"]["mensaje"] == identificacion.MENSAJE_IA_GENERICO
