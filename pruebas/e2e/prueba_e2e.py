"""Prueba de punta a punta en un navegador (teléfono de 390x844) contra el sistema local completo.

Requiere ./levantar.sh corriendo. Guarda capturas en pruebas/e2e/capturas/.
"""
import io
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
from PIL import Image, ImageDraw
from playwright.sync_api import expect, sync_playwright

APP = "http://localhost:8100"
SB = "http://127.0.0.1:54321"
IA = "http://127.0.0.1:54400"
CAPTURAS = Path(__file__).parent / "capturas"
CAPTURAS.mkdir(exist_ok=True)
SERVICE = os.environ["E2E_SERVICE_KEY"]
# Formato que pide Playwright para simular el GPS del navegador.
PUEBLA = {"latitude": 19.0414, "longitude": -98.2063}
CDMX = {"latitude": 19.4326, "longitude": -99.1332}
SUFIJO = str(int(time.time()))[-6:]
CORREO = f"prueba{SUFIJO}@ejemplo.mx"
USUARIO = f"alex_{SUFIJO}"

resultados: list[tuple[str, bool, str]] = []


def paso(nombre: str, ok: bool, detalle: str = "") -> None:
    resultados.append((nombre, ok, detalle))
    print(("OK   " if ok else "FALLO") + f" {nombre} {detalle}", flush=True)


def servicio(method: str, ruta: str, **kw) -> httpx.Response:
    h = {"apikey": SERVICE, "Authorization": f"Bearer {SERVICE}", **kw.pop("headers", {})}
    return httpx.request(method, f"{SB}{ruta}", headers=h, **kw)


def especie(cientifico: str) -> int:
    return servicio("GET", "/rest/v1/especies", params={"select": "id", "nombre_cientifico": f"eq.{cientifico}"}).json()[0]["id"]


def ficha(cientifico: str, comun: str, grupo: str, reino: str = "animal", **extra) -> dict:
    base = {"nombre_cientifico": cientifico, "nombre_comun": comun, "reino": reino, "grupo": grupo, "familia": None,
            "descripcion": None, "habitat": None, "alimentacion": None, "tamano": None, "categoria_nom059": None, "introducida": False}
    return {**base, **extra}


def escenario(**resultado) -> None:
    base = {"problema": "ninguno", "especie": None, "confianza": 0.0, "explicacion": "", "candidatos": []}
    httpx.post(f"{IA}/_escenario", json={**base, **resultado})


def foto_jpeg(color: str) -> bytes:
    img = Image.new("RGB", (2400, 1800), color)
    d = ImageDraw.Draw(img)
    d.ellipse((800, 500, 1600, 1300), fill="#2f8f4e")
    d.rectangle((1100, 1200, 1300, 1700), fill="#6b4a2b")
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=90)
    return buf.getvalue()


def foto_referencia() -> bytes:
    """Foto vertical (600x900) que reemplaza a Wikimedia, que no es accesible desde el entorno de pruebas."""
    img = Image.new("RGB", (600, 900), "#d9c9a3")
    ImageDraw.Draw(img).ellipse((100, 250, 500, 650), fill="#3b6e4f")
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=85)
    return buf.getvalue()


def caja_foto(page, selector: str) -> dict:
    """Tamaño de la caja, tamaño de la imagen dentro y su object-fit (para comprobar que no se deforma)."""
    return page.locator(selector).first.evaluate("""el => {
        const img = el.querySelector('img'); const c = el.getBoundingClientRect(); const i = img.getBoundingClientRect();
        return {ancho: Math.round(c.width), alto: Math.round(c.height), img_ancho: Math.round(i.width), img_alto: Math.round(i.height),
                ajuste: getComputedStyle(img).objectFit, natural: img.naturalWidth + 'x' + img.naturalHeight};
    }""")


def captura(page, nombre: str) -> None:
    page.wait_for_timeout(600)
    page.screenshot(path=str(CAPTURAS / f"{nombre}.png"))


def identificar(page, color="#a7c7e7") -> None:
    page.goto(f"{APP}/app/identificar")
    boton = page.locator("app-inicio").get_by_role("button", name="Subir imagen")
    expect(boton).to_be_visible()
    with page.expect_file_chooser() as fc:
        boton.click()
    fc.value.set_files(files=[{"name": "foto.jpg", "mimeType": "image/jpeg", "buffer": foto_jpeg(color)}])


