"""Prueba de punta a punta en un navegador (teléfono de 390x844) contra el sistema local completo.

Requiere `python pruebas/e2e/levantar.py` corriendo. Guarda capturas en pruebas/e2e/capturas/.
"""
import io
import json
import sys
import tempfile
import time
from pathlib import Path

import httpx
from PIL import Image, ImageDraw
from playwright.sync_api import expect, sync_playwright

APP = "http://localhost:8100"
SB = "http://127.0.0.1:54321"
IA = "http://127.0.0.1:54400"
API = "http://127.0.0.1:8000"
CAPTURAS = Path(__file__).parent / "capturas"
CAPTURAS.mkdir(exist_ok=True)
CLAVES = json.loads((Path(tempfile.gettempdir()) / "fauna-e2e" / "claves.json").read_text(encoding="utf-8"))
SERVICE, ANON = CLAVES["service"], CLAVES["anon"]
PUEBLA = {"latitude": 19.0414, "longitude": -98.2063}
SUFIJO = str(int(time.time()))[-6:]
CORREO = f"prueba{SUFIJO}@ejemplo.mx"
USUARIO = f"alex_{SUFIJO}"

resultados: list[tuple[str, bool, str]] = []


def paso(nombre: str, ok: bool, detalle: str = "") -> None:
    resultados.append((nombre, ok, detalle))
    print(("OK   " if ok else "FALLO") + f" {nombre} {detalle}", flush=True)


def servicio(method: str, ruta: str, **kw) -> httpx.Response:
    h = {"apikey": SERVICE, "Authorization": f"Bearer {SERVICE}", **kw.pop("headers", {})}
    return httpx.request(method, f"{SB}{ruta}", headers=h, timeout=30, **kw)


def como(token: str, method: str, ruta: str, **kw) -> httpx.Response:
    h = {"apikey": ANON, "Authorization": f"Bearer {token}", **kw.pop("headers", {})}
    return httpx.request(method, f"{SB}{ruta}", headers=h, timeout=30, **kw)


def escenario(comun=None, cientifico=None, grupo="ave", reino="animal", confianza=0.9, candidatos=None, explicacion="Rasgos claros.",
              problema="ninguno", **extra) -> None:
    cands = candidatos if candidatos is not None else (
        [{"nombre_cientifico": cientifico, "nombre_comun": comun, "grupo": grupo, "confianza": confianza}] if cientifico else [])
    httpx.post(f"{IA}/_escenario", json={
        "problema": problema, "nombre_comun": comun, "nombre_cientifico": cientifico, "reino": reino if cientifico else None,
        "grupo": grupo if cientifico else None, "confianza": confianza, "candidatos": cands, "explicacion": explicacion, **extra})


def llamadas_ia() -> int:
    return len([p for p in httpx.get(f"{IA}/_peticiones").json() if p["tipo"] == "identificar"])


def foto_jpeg(color: str) -> bytes:
    img = Image.new("RGB", (2400, 1800), color)
    d = ImageDraw.Draw(img)
    d.ellipse((800, 500, 1600, 1300), fill="#2f8f4e")
    d.rectangle((1100, 1200, 1300, 1700), fill="#6b4a2b")
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=90)
    return buf.getvalue()


def captura(page, nombre: str) -> None:
    page.wait_for_timeout(700)
    page.screenshot(path=str(CAPTURAS / f"{nombre}.png"))


def elegir_foto(page, color="#a7c7e7") -> None:
    """Desde Inicio: botón Galería -> elegir archivo (en el teléfono abre la galería)."""
    page.goto(f"{APP}/app/inicio")
    boton = page.locator("app-inicio").get_by_role("button", name="Galería")
    expect(boton).to_be_enabled()
    with page.expect_file_chooser() as fc:
        boton.click()
    fc.value.set_files(files=[{"name": "foto.jpg", "mimeType": "image/jpeg", "buffer": foto_jpeg(color)}])


def token_de(page) -> str:
    return page.evaluate("() => JSON.parse(localStorage.getItem(Object.keys(localStorage).find(k => k.endsWith('-auth-token')))).access_token")


def nuevo_contexto(nav):
    ctx = nav.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, geolocation=PUEBLA,
                          permissions=["geolocation"], locale="es-MX", is_mobile=True, has_touch=True)
    return ctx


