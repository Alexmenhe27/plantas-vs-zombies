"""Levanta todo el sistema en local para las pruebas de punta a punta (Windows, Mac o Linux):

Postgres (127.0.0.1:54329) -> PostgREST :3001 -> mini Supabase :54321
Claude y GBIF falsos :54400 -> API Python :8000 -> app Angular :8100

Requisitos: Postgres 16+ escuchando en 127.0.0.1:54329 (o --pg-bin para arrancarlo aquí), PostgREST
(--postgrest o la variable POSTGREST_BIN) y `pip install -r pruebas/e2e/requirements.txt`.

Uso:
    python pruebas/e2e/levantar.py [--pg-bin C:/ruta/a/postgres/bin] [--postgrest C:/ruta/postgrest.exe]
Deja todo corriendo; Ctrl+C lo detiene. Luego, en otra terminal: python pruebas/e2e/prueba_e2e.py
"""
import argparse
import json
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

import httpx
import psycopg

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parent.parent
sys.path.insert(0, str(AQUI))
import mini_supabase  # noqa: E402  (genera las claves de prueba)

PUERTO_PG = 54329
WINDOWS = os.name == "nt"


def sql(dsn: str, texto: str) -> None:
    with psycopg.connect(dsn, autocommit=True) as c:
        c.execute(texto)


def preparar_base(dsn_postgres: str) -> None:
    with psycopg.connect(dsn_postgres, autocommit=True) as c:
        c.execute("drop database if exists app_e2e with (force)")
        c.execute("create database app_e2e")
    dsn = dsn_postgres.replace("dbname=postgres", "dbname=app_e2e")
    sql(dsn, (RAIZ / "supabase/tests/00_stub_supabase.sql").read_text(encoding="utf-8"))
    for m in sorted((RAIZ / "supabase/migrations").glob("*.sql")):
        sql(dsn, m.read_text(encoding="utf-8"))
    sql(dsn, (RAIZ / "supabase/seed.sql").read_text(encoding="utf-8"))
    sql(dsn, (RAIZ / "supabase/seed_imagenes.sql").read_text(encoding="utf-8"))
    print("Base de datos de prueba lista (migraciones reales + catálogo).")


def arrancar_postgres(pg_bin: Path, datos: Path) -> subprocess.Popen | None:
    try:
        psycopg.connect(f"host=127.0.0.1 port={PUERTO_PG} dbname=postgres user=postgres", connect_timeout=2).close()
        return None  # ya está corriendo
    except psycopg.OperationalError:
        pass
    if not (datos / "PG_VERSION").exists():
        subprocess.run([str(pg_bin / "initdb"), "-D", str(datos), "-U", "postgres", "-A", "trust", "-E", "UTF8", "--locale=C"], check=True)
    return subprocess.Popen([str(pg_bin / "postgres"), "-D", str(datos), "-p", str(PUERTO_PG), "-c", "listen_addresses=127.0.0.1"])


def esperar(url: str, nombre: str, segundos: int = 120) -> None:
    limite = time.time() + segundos
    while time.time() < limite:
        try:
            if httpx.get(url, timeout=3).status_code < 500:
                print(f"  {nombre} listo")
                return
        except httpx.HTTPError:
            pass
        time.sleep(1)
    raise SystemExit(f"{nombre} no respondió en {segundos} s (revisa los logs en {mini_supabase.CARPETA})")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--pg-bin", type=Path, default=os.environ.get("PG_BIN"))
    p.add_argument("--postgrest", default=os.environ.get("POSTGREST_BIN") or shutil.which("postgrest") or "postgrest")
    p.add_argument("--api-python", default=str(RAIZ / "api" / ".venv" / ("Scripts/python.exe" if WINDOWS else "bin/python")))
    args = p.parse_args()

    carpeta = mini_supabase.CARPETA
    logs = carpeta / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    procesos: list[subprocess.Popen] = []

    def lanzar(nombre: str, comando: list[str], cwd: Path, entorno: dict | None = None) -> None:
        salida = open(logs / f"{nombre}.log", "w", encoding="utf-8")
        procesos.append(subprocess.Popen(comando, cwd=cwd, stdout=salida, stderr=subprocess.STDOUT, env={**os.environ, **(entorno or {})},
                                         shell=WINDOWS and comando[0].endswith(".cmd")))

    if args.pg_bin:
        pg = arrancar_postgres(Path(args.pg_bin), carpeta / "pgdata")
        if pg:
            procesos.append(pg)
            time.sleep(3)
    preparar_base(f"host=127.0.0.1 port={PUERTO_PG} dbname=postgres user=postgres")

    jwks = carpeta / "jwks.json"
    jwks.write_text(json.dumps(mini_supabase.jwks_para_postgrest()), encoding="utf-8")
    conf = carpeta / "postgrest.conf"
    conf.write_text(
        f'db-uri = "postgres://authenticator@127.0.0.1:{PUERTO_PG}/app_e2e"\n'
        'db-schemas = "public"\ndb-anon-role = "anon"\n'
        f'jwt-secret = "@{jwks.as_posix()}"\nserver-port = 3001\nserver-host = "127.0.0.1"\n',
        encoding="utf-8",
    )
    (carpeta / "claves.json").write_text(json.dumps({"service": mini_supabase.SERVICE_KEY, "anon": mini_supabase.ANON_KEY}), encoding="utf-8")

    print("Levantando servicios…")
    lanzar("postgrest", [args.postgrest, str(conf)], AQUI)
    lanzar("supabase", [sys.executable, "-m", "uvicorn", "mini_supabase:app", "--port", "54321"], AQUI)
    lanzar("ia", [sys.executable, "-m", "uvicorn", "fake_ia:app", "--port", "54400"], AQUI)
    lanzar("api", [args.api_python, "-m", "uvicorn", "app.main:app", "--port", "8000"], RAIZ / "api", {
        "SUPABASE_URL": "http://127.0.0.1:54321", "SUPABASE_SERVICE_KEY": mini_supabase.SERVICE_KEY,
        "ANTHROPIC_API_KEY": "sk-ant-falsa", "IA_URL": "http://127.0.0.1:54400", "GBIF_URL": "http://127.0.0.1:54400/gbif",
        "IA_MODELO": "claude-haiku-5-5", "IA_RAZONAMIENTO": "bajo",
    })
    lanzar("app", ["npx.cmd" if WINDOWS else "npx", "ng", "serve", "--configuration", "e2e", "--port", "8100"], RAIZ / "app")

    try:
        esperar("http://127.0.0.1:3001/", "PostgREST")
        esperar("http://127.0.0.1:54321/auth/v1/.well-known/jwks.json", "mini Supabase")
        esperar("http://127.0.0.1:54400/gbif/species/match?name=Ara%20militaris", "Claude y GBIF falsos")
        esperar("http://127.0.0.1:8000/salud", "API")
        esperar("http://localhost:8100/", "app", 240)
        print(f"Todo listo. Logs en {logs}. Corre: python pruebas/e2e/prueba_e2e.py   (Ctrl+C para detener)", flush=True)
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        for pr in reversed(procesos):
            try:
                if WINDOWS:
                    subprocess.run(["taskkill", "/F", "/T", "/PID", str(pr.pid)], capture_output=True)
                else:
                    pr.send_signal(signal.SIGTERM)
            except OSError:
                pass


if __name__ == "__main__":
    main()