def main() -> int:
    llamadas_previas = len(httpx.get(f"{IA}/_peticiones").json())
    guacamaya, teporingo, conejo = especie("Ara militaris"), especie("Romerolagus diazi"), especie("Sylvilagus floridanus")
    with sync_playwright() as p:
        nav = p.chromium.launch(executable_path="/opt/pw-browsers/chromium-1194/chrome-linux/chrome")
        ctx = nav.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, geolocation=PUEBLA,
                              permissions=["geolocation"], locale="es-MX", is_mobile=True, has_touch=True)
        page = ctx.new_page()
        errores_consola = []
        # El 404 simulado de una foto de Wikimedia es intencional (prueba el respaldo), no cuenta como error.
        page.on("console", lambda m: errores_consola.append(m.text)
                if m.type == "error" and "wikimedia.org" not in (m.location or {}).get("url", "") else None)
        referencia = foto_referencia()
        fotos_wikimedia = []

        def wikimedia(route):
            fotos_wikimedia.append(route.request.url)
            if "Romerolagus_diazi" in route.request.url:  # enlace roto a propósito
                route.fulfill(status=404, body="no existe")
            else:
                route.fulfill(status=200, content_type="image/jpeg", body=referencia)
        ctx.route("https://*.wikimedia.org/**", wikimedia)

        # 1. Sin sesión redirige a "entrar"
        page.goto(APP)
        page.wait_for_url("**/entrar")
        login = page.locator("app-login")
        expect(login.get_by_text("Descubre la vida silvestre que te rodea")).to_be_visible()
        login.get_by_role("button", name="Iniciar sesión").click()
        expect(login.get_by_text("Escribe tu correo y tu contraseña.")).to_be_visible()
        login.get_by_label("Correo electrónico").fill("nadie@ejemplo.mx")
        login.get_by_label("Contraseña").fill("incorrecta")
        login.get_by_role("button", name="Iniciar sesión").click()
        expect(login.get_by_text("El correo o la contraseña no son correctos.")).to_be_visible()
        captura(page, "01-iniciar-sesion")
        paso("Login rechaza credenciales malas", True)

        # 2. Registro
        login.get_by_role("link", name="Regístrate").click()
        reg = page.locator("app-registro")
        httpx.post(f"{SB}/auth/v1/signup", json={"email": f"ocupado{SUFIJO}@ejemplo.mx", "password": "x123456", "data": {"nombre_usuario": f"ocupado_{SUFIJO}"}})
        reg.get_by_label("Nombre de usuario").fill(f"Ocupado_{SUFIJO}")
        reg.get_by_label("Correo electrónico").fill(CORREO)
        reg.get_by_label("Contraseña (mínimo 6 caracteres)").fill("secreta123")
        reg.get_by_role("button", name="Crear cuenta").click()
        expect(reg.get_by_text("Ese nombre de usuario ya existe. Prueba con otro.")).to_be_visible()
        paso("Registro avisa si el nombre de usuario está ocupado", True)
        reg.get_by_label("Nombre de usuario").fill(USUARIO)
        reg.get_by_label("Correo electrónico").fill(CORREO)
        reg.get_by_label("Contraseña (mínimo 6 caracteres)").fill("secreta123")
        reg.get_by_role("button", name="Crear cuenta").click()
        page.wait_for_url("**/app/identificar")
        expect(page.locator("app-inicio").get_by_role("heading", name=f"Hola, {USUARIO}")).to_be_visible()
        expect(page.locator("app-inicio").get_by_text("Te quedan 10 de 10")).to_be_visible()
        captura(page, "02-inicio")
        paso("Registro crea cuenta y perfil", True)

        # 3. Identificación correcta
        escenario(especie=ficha("Ara militaris", "Guacamaya verde", "ave"), confianza=0.94,
                  explicacion="Plumaje verde, frente roja y cola larga: rasgos de la guacamaya verde.",
                  candidatos=[{"nombre_cientifico": "Ara militaris", "nombre_comun": "Guacamaya verde", "confianza": 0.94}])
        n_especies = len(servicio("GET", "/rest/v1/especies", params={"select": "id"}).json())
        identificar(page)
        page.wait_for_url("**/observacion/**", timeout=20000)
        res = page.locator("app-observacion").last
        expect(res.get_by_role("heading", name="Guacamaya verde")).to_be_visible()
        expect(res.get_by_text("94 % · Muy alta")).to_be_visible()
        expect(res.get_by_text("¡Especie identificada!")).to_be_visible()
        expect(res.get_by_text("En peligro · NOM-059")).to_be_visible()
        captura(page, "03-resultado")
        pet = httpx.get(f"{IA}/_peticiones").json()[-1]
        paso("Identificación correcta de punta a punta (especie ya en el catálogo, sin duplicarla)",
             pet["media_type"] == "image/jpeg" and pet["largo_instrucciones"] < 3000 and pet["razonamiento"] == {"thinkingLevel": "low"}
             and len(servicio("GET", "/rest/v1/especies", params={"select": "id"}).json()) == n_especies,
             f"(petición corta: {pet['largo_instrucciones']} caracteres, sin catálogo; razonamiento {pet['razonamiento']})")

        # La foto llegó comprimida (máx. 1024 px) y sin EXIF
        obs = servicio("GET", "/rest/v1/observaciones", params={"select": "ruta_foto,latitud", "order": "creado_en.desc", "limit": 1}).json()[0]
        foto = servicio("GET", f"/storage/v1/object/fotos/{obs['ruta_foto']}").content
        img = Image.open(io.BytesIO(foto))
        paso("Foto comprimida y sin EXIF", max(img.size) <= 1024 and not img.getexif() and len(foto) < 250_000, f"({img.size[0]}x{img.size[1]}, {len(foto) // 1024} KB)")
        paso("Ubicación guardada", abs(obs["latitud"] - PUEBLA["latitude"]) < 0.01)

        # 4. Ficha de la especie con el avistamiento público
        res.get_by_role("link", name="Ver ficha completa").click()
        page.wait_for_url("**/especie/**")
        pag_ficha = page.locator("app-ficha")
        expect(pag_ficha.get_by_text("Avistamientos recientes")).to_be_visible()
        expect(pag_ficha.get_by_text(USUARIO)).to_be_visible()
        captura(page, "04-ficha")
        paso("Ficha muestra avistamiento público", True)
        expect(pag_ficha.locator("pvz-foto.portada img.lista")).to_be_visible()
        expect(pag_ficha.get_by_role("link", name="Foto de referencia: Wikimedia Commons")).to_have_attribute("href", "https://commons.wikimedia.org/wiki/File:Ara_militaris_-London_Zoo-8a.jpg")
        c = caja_foto(page, "app-ficha pvz-foto.portada")
        paso("Ficha muestra la foto de referencia sin deformarla, con crédito",
             c["ajuste"] == "cover" and c["ancho"] == c["img_ancho"] == 390 and c["alto"] == c["img_alto"] == 390 and c["natural"] == "600x900", f"({c})")

        # 5. Baja confianza -> revisión con especies parecidas
        escenario(especie=ficha("Romerolagus diazi", "Teporingo", "mamifero"), confianza=0.48, explicacion="El animal se ve pequeño y lejos.",
                  candidatos=[{"nombre_cientifico": "Romerolagus diazi", "nombre_comun": "Teporingo", "confianza": 0.48},
                              {"nombre_cientifico": "Sylvilagus floridanus", "nombre_comun": "Conejo serrano", "confianza": 0.31},
                              {"nombre_cientifico": "Lepus callotis", "nombre_comun": "Liebre torda", "confianza": 0.1}])
        identificar(page, "#c9b48a")
        page.wait_for_url("**/observacion/**", timeout=20000)
        res = page.locator("app-observacion").last
        expect(res.get_by_text("No estamos seguros de qué especie es")).to_be_visible()
        expect(res.get_by_text("Conejo serrano")).to_be_visible()
        captura(page, "05-baja-confianza")
        paso("Baja confianza queda en revisión", True)
        cand = res.locator(".candidato")
        expect(cand.nth(1).locator("pvz-foto img.lista")).to_be_visible()
        expect(cand.nth(0).locator("pvz-foto .respaldo ion-icon")).to_be_visible()
        expect(cand.nth(2).get_by_text("Liebre torda")).to_be_visible()
        paso("Especies parecidas (también las que no están en el catálogo); si una foto falla se ve el icono",
             cand.nth(0).locator("pvz-foto img").count() == 0 and cand.nth(2).evaluate("e => e.tagName") == "DIV")

        # 6. Foto borrosa
        escenario(problema="borrosa", explicacion="La imagen está movida; intenta apoyar el teléfono.")
        identificar(page, "#888888")
        page.wait_for_url("**/observacion/**", timeout=20000)
        expect(page.locator("app-observacion").last.get_by_text("La foto salió borrosa")).to_be_visible()
        captura(page, "06-foto-borrosa")
        paso("Foto borrosa muestra consejos", True)

        # 7. Historial
        page.goto(f"{APP}/app/historial")
        hist = page.locator("app-historial")
        expect(hist.get_by_role("heading", name="Mis observaciones")).to_be_visible()
        expect(hist.get_by_text("¿Teporingo?")).to_be_visible()
        expect(hist.get_by_text("En revisión")).to_be_visible()
        stats = hist.locator(".stats dd").all_inner_texts()
        captura(page, "07-historial")
        paso("Historial con estadísticas", stats == ["2", "1", "1"], f"(stats={stats})")

        # 8. Catálogo con filtros
        page.goto(f"{APP}/app/explorar")
        cat = page.locator("app-catalogo")
        cat.get_by_role("button", name="Reptiles").click()
        cat.get_by_role("switch", name="Solo especies protegidas").click()
        expect(cat.get_by_text("Iguana negra")).to_be_visible()
        page.wait_for_function("document.querySelectorAll('app-catalogo pvz-foto img.lista').length >= 5")
        captura(page, "08-catalogo")
        c = caja_foto(page, "app-catalogo pvz-foto.miniatura:has(img.lista)")
        paso("Catálogo muestra miniaturas cuadradas sin deformar", c["ajuste"] == "cover" and c["ancho"] == c["alto"] == 64 == c["img_ancho"] == c["img_alto"], f"({c})")
        n = cat.locator(".conteo").inner_text()
        cat.get_by_role("button", name="Todos").click()
        cat.get_by_role("switch", name="Solo especies protegidas").click()
        cat.get_by_label("Buscar especie").fill("ajolote")
        expect(cat.get_by_text("Ajolote de meseta")).to_be_visible()
        paso("Catálogo filtra por grupo, protección y búsqueda", n == "6 especies", f"({n} reptiles protegidos)")

        # 9. Especie nueva, fotografiada fuera de Puebla: se identifica y se agrega sola al catálogo
        ctx.set_geolocation(CDMX)
        escenario(especie=ficha("Ambystoma mexicanum", "Ajolote mexicano", "anfibio", familia="Ambystomatidae", categoria_nom059="P",
                                descripcion="Salamandra que conserva sus branquias toda la vida.", habitat="Canales de Xochimilco"),
                  confianza=0.92, explicacion="Branquias externas en forma de pluma y cabeza ancha.")
        identificar(page)
        page.wait_for_url("**/observacion/**", timeout=20000)
        res = page.locator("app-observacion").last
        expect(res.get_by_role("heading", name="Ajolote mexicano")).to_be_visible()
        captura(page, "09-especie-nueva")
        nueva = servicio("GET", "/rest/v1/especies", params={"select": "verificada,protegida", "nombre_cientifico": "eq.Ambystoma mexicanum"}).json()
        pet = httpx.get(f"{IA}/_peticiones").json()[-1]
        res.get_by_role("link", name="Ver ficha completa").click()
        expect(page.locator("app-ficha").get_by_text("Ficha generada por la IA")).to_be_visible()
        ctx.set_geolocation(PUEBLA)
        paso("Especie nueva fuera de Puebla: se agrega al catálogo marcada como generada por IA",
             nueva == [{"verificada": False, "protegida": True}] and "latitud 19.43" in pet["pista"], f"({nueva})")

        # 10. Sin conexión: la foto se conserva y se puede reintentar
        identificar(page)
        page.wait_for_url("**/analizando")
        # (se corta la red justo al empezar)
        ctx.set_offline(True)
        ok_offline = True
        try:
            expect(page.locator("app-analizando").get_by_text("No pudimos enviar tu foto")).to_be_visible(timeout=20000)
            captura(page, "10-sin-conexion")
        except AssertionError:
            ok_offline = False
        ctx.set_offline(False)
        if ok_offline:
            escenario(especie=ficha("Ara militaris", "Guacamaya verde", "ave"), confianza=0.9, explicacion="Otra guacamaya.")
            page.locator("app-analizando").get_by_role("button", name="Reintentar").click()
            page.wait_for_url("**/observacion/**", timeout=20000)
        paso("Sin conexión permite reintentar", ok_offline)

        # 11. Límite diario: completar 10 en las últimas 24 h
        uid = servicio("GET", "/rest/v1/perfiles", params={"select": "id", "nombre_usuario": f"eq.{USUARIO}"}).json()[0]["id"]
        usadas = len(servicio("GET", "/rest/v1/observaciones", params={"select": "id", "usuario_id": f"eq.{uid}"}).json())
        ahora = datetime.now(timezone.utc)
        filas = [{"usuario_id": uid, "ruta_foto": f"{uid}/relleno{i}.jpg", "estado": "identificada", "especie_id": guacamaya,
                  "creado_en": (ahora - timedelta(hours=20, minutes=40 - i)).isoformat()} for i in range(10 - usadas)]
        servicio("POST", "/rest/v1/observaciones", json=filas, headers={"Content-Type": "application/json"})
        page.goto(f"{APP}/app/identificar")
        expect(page.locator("app-inicio").get_by_text("Te quedan 0 de 10")).to_be_visible()
        identificar(page)
        lim = page.locator("app-analizando")
        expect(lim.get_by_text("Llegaste al límite de hoy")).to_be_visible(timeout=20000)
        expect(lim.get_by_text("Siguiente identificación disponible en")).to_be_visible()
        captura(page, "11-limite-diario")
        n_ia = len(httpx.get(f"{IA}/_peticiones").json()) - llamadas_previas
        paso("Límite de 10 al día", n_ia == 5, f"(la IA se llamó {n_ia} veces en esta prueba)")

        # 12. Perfil y cerrar sesión
        page.goto(f"{APP}/app/perfil")
        perfil = page.locator("app-perfil")
        expect(perfil.get_by_text(CORREO)).to_be_visible()
        captura(page, "12-perfil")
        perfil.get_by_role("button", name="Cerrar sesión").click()
        page.wait_for_url("**/entrar")
        page.goto(f"{APP}/app/historial")
        page.wait_for_url("**/entrar")
        paso("Cerrar sesión protege las pantallas", True)

        # 13. Otra persona no ve lo privado
        r = httpx.post(f"{SB}/auth/v1/signup", json={"email": f"otra{SUFIJO}@ejemplo.mx", "password": "otra1234", "data": {"nombre_usuario": f"otra_{SUFIJO}"}})
        tok = r.json()["access_token"]
        h = {"apikey": SERVICE, "Authorization": f"Bearer {tok}"}
        propias = httpx.get(f"{SB}/rest/v1/observaciones", params={"select": "id"}, headers=h).json()
        publicas = httpx.get(f"{SB}/rest/v1/observaciones_publicas", params={"select": "id,latitud"}, headers=h).json()
        firmadas = httpx.post(f"{SB}/storage/v1/object/sign/fotos", json={"expiresIn": 60, "paths": [obs["ruta_foto"]]}, headers=h).json()
        prot = all(abs(x["latitud"] * 10 - round(x["latitud"] * 10)) < 1e-9 for x in publicas if x["latitud"] is not None)
        paso("Otra persona: no ve observaciones ajenas, sí las públicas con ubicación aproximada",
             propias == [] and len(publicas) >= 1 and prot and firmadas[0]["signedURL"],
             f"(públicas={len(publicas)})")
        api = httpx.post("http://127.0.0.1:8000/identificar", json={"ruta_foto": obs["ruta_foto"]}, headers={"Authorization": f"Bearer {tok}"})
        paso("La API rechaza fotos de otra persona", api.status_code == 403)

        errores = [e for e in errores_consola if "net::ERR_INTERNET_DISCONNECTED" not in e and "Failed to fetch" not in e and "status of 4" not in e]
        paso("Sin errores en la consola del navegador", not errores, "; ".join(errores[:3]))
        nav.close()

    fallos = [r for r in resultados if not r[1]]
    print(f"\n{len(resultados) - len(fallos)}/{len(resultados)} pasos OK")
    (CAPTURAS / "resultados.json").write_text(json.dumps(resultados, ensure_ascii=False, indent=1))
    return 1 if fallos else 0


if __name__ == "__main__":
    sys.exit(main())
