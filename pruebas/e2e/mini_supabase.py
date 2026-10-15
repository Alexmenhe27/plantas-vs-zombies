"""Mini Supabase para pruebas de punta a punta SIN cuenta en la nube.

Imita lo que la app y la API usan de Supabase:
- Auth (/auth/v1): registro, entrar sin cuenta (anónimo), login con contraseña, refresh, usuario, cambiar correo
  (un invitado que crea su cuenta), logout, recuperar, borrar usuario (admin) y claves públicas (JWKS).
  Las sesiones se firman con ES256 como en Supabase, así la API las valida sola con la clave pública.
- Base de datos (/rest/v1): se reenvía a PostgREST, que corre sobre el Postgres local con las
  migraciones reales y RLS, así que los permisos que se prueban son los de verdad.
- Storage (/storage/v1): subir, listar, firmar URLs, descargar y borrar fotos. Cada operación se valida
  contra las políticas reales de storage.objects ejecutando como el usuario.

Solo para pruebas locales. No usar en producción.
"""
import base64
import hashlib
import json
import os
import secrets
import sys
import tempfile
import time
import uuid
from pathlib import Path

import httpx
import jwt
import psycopg
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

DB = os.environ.get("E2E_DB", "host=127.0.0.1 port=54329 dbname=app_e2e user=postgres")
POSTGREST = os.environ.get("E2E_POSTGREST", "http://127.0.0.1:3001")
BASE = os.environ.get("E2E_SUPABASE_URL", "http://127.0.0.1:54321")
SECRET = os.environ.get("E2E_JWT_SECRET", "secreto-de-pruebas-locales-de-32-caracteres-o-mas")
CARPETA = Path(os.environ.get("E2E_DATOS", Path(tempfile.gettempdir()) / "fauna-e2e"))
ARCHIVOS = CARPETA / "storage"
ARCHIVOS.mkdir(parents=True, exist_ok=True)
KID = "clave-e2e"


