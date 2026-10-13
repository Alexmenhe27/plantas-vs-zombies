"""Mini Supabase para pruebas de punta a punta SIN cuenta en la nube.

Imita lo que la app y la API usan de Supabase:
- Auth (/auth/v1): registro, login con contraseña, refresh, usuario, logout, recuperar.
- Base de datos (/rest/v1): se reenvía a PostgREST, que corre sobre el Postgres local con las
  migraciones reales y RLS, así que los permisos que se prueban son los de verdad.
- Storage (/storage/v1): subir, firmar URLs, descargar y borrar fotos. Cada operación se valida
  contra las políticas reales de storage.objects ejecutando como el usuario.

Solo para pruebas locales. No usar en producción.
"""
import hashlib
import json
import os
import secrets
import time
import uuid
from pathlib import Path

import httpx
import jwt
import psycopg
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

DB = os.environ.get("E2E_DB", "host=/tmp port=54329 dbname=pvz user=postgres")
POSTGREST = os.environ.get("E2E_POSTGREST", "http://127.0.0.1:3001")
SECRET = os.environ.get("E2E_JWT_SECRET", "secreto-de-pruebas-locales-de-32-caracteres-o-mas")
ARCHIVOS = Path(os.environ.get("E2E_ARCHIVOS", "/tmp/claude-0/e2e-storage"))
ARCHIVOS.mkdir(parents=True, exist_ok=True)

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"], expose_headers=["*"])
http = httpx.AsyncClient(timeout=30)
refresh_tokens: dict[str, str] = {}


def clave(role: str) -> str:
    return jwt.encode({"role": role, "iss": "mini-supabase", "exp": int(time.time()) + 10 * 365 * 86400}, SECRET, algorithm="HS256")


ANON_KEY = clave("anon")
SERVICE_KEY = clave("service_role")


def hash_pw(pw: str) -> str:
    return hashlib.sha256(pw.encode()).hexdigest()


def usuario_json(fila) -> dict:
    uid, email, meta, creado = fila
    return {
        "id": str(uid), "aud": "authenticated", "role": "authenticated", "email": email,
        "email_confirmed_at": creado.isoformat(), "user_metadata": meta or {}, "app_metadata": {"provider": "email"},
        "created_at": creado.isoformat(), "updated_at": creado.isoformat(),
    }


def sesion(fila) -> dict:
    user = usuario_json(fila)
    exp = int(time.time()) + 3600
    token = jwt.encode(
        {"sub": user["id"], "role": "authenticated", "aud": "authenticated", "email": user["email"], "exp": exp},
        SECRET, algorithm="HS256",
    )
    rt = secrets.token_hex(16)
    refresh_tokens[rt] = user["id"]
    return {"access_token": token, "token_type": "bearer", "expires_in": 3600, "expires_at": exp, "refresh_token": rt, "user": user}


def claims(request: Request) -> dict | None:
    auth = request.headers.get("authorization", "")
    if not auth.lower().startswith("bearer "):
        return None
    try:
        return jwt.decode(auth[7:], SECRET, algorithms=["HS256"], options={"verify_aud": False})
    except jwt.PyJWTError:
        return None


def error(status: int, msg: str) -> JSONResponse:
    return JSONResponse({"error": msg, "error_description": msg, "msg": msg, "message": msg, "statusCode": str(status)}, status_code=status)


# ---------------- Auth ----------------
@app.post("/auth/v1/signup")
async def signup(request: Request):
    body = await request.json()
    with psycopg.connect(DB, autocommit=True) as c:
        if c.execute("select 1 from auth.users where email = %s", (body["email"],)).fetchone():
            return error(422, "User already registered")
        fila = c.execute(
            "insert into auth.users (email, encrypted_password, raw_user_meta_data) values (%s, %s, %s) "
            "returning id, email, raw_user_meta_data, created_at",
            (body["email"], hash_pw(body["password"]), json.dumps(body.get("data") or {})),
        ).fetchone()
    return sesion(fila)


@app.post("/auth/v1/token")
async def token(request: Request, grant_type: str):
    body = await request.json()
    with psycopg.connect(DB, autocommit=True) as c:
        if grant_type == "password":
            fila = c.execute(
                "select id, email, raw_user_meta_data, created_at from auth.users where email = %s and encrypted_password = %s",
                (body.get("email"), hash_pw(body.get("password", ""))),
            ).fetchone()
        elif grant_type == "refresh_token" and body.get("refresh_token") in refresh_tokens:
            fila = c.execute(
                "select id, email, raw_user_meta_data, created_at from auth.users where id = %s",
                (refresh_tokens[body["refresh_token"]],),
            ).fetchone()
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
        fila = c.execute("select id, email, raw_user_meta_data, created_at from auth.users where id = %s", (cl["sub"],)).fetchone()
    return usuario_json(fila) if fila else error(401, "user not found")


@app.put("/auth/v1/user")
async def actualizar_usuario(request: Request):
    cl = claims(request)
    if not cl or not cl.get("sub"):
        return error(401, "invalid JWT")
    body = await request.json()
    with psycopg.connect(DB, autocommit=True) as c:
        if body.get("password"):
            c.execute("update auth.users set encrypted_password = %s where id = %s", (hash_pw(body["password"]), cl["sub"]))
        fila = c.execute("select id, email, raw_user_meta_data, created_at from auth.users where id = %s", (cl["sub"],)).fetchone()
    return usuario_json(fila)


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
def como_usuario(cl: dict | None, sql: str, params: tuple) -> bool:
    """Ejecuta una sentencia sobre storage.objects aplicando RLS como el usuario. True si afecta filas."""
    rol = (cl or {}).get("role", "anon")
    rol = rol if rol in ("anon", "authenticated", "service_role") else "anon"
    try:
        with psycopg.connect(DB) as c:
            c.execute(f"set local role {rol}")
            c.execute("select set_config('request.jwt.claims', %s, true)", (json.dumps(cl or {}),))
            return c.execute(sql, params).rowcount > 0
    except psycopg.errors.InsufficientPrivilege:
        return False


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


@app.post("/storage/v1/object/{bucket}/{ruta:path}")
async def subir(bucket: str, ruta: str, request: Request):
    cl = claims(request)
    form = await request.form()
    archivo = next((v for v in form.values() if hasattr(v, "read")), None)
    if archivo is None:
        return error(400, "no file")
    contenido = await archivo.read()
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
    print("ANON_KEY=" + ANON_KEY)
    print("SERVICE_KEY=" + SERVICE_KEY)