def main() -> int:
    # Se puede correr varias veces: se borran las especies que agregaron corridas anteriores.
    servicio("DELETE", "/rest/v1/especies", params={"verificada": "is.false"})
    with sync_playwright() as p:
        nav = p.chromium.launch(args=["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"])
        ctx = nuevo_contexto(nav)
        page = ctx.new_page()
        errores_consola: list[str] = []
        page.on("console", lambda m: errores_consola.append(f"{m.text} @ {(m.location or {}).get('url', '')}") if m.type == "error" else None)

        # 1. Bienvenida: sin sesión se llega aquí y se puede empezar sin cuenta
        page.goto(APP)
        page.wait_for_url("**/bienvenida")
        bien = page.locator("app-bienvenida")
        expect(bien.get_by_role("heading", name="Descubre qué vive a tu alrededor")).to_be_visible()
        captura(page, "01-bienvenida")
        bien.get_by_role("button", name="Empezar sin cuenta").click()
        page.wait_for_url("**/app/inicio")
        inicio = page.locator("app-inicio")
        expect(inicio.get_by_role("heading", name="Hola, explorador")).to_be_visible()
        expect(inicio.get_by_text("3 de 3")).to_be_visible()
        expect(inicio.get_by_text("Estás usando la app sin cuenta")).to_be_visible()
        captura(page, "02-inicio-invitado")
        paso("Invitado: entra sin cuenta en un toque, con 3 identificaciones al día", True)

        # 2. Identificación por partes: el nombre aparece mientras la IA sigue escribiendo
        base_ia = llamadas_ia()
        escenario("Guacamaya verde", "Ara militaris", confianza=0.94, _pausa=0.12,
                  explicacion="Plumaje verde, frente roja y cola larga: rasgos de la guacamaya verde.")
        elegir_foto(page)
        page.wait_for_url("**/identificar")
        ident = page.locator("app-identificar")
        expect(ident.get_by_role("heading", name="Guacamaya verde")).to_be_visible(timeout=20000)
        escaneando = ident.get_by_text("Analizando rasgos").is_visible()
        captura(page, "03-nombre-llegando")
        expect(ident.get_by_text("¡Especie identificada!")).to_be_visible(timeout=20000)
        expect(ident.get_by_text("Muy alta · 94 %")).to_be_visible()
        expect(ident.get_by_text("En peligro").first).to_be_visible()
        captura(page, "04-resultado")
        pet = [x for x in httpx.get(f"{IA}/_peticiones").json() if x["tipo"] == "identificar"][-1]
        paso("El nombre aparece antes de terminar (streaming)", escaneando, "(se veía 'Analizando rasgos' con el nombre ya escrito)")
        paso("Petición a Claude: Haiku, razonamiento bajo, salida estructurada, instrucciones en caché",
             pet["model"] == "claude-haiku-5-5" and pet["razonamiento"] == "low" and pet["thinking"] is None
             and pet["formato"] == "json_schema" and pet["cache"] and "latitud 19.04" in pet["pista"], f"({pet['largo_instrucciones']} caracteres)")
        obs = servicio("GET", "/rest/v1/observaciones", params={"select": "id,ruta_foto,latitud,es_publica,usuario_id", "order": "creado_en.desc", "limit": 1}).json()[0]
        foto = servicio("GET", f"/storage/v1/object/fotos/{obs['ruta_foto']}").content
        img = Image.open(io.BytesIO(foto))
        page.wait_for_timeout(1500)
        mini = servicio("GET", f"/storage/v1/object/fotos/{obs['ruta_foto'].replace('.jpg', '.mini.jpg')}")
        paso("Foto comprimida (1024 px, sin EXIF) y miniatura de 320 px",
             max(img.size) <= 1024 and not img.getexif() and mini.status_code == 200 and max(Image.open(io.BytesIO(mini.content)).size) <= 320,
             f"({img.size[0]}x{img.size[1]}, {len(foto) // 1024} KB; miniatura {len(mini.content) // 1024} KB)")
        paso("Privada por defecto y con ubicación guardada", obs["es_publica"] is False and abs(obs["latitud"] - PUEBLA["latitude"]) < 0.01)

        # 3. Especie nueva: validada en GBIF, se agrega al catálogo y su ficha llega después del resultado
        escenario("Mirlo dorso rufo", "Turdus rufopalliatus", confianza=0.9, explicacion="Dorso rojizo y pecho gris.",
                  _ficha={"descripcion": "Mirlo de dorso rojizo, común en parques y jardines.", "habitat": "Bosques y ciudades",
                          "alimentacion": "Insectos y frutos", "tamano": "23 a 25 cm", "familia": "Turdidae", "categoria_nom059": None,
                          "introducida": False})
        elegir_foto(page, "#b98a6a")
        page.wait_for_url("**/identificar")
        ident = page.locator("app-identificar")
        expect(ident.get_by_role("heading", name="Mirlo dorso rufo")).to_be_visible(timeout=20000)
        expect(ident.get_by_text("Mirlo de dorso rojizo, común en parques y jardines.")).to_be_visible(timeout=20000)
        captura(page, "05-especie-nueva")
        nueva = servicio("GET", "/rest/v1/especies", params={"select": "verificada,gbif_id,descripcion,familia", "nombre_cientifico": "eq.Turdus rufopalliatus"}).json()
        fichas = [x for x in httpx.get(f"{IA}/_peticiones").json() if x["tipo"] == "ficha"]
        paso("Especie nueva: validada en GBIF, sin verificar, con ficha escrita aparte (sin foto)",
             len(nueva) == 1 and nueva[0]["verificada"] is False and nueva[0]["gbif_id"] and nueva[0]["descripcion"]
             and fichas and "Turdus rufopalliatus" in fichas[-1]["texto"], f"({nueva})")

        # 4. La IA duda: la persona elige entre las parecidas
        escenario("Teporingo", "Romerolagus diazi", grupo="mamifero", confianza=0.45, explicacion="El animal se ve pequeño y lejos.",
                  candidatos=[{"nombre_cientifico": "Romerolagus diazi", "nombre_comun": "Teporingo", "grupo": "mamifero", "confianza": 0.45},
                              {"nombre_cientifico": "Sylvilagus floridanus", "nombre_comun": "Conejo serrano", "grupo": "mamifero", "confianza": 0.35},
                              {"nombre_cientifico": "Lepus callotis", "nombre_comun": "Liebre torda", "grupo": "mamifero", "confianza": 0.1}])
        elegir_foto(page, "#c9b48a")
        ident = page.locator("app-identificar")
        expect(ident.get_by_role("heading", name="¿Cuál de estas es?")).to_be_visible(timeout=20000)
        expect(ident.get_by_text("Liebre torda")).to_be_visible()
        captura(page, "06-cual-de-estas")
        ident.locator(".candidato", has_text="Conejo serrano").get_by_role("button", name="Es esta").click()
        expect(ident.get_by_text("Elegida por ti")).to_be_visible(timeout=15000)
        expect(ident.get_by_role("heading", name="Conejo serrano")).to_be_visible()
        captura(page, "07-elegida")
        ultima = servicio("GET", "/rest/v1/observaciones", params={"select": "estado,especie:especies(nombre_cientifico)", "order": "creado_en.desc", "limit": 1}).json()[0]
        paso("¿Cuál de estas es?: la elección se guarda", ultima["estado"] == "elegida" and ultima["especie"]["nombre_cientifico"] == "Sylvilagus floridanus")

        # 5. Límite del invitado: la 4.ª no gasta IA; borrar observaciones no devuelve el cupo
        tok = token_de(page)
        borrar = como(tok, "DELETE", "/rest/v1/observaciones", params={"id": f"eq.{obs['id']}"})
        cupo = como(tok, "POST", "/rest/v1/rpc/mi_cupo", json={}).json()
        antes = llamadas_ia()
        elegir_foto(page, "#888888")
        ident = page.locator("app-identificar")
        expect(ident.get_by_role("heading", name="Llegaste al límite de hoy")).to_be_visible(timeout=20000)
        expect(ident.get_by_role("link", name="Crear mi cuenta gratis")).to_be_visible()
        captura(page, "08-limite-invitado")
        paso("Límite del invitado: 3 al día, borrar no devuelve el cupo, la 4.ª no llama a la IA",
             borrar.status_code in (200, 204) and cupo["restantes"] == 0 and llamadas_ia() == antes and antes - base_ia == 3,
             f"(cupo tras borrar: {cupo['restantes']}; llamadas a la IA: {antes - base_ia})")
        ident.get_by_role("button", name="Identificarla cuando se libere").click()
        expect(ident.get_by_text("La identificaremos en cuanto se pueda")).to_be_visible()
        paso("Sin cupo se puede dejar la foto en espera", True)

        # 6. Colección del invitado
        page.goto(f"{APP}/app/coleccion")
        col = page.locator("app-coleccion")
        expect(col.get_by_role("heading", name="Mi colección")).to_be_visible()
        page.wait_for_function("document.querySelectorAll('app-coleccion app-tarjeta-especie').length >= 2")
        stats = col.locator(".stats dd").all_inner_texts()
        captura(page, "09-coleccion")
        col.get_by_role("tab", name="Observaciones").click()
        expect(col.get_by_text("Elegida", exact=True)).to_be_visible()
        captura(page, "10-coleccion-observaciones")
        paso("Colección con especies y estadísticas", stats[0] == "2", f"(stats={stats})")
        col.get_by_role("tab", name="Mapa").click()
        page.wait_for_timeout(9000)
        lienzo = col.locator("app-mapa canvas")
        captura(page, "11-coleccion-mapa")
        paso("Mapa propio con MapLibre (ubicación exacta, solo la ve la persona)", lienzo.count() == 1 and lienzo.is_visible())

        # 7. El invitado crea su cuenta sin perder nada
        page.goto(f"{APP}/app/perfil?crear=1")
        perfil = page.locator("app-perfil")
        perfil.get_by_label("Correo electrónico").fill(f"invitado{SUFIJO}@ejemplo.mx")
        perfil.get_by_label("Nombre de usuario").fill(f"inv_{SUFIJO}")
        perfil.get_by_role("button", name="Crear mi cuenta").click()
        expect(perfil.get_by_text("Te enviamos un correo")).to_be_visible(timeout=15000)
        captura(page, "12-crear-cuenta")
        uid_inv = page.evaluate("() => JSON.parse(localStorage.getItem(Object.keys(localStorage).find(k => k.endsWith('-auth-token')))).user.id")
        httpx.post(f"{SB}/_confirmar_correo/{uid_inv}")
        usuario = servicio("GET", "/rest/v1/perfiles", params={"select": "nombre_usuario", "id": f"eq.{uid_inv}"}).json()
        n_obs = len(servicio("GET", "/rest/v1/observaciones", params={"select": "id", "usuario_id": f"eq.{uid_inv}"}).json())
        paso("Invitado -> cuenta: mismo usuario, conserva sus observaciones", usuario[0]["nombre_usuario"] == f"inv_{SUFIJO}" and n_obs == 2,
             f"({usuario}, {n_obs} observaciones)")
        page.goto(f"{APP}/app/inicio")
        expect(page.locator("app-inicio").get_by_text("10", exact=False).first).to_be_visible()
        expect(page.locator("app-inicio").get_by_text("Estás usando la app sin cuenta")).to_have_count(0, timeout=15000)
        paso("Al confirmar el correo, la app deja de tratarlo como invitado (sin volver a entrar)", True)
        expect(page.locator("app-tabs .globo")).to_have_count(0, timeout=30000)
        paso("La foto que esperaba cupo se identifica sola al tener cuenta", llamadas_ia() == antes + 1, f"(llamadas: {llamadas_ia() - base_ia})")

        # 8. Modo oscuro
        page.goto(f"{APP}/app/perfil")
        perfil = page.locator("app-perfil")
        page.wait_for_function("document.documentElement.classList.contains('ion-palette-dark')", timeout=5000)
        captura(page, "13-perfil-oscuro")
        paso("La app siempre usa el modo oscuro", True)
        ctx.close()

        # 9. Persona registrada
        ctx = nuevo_contexto(nav)
        page = ctx.new_page()
        page.on("console", lambda m: errores_consola.append(f"{m.text} @ {(m.location or {}).get('url', '')}") if m.type == "error" else None)
        page.goto(f"{APP}/registro")
        reg = page.locator("app-registro")
        reg.get_by_label("Nombre de usuario").fill(USUARIO)
        reg.get_by_label("Correo electrónico").fill(CORREO)
        reg.get_by_label("Contraseña (mínimo 6 caracteres)").fill("secreta123")
        captura(page, "16-registro")
        reg.get_by_role("button", name="Crear cuenta").click()
        page.wait_for_url("**/app/inicio")
        expect(page.locator("app-inicio").get_by_text("10 de 10")).to_be_visible()
        captura(page, "17-inicio")
        paso("Registro: cuenta con 10 identificaciones al día", True)

        # 10. Explorar: búsqueda sin acentos y filtros
        page.goto(f"{APP}/app/explorar")
        cat = page.locator("app-catalogo")
        cat.get_by_label("Buscar especie").fill("buho")
        expect(cat.locator("app-tarjeta-especie", has_text="Búho cornudo")).to_be_visible(timeout=10000)
        captura(page, "18-explorar-busqueda")
        cat.get_by_label("Buscar especie").fill("")
        cat.get_by_role("button", name="Reptiles").click()
        cat.get_by_role("button", name="Protegidas").click()
        expect(cat.get_by_text("Iguana negra")).to_be_visible(timeout=10000)
        n = cat.locator(".conteo").inner_text()
        paso("Explorar: búsqueda sin acentos en el servidor, filtros por grupo y protección", n.startswith("6 especies"), f"({n})")

        # 11. Publicar un avistamiento (ubicación aproximada) y verlo en el mapa público
        escenario("Zanate mayor", "Quiscalus mexicanus", confianza=0.93, explicacion="Plumaje negro iridiscente y cola en forma de quilla.")
        elegir_foto(page, "#222222")
        ident = page.locator("app-identificar")
        expect(ident.get_by_text("¡Especie identificada!")).to_be_visible(timeout=20000)
        ident.get_by_role("switch", name="Publicar avistamiento").click()
        page.wait_for_timeout(1000)
        zanate = servicio("GET", "/rest/v1/observaciones", params={"select": "id,ruta_foto,es_publica,especie_id", "order": "creado_en.desc", "limit": 1}).json()[0]
        paso("Publicar desde el resultado", zanate["es_publica"] is True)
        ident.get_by_role("link", name="Ver ficha").click()
        page.wait_for_url("**/especie/**")
        ficha = page.locator("app-ficha")
        expect(ficha.get_by_role("heading", name="Avistamientos")).to_be_visible()
        expect(ficha.get_by_text(USUARIO)).to_be_visible()
        page.wait_for_timeout(2500)
        captura(page, "19-ficha")
        paso("Ficha con avistamiento público y ubicación aproximada", ficha.get_by_text("ubicación aproximada").count() >= 1)
        page.goto(f"{APP}/app/explorar")
        page.locator("app-catalogo").get_by_role("tab", name="Mapa").click()
        page.wait_for_timeout(5000)
        captura(page, "20-explorar-mapa")
        paso("Mapa público", page.locator("app-catalogo app-mapa canvas").count() == 1)

        # 12. Otra persona: no ve lo privado; lo público sin ubicación exacta
        otro = httpx.post(f"{SB}/auth/v1/signup", json={"email": f"otra{SUFIJO}@ejemplo.mx", "password": "otra1234",
                                                         "data": {"nombre_usuario": f"otra_{SUFIJO}"}}).json()["access_token"]
        ajenas = como(otro, "GET", "/rest/v1/observaciones", params={"select": "id"}).json()
        publicos = como(otro, "POST", "/rest/v1/rpc/avistamientos_publicos", json={"p_especie_id": None, "p_limite": 50}).json()
        firm = como(otro, "POST", "/storage/v1/object/sign/fotos", json={"expiresIn": 60, "paths": [zanate["ruta_foto"]]}).json()
        aprox = all(x["latitud"] is None or abs(x["latitud"] * 10 - round(x["latitud"] * 10)) < 1e-9 for x in publicos)
        api_ajena = httpx.post(f"{API}/identificar", json={"ruta_foto": zanate["ruta_foto"]}, headers={"Authorization": f"Bearer {otro}"})
        paso("Otra persona no ve lo privado; lo público con ubicación aproximada; la API rechaza fotos ajenas",
             ajenas == [] and len(publicos) == 1 and aprox and firm[0]["signedURL"] and api_ajena.status_code == 403,
             f"(públicos={len(publicos)}, latitud={publicos[0]['latitud'] if publicos else None})")

        # 13. "¿No es correcto?" desde la observación guardada
        page.goto(f"{APP}/observacion/{zanate['id']}")
        obs_pag = page.locator("app-observacion")
        expect(obs_pag.get_by_role("heading", name="Zanate mayor")).to_be_visible(timeout=15000)
        obs_pag.get_by_role("button", name="¿No es correcto?").click()
        page.locator("ion-alert").get_by_role("button", name="Mandar a revisión").click()
        expect(obs_pag.get_by_role("heading", name="¿Cuál de estas es?")).to_be_visible(timeout=10000)
        captura(page, "21-no-es-correcto")
        paso("¿No es correcto? manda a revisión", servicio("GET", "/rest/v1/observaciones", params={"select": "estado", "id": f"eq.{zanate['id']}"}).json()[0]["estado"] == "revisar")

        # 14. Sin conexión: la foto queda en espera y se identifica sola al volver la señal
        escenario("Cardenal rojo", "Cardinalis cardinalis", confianza=0.92, explicacion="Plumaje rojo y cresta.")
        page.goto(f"{APP}/app/inicio")
        boton = page.locator("app-inicio").get_by_role("button", name="Galería")
        expect(boton).to_be_enabled()
        page.wait_for_timeout(3000)  # la app precarga sus pantallas al arrancar; sin conexión ya no podría descargarlas
        ctx.set_offline(True)
        with page.expect_file_chooser() as fc:
            boton.click()
        fc.value.set_files(files=[{"name": "foto.jpg", "mimeType": "image/jpeg", "buffer": foto_jpeg("#cc2222")}])
        expect(page.locator("app-identificar").get_by_text("La identificaremos en cuanto se pueda")).to_be_visible(timeout=15000)
        captura(page, "22-en-espera")
        ctx.set_offline(False)
        expect(page.get_by_text("Tu foto en espera se identificó: Cardenal rojo")).to_be_visible(timeout=30000)
        captura(page, "23-espera-resuelta")
        paso("Sin conexión: se guarda en el teléfono y se identifica sola al volver la señal", True)

        # 15. Panel de revisión (administrador)
        uid = servicio("GET", "/rest/v1/perfiles", params={"select": "id", "nombre_usuario": f"eq.{USUARIO}"}).json()[0]["id"]
        servicio("PATCH", "/rest/v1/perfiles", params={"id": f"eq.{uid}"}, json={"rol": "admin"}, headers={"Content-Type": "application/json"})
        page.goto(f"{APP}/app/perfil")
        page.reload()
        expect(page.locator("app-perfil").get_by_role("link", name="Panel de revisión")).to_be_visible(timeout=15000)
        page.locator("app-perfil").get_by_role("link", name="Panel de revisión").click()
        page.wait_for_url("**/revision")
        rev = page.locator("app-revision")
        tarjeta = rev.locator("article", has_text="Zanate mayor").first
        expect(tarjeta).to_be_visible(timeout=15000)
        captura(page, "24-revision")
        tarjeta.get_by_role("button", name="Confirmar Zanate mayor").click()
        expect(page.get_by_text("Especie confirmada.")).to_be_visible()
        rev.get_by_role("button", name="Fichas de la IA").click()
        expect(rev.get_by_text("Mirlo dorso rufo")).to_be_visible()
        captura(page, "25-revision-fichas")
        paso("Panel de revisión: el admin confirma la especie",
             servicio("GET", "/rest/v1/observaciones", params={"select": "estado", "id": f"eq.{zanate['id']}"}).json()[0]["estado"] == "corregida")

        esperados = ("net::ERR_INTERNET_DISCONNECTED", "Failed to fetch", "status of 4", "ERR_NAME_NOT_RESOLVED", "openfreemap", "wikipedia",
                     "Mapa:", "WebGL", "ERR_ABORTED")
        errores = [e for e in errores_consola if not any(x in e for x in esperados)]
        paso("Sin errores inesperados en la consola del navegador", not errores, "; ".join(errores[:4]))
        nav.close()

    fallos = [r for r in resultados if not r[1]]
    print(f"\n{len(resultados) - len(fallos)}/{len(resultados)} pasos OK")
    (CAPTURAS / "resultados.json").write_text(json.dumps(resultados, ensure_ascii=False, indent=1), encoding="utf-8")
    return 1 if fallos else 0


if __name__ == "__main__":
    sys.exit(main())