def _clave_privada() -> ec.EllipticCurvePrivateKey:
    """La clave ES256 se guarda en disco para que PostgREST y la API la conozcan aunque se reinicie este servidor."""
    archivo = CARPETA / "clave_es256.pem"
    if archivo.exists():
        return serialization.load_pem_private_key(archivo.read_bytes(), password=None)
    clave = ec.generate_private_key(ec.SECP256R1())
    archivo.write_bytes(clave.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    return clave


PRIVADA = _clave_privada()
JWK_PUBLICA = {**json.loads(jwt.algorithms.ECAlgorithm.to_jwk(PRIVADA.public_key())), "kid": KID, "alg": "ES256", "use": "sig"}


def jwks_para_postgrest() -> dict:
    """PostgREST acepta las claves de rol (HS256, con el secreto) y las sesiones (ES256)."""
    k = base64.urlsafe_b64encode(SECRET.encode()).rstrip(b"=").decode()
    return {"keys": [JWK_PUBLICA, {"kty": "oct", "k": k, "alg": "HS256"}]}


app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"], expose_headers=["*"])
http = httpx.AsyncClient(timeout=30)
refresh_tokens: dict[str, str] = {}
correos_pendientes: dict[str, str] = {}


def clave(role: str) -> str:
    return jwt.encode({"role": role, "iss": "mini-supabase", "exp": int(time.time()) + 10 * 365 * 86400}, SECRET, algorithm="HS256")


ANON_KEY = clave("anon")
SERVICE_KEY = clave("service_role")
COLUMNAS = "id, email, raw_user_meta_data, created_at, is_anonymous"


def hash_pw(pw: str) -> str:
    return hashlib.sha256(pw.encode()).hexdigest()


def usuario_json(fila) -> dict:
    uid, email, meta, creado, anonimo = fila
    u = {
        "id": str(uid), "aud": "authenticated", "role": "authenticated", "email": email or "", "is_anonymous": bool(anonimo),
        "email_confirmed_at": None if anonimo else creado.isoformat(), "user_metadata": meta or {},
        "app_metadata": {"provider": "anonymous" if anonimo else "email"}, "created_at": creado.isoformat(), "updated_at": creado.isoformat(),
    }
    if str(uid) in correos_pendientes:
        u["new_email"] = correos_pendientes[str(uid)]
    return u


def sesion(fila) -> dict:
    user = usuario_json(fila)
    exp = int(time.time()) + 3600
    token = jwt.encode(
        {"sub": user["id"], "role": "authenticated", "aud": "authenticated", "email": user["email"], "exp": exp,
         "iss": f"{BASE}/auth/v1", "is_anonymous": user["is_anonymous"]},
        PRIVADA, algorithm="ES256", headers={"kid": KID},
    )
    rt = secrets.token_hex(16)
    refresh_tokens[rt] = user["id"]
    return {"access_token": token, "token_type": "bearer", "expires_in": 3600, "expires_at": exp, "refresh_token": rt, "user": user}


def claims(request: Request) -> dict | None:
    auth = request.headers.get("authorization", "")
    if not auth.lower().startswith("bearer "):
        return None
    token = auth[7:]
    try:
        if jwt.get_unverified_header(token).get("alg") == "ES256":
            return jwt.decode(token, PRIVADA.public_key(), algorithms=["ES256"], options={"verify_aud": False})
        return jwt.decode(token, SECRET, algorithms=["HS256"], options={"verify_aud": False})
    except jwt.PyJWTError:
        return None


def error(status: int, msg: str) -> JSONResponse:
    return JSONResponse({"error": msg, "error_description": msg, "msg": msg, "message": msg, "statusCode": str(status)}, status_code=status)


def leer_usuario(c, uid):
    return c.execute(f"select {COLUMNAS} from auth.users where id = %s", (uid,)).fetchone()


# ---------------- Auth ----------------
@app.get("/auth/v1/.well-known/jwks.json")
async def jwks():
    return {"keys": [JWK_PUBLICA]}


@app.post("/auth/v1/signup")
async def signup(request: Request):
    body = await request.json()
    with psycopg.connect(DB, autocommit=True) as c:
        if not body.get("email"):  # entrar sin cuenta (signInAnonymously)
            fila = c.execute(f"insert into auth.users (is_anonymous, raw_user_meta_data) values (true, %s) returning {COLUMNAS}",
                             (json.dumps(body.get("data") or {}),)).fetchone()
            return sesion(fila)
        if c.execute("select 1 from auth.users where email = %s", (body["email"],)).fetchone():
            return error(422, "User already registered")
        fila = c.execute(
            f"insert into auth.users (email, encrypted_password, raw_user_meta_data) values (%s, %s, %s) returning {COLUMNAS}",
            (body["email"], hash_pw(body["password"]), json.dumps(body.get("data") or {})),
        ).fetchone()
    return sesion(fila)


@app.post("/auth/v1/token")
async def token(request: Request, grant_type: str):
    body = await request.json()
    with psycopg.connect(DB, autocommit=True) as c:
        if grant_type == "password":
            fila = c.execute(
                f"select {COLUMNAS} from auth.users where email = %s and encrypted_password = %s",
                (body.get("email"), hash_pw(body.get("password", ""))),
            ).fetchone()
        elif grant_type == "refresh_token" and body.get("refresh_token") in refresh_tokens:
            fila = leer_usuario(c, refresh_tokens[body["refresh_token"]])
        else:
            fila = None
    if not fila:
        return error(400, "Invalid login credentials")
    return sesion(fila)


@app.get("/auth/v1/user")
async def user(request: Request):
    cl = claims(request)
    if not cl or not cl.get("sub"):
        return error(401, "invalid JWT")
    with psycopg.connect(DB) as c:
        fila = leer_usuario(c, cl["sub"])
    return usuario_json(fila) if fila else error(401, "user not found")


@app.put("/auth/v1/user")
async def actualizar_usuario(request: Request):
    cl = claims(request)
    if not cl or not cl.get("sub"):
        return error(401, "invalid JWT")
    body = await request.json()
    with psycopg.connect(DB, autocommit=True) as c:
        if body.get("email"):
            if c.execute("select 1 from auth.users where email = %s and id <> %s", (body["email"], cl["sub"])).fetchone():
                return error(422, "A user with this email address has already been registered")
            correos_pendientes[cl["sub"]] = body["email"]  # como en Supabase: queda pendiente hasta confirmar
        if body.get("data"):
            c.execute("update auth.users set raw_user_meta_data = raw_user_meta_data || %s where id = %s", (json.dumps(body["data"]), cl["sub"]))
        if body.get("password"):
            c.execute("update auth.users set encrypted_password = %s where id = %s", (hash_pw(body["password"]), cl["sub"]))
        fila = leer_usuario(c, cl["sub"])
    return usuario_json(fila)


@app.post("/_confirmar_correo/{uid}")
async def confirmar_correo(uid: str):
    """Solo pruebas: simula que la persona abrió el enlace del correo de confirmación."""
    correo = correos_pendientes.pop(uid, None)
    with psycopg.connect(DB, autocommit=True) as c:
        c.execute("update auth.users set email = %s, is_anonymous = false where id = %s", (correo, uid))
        return sesion(leer_usuario(c, uid))


@app.delete("/auth/v1/admin/users/{uid}")
async def borrar_usuario(uid: str, request: Request):
    if (claims(request) or {}).get("role") != "service_role":
        return error(403, "not admin")
    with psycopg.connect(DB, autocommit=True) as c:
        c.execute("delete from auth.users where id = %s", (uid,))
    return {}


@app.post("/auth/v1/logout")
async def logout():
    return Response(status_code=204)


@app.post("/auth/v1/recover")
async def recover():
    return {}


# ---------------- Base de datos (PostgREST) ----------------
@app.api_route("/rest/v1/{ruta:path}", methods=["GET", "POST", "PATCH", "DELETE", "PUT", "HEAD"])
async def rest(ruta: str, request: Request):
    headers = {k: v for k, v in request.headers.items() if k.lower() not in ("host", "content-length", "apikey", "origin")}
    if "authorization" not in {k.lower() for k in headers}:
        headers["authorization"] = f"Bearer {request.headers.get('apikey', ANON_KEY)}"
    r = await http.request(request.method, f"{POSTGREST}/{ruta}", params=request.query_params, content=await request.body(), headers=headers)
    salida = {k: v for k, v in r.headers.items() if k.lower() in ("content-type", "content-range", "preference-applied")}
    return Response(content=r.content, status_code=r.status_code, headers=salida)


# ---------------- Storage ----------------
def como_usuario(cl: dict | None, sql: str, params: tuple, filas: bool = False):
    """Ejecuta una sentencia sobre storage.objects aplicando RLS como el usuario. True si afecta filas (o las filas)."""
    rol = (cl or {}).get("role", "anon")
    rol = rol if rol in ("anon", "authenticated", "service_role") else "anon"
    try:
        with psycopg.connect(DB) as c:
            c.execute(f"set local role {rol}")
            c.execute("select set_config('request.jwt.claims', %s, true)", (json.dumps(cl or {}),))
            cur = c.execute(sql, params)
            return cur.fetchall() if filas else cur.rowcount > 0
    except psycopg.errors.InsufficientPrivilege:
        return [] if filas else False


@app.post("/storage/v1/object/sign/{bucket}")
async def firmar(bucket: str, request: Request):
    cl = claims(request)
    body = await request.json()
    salida = []
    for p in body["paths"]:
        visible = como_usuario(cl, "select 1 from storage.objects where bucket_id = %s and name = %s", (bucket, p))
        if visible:
            t = jwt.encode({"url": f"{bucket}/{p}", "exp": int(time.time()) + int(body["expiresIn"])}, SECRET, algorithm="HS256")
            salida.append({"path": p, "signedURL": f"/object/sign/{bucket}/{p}?token={t}", "error": None})
        else:
            salida.append({"path": p, "signedURL": None, "error": "Either the object does not exist or you do not have access to it"})
    return salida


@app.get("/storage/v1/object/sign/{bucket}/{ruta:path}")
async def descargar_firmado(bucket: str, ruta: str, token: str):
    try:
        datos = jwt.decode(token, SECRET, algorithms=["HS256"])
    except jwt.PyJWTError:
        return error(400, "invalid signature")
    if datos["url"] != f"{bucket}/{ruta}":
        return error(400, "invalid signature")
    archivo = ARCHIVOS / bucket / ruta
    return Response(archivo.read_bytes(), media_type="image/jpeg") if archivo.exists() else error(404, "not found")


@app.post("/storage/v1/object/list/{bucket}")
async def listar(bucket: str, request: Request):
    cl = claims(request)
    body = await request.json()
    prefijo = body.get("prefix", "")
    filas = como_usuario(cl, "select name from storage.objects where bucket_id = %s and name like %s order by name limit %s offset %s",
                         (bucket, prefijo + "%", int(body.get("limit", 100)), int(body.get("offset", 0))), filas=True)
    return [{"name": f[0][len(prefijo):], "id": str(uuid.uuid4())} for f in filas]


@app.post("/storage/v1/object/{bucket}/{ruta:path}")
async def subir(bucket: str, ruta: str, request: Request):
    cl = claims(request)
    tipo = request.headers.get("content-type", "")
    if tipo.startswith("multipart/"):
        form = await request.form()
        archivo = next((v for v in form.values() if hasattr(v, "read")), None)
        if archivo is None:
            return error(400, "no file")
        contenido = await archivo.read()
    else:
        contenido = await request.body()
    ok = como_usuario(cl, "insert into storage.objects (bucket_id, name, owner) values (%s, %s, auth.uid())", (bucket, ruta))
    if not ok:
        return error(403, "new row violates row-level security policy")
    destino = ARCHIVOS / bucket / ruta
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_bytes(contenido)
    return {"Id": str(uuid.uuid4()), "Key": f"{bucket}/{ruta}"}


@app.get("/storage/v1/object/{bucket}/{ruta:path}")
async def descargar(bucket: str, ruta: str, request: Request):
    cl = claims(request)
    if not como_usuario(cl, "select 1 from storage.objects where bucket_id = %s and name = %s", (bucket, ruta)):
        return error(404, "Object not found")
    archivo = ARCHIVOS / bucket / ruta
    return Response(archivo.read_bytes(), media_type="image/jpeg") if archivo.exists() else error(404, "Object not found")


@app.delete("/storage/v1/object/{bucket}")
async def borrar(bucket: str, request: Request):
    cl = claims(request)
    body = await request.json()
    borrados = []
    for p in body.get("prefixes", []):
        if como_usuario(cl, "delete from storage.objects where bucket_id = %s and name = %s", (bucket, p)):
            (ARCHIVOS / bucket / p).unlink(missing_ok=True)
            borrados.append({"name": p})
    return borrados


if __name__ == "__main__":
    # python mini_supabase.py           -> imprime las claves
    # python mini_supabase.py jwks ruta -> escribe el JWKS que necesita PostgREST
    if len(sys.argv) > 2 and sys.argv[1] == "jwks":
        Path(sys.argv[2]).write_text(json.dumps(jwks_para_postgrest()), encoding="utf-8")
    print("ANON_KEY=" + ANON_KEY)
    print("SERVICE_KEY=" + SERVICE_KEY)
