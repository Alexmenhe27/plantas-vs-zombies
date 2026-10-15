"""Validación de la sesión dentro de la API: firma ES256 (como la de Supabase), vencimiento, audiencia y emisor."""
import asyncio
import json
import time

import httpx
import jwt
import pytest
import respx
from cryptography.hazmat.primitives.asymmetric import ec

from app.sesion import ValidadorSesion
from app.supabase_client import Supabase

SB = "https://prueba.supabase.co"
CLAVE = ec.generate_private_key(ec.SECP256R1())
OTRA_CLAVE = ec.generate_private_key(ec.SECP256R1())


def jwk_publica(clave, kid="clave-1"):
    d = json.loads(jwt.algorithms.ECAlgorithm.to_jwk(clave.public_key()))
    return {**d, "kid": kid, "alg": "ES256", "use": "sig"}


def token(clave=CLAVE, kid="clave-1", **cambios):
    datos = {"sub": "11111111-1111-1111-1111-111111111111", "role": "authenticated", "aud": "authenticated",
             "iss": f"{SB}/auth/v1", "exp": int(time.time()) + 3600, "email": "ana@ejemplo.mx", "is_anonymous": False}
    datos.update(cambios)
    return jwt.encode({k: v for k, v in datos.items() if v is not None}, clave, algorithm="ES256", headers={"kid": kid})


def validar(t):
    async def correr():
        async with httpx.AsyncClient() as http:
            return await ValidadorSesion(Supabase(http)).validar(t)
    return asyncio.run(correr())


@pytest.fixture
def jwks():
    with respx.mock(base_url=SB, assert_all_called=False) as mock:
        ruta = mock.get("/auth/v1/.well-known/jwks.json").respond(200, json={"keys": [jwk_publica(CLAVE)]})
        yield ruta


def test_token_valido(jwks):
    u = validar(token())
    assert u.id == "11111111-1111-1111-1111-111111111111" and not u.es_invitado and u.email == "ana@ejemplo.mx"


def test_invitado(jwks):
    assert validar(token(is_anonymous=True, email=None)).es_invitado


@pytest.mark.parametrize("cambios", [
    {"exp": int(time.time()) - 3600},          # vencido
    {"aud": "otra"},                            # otra audiencia
    {"iss": "https://otro.supabase.co/auth/v1"},  # otro proyecto
    {"role": "anon"},                           # clave pública, no una sesión
    {"sub": None},                              # sin usuario
])
def test_tokens_invalidos(jwks, cambios):
    assert validar(token(**cambios)) is None


def test_firma_con_otra_clave(jwks):
    assert validar(token(clave=OTRA_CLAVE)) is None


def test_clave_desconocida_pregunta_a_supabase(jwks):
    """Si Supabase acaba de cambiar sus claves, la API no rechaza a ciegas: le pregunta a Supabase."""
    with respx.mock(base_url=SB, assert_all_called=False) as mock:
        mock.get("/auth/v1/.well-known/jwks.json").respond(200, json={"keys": [jwk_publica(CLAVE)]})
        usuario = mock.get("/auth/v1/user").respond(401, json={})
        assert validar(token(kid="clave-nueva", clave=OTRA_CLAVE)) is None
        assert usuario.called


def test_texto_que_no_es_jwt(jwks):
    assert validar("no-es-un-token") is None


def test_proyecto_con_clave_secreta_anterior_pregunta_a_supabase():
    """Un token HS256 (clave secreta anterior de Supabase) se valida preguntándole a Supabase."""
    bueno = jwt.encode({"sub": "x", "exp": int(time.time()) + 60}, "secreto-de-32-caracteres-o-mas-123456", algorithm="HS256")
    malo = jwt.encode({"sub": "y", "exp": int(time.time()) + 60}, "secreto-de-32-caracteres-o-mas-123456", algorithm="HS256")
    with respx.mock(base_url=SB) as mock:
        mock.get("/auth/v1/user").mock(side_effect=lambda req: httpx.Response(
            200, json={"id": "22222222-2222-2222-2222-222222222222", "is_anonymous": True})
            if req.headers["authorization"] == f"Bearer {bueno}" else httpx.Response(401, json={}))
        u = validar(bueno)
        assert u.id == "22222222-2222-2222-2222-222222222222" and u.es_invitado
        assert validar(malo) is None
