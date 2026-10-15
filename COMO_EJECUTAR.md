# Cómo ejecutar la app en tu computadora

¿Ya lo tenías funcionando y descargaste una versión nueva? Ve a [Actualizar a una versión nueva](#actualizar-a-una-versión-nueva).

Son 7 pasos. Tú instalas programas, pones dos claves, preparas Supabase (paso 5) y arrancas dos procesos.
Los comandos son para **cmd de Windows**.

## 1. Instala los programas (una sola vez)

| Programa | Versión | Dónde |
|---|---|---|
| Node.js | 22 LTS (mínimo 20.19) | https://nodejs.org |
| Python | 3.11 o más nuevo | https://www.python.org/downloads (en Windows marca **"Add Python to PATH"**) |
| Un editor (opcional) | VS Code | https://code.visualstudio.com |

Comprueba en una ventana de cmd:

```bash
node -v      # v22.x
npm -v
python --version
```

## 2. Descomprime el proyecto

Descarga o clona el proyecto en una carpeta, por ejemplo `Documentos/fauna-y-flora`.
Adentro verás `app/`, `api/`, `supabase/`, `pruebas/` y `README.md`.

## 3. Consigue tus dos claves secretas

**a) Clave secreta de Supabase**
1. Entra a https://supabase.com/dashboard y abre tu proyecto (el de la URL `boppdniulsvoyevhoerp`).
2. Ve a **Project Settings → API Keys**.
3. Copia la clave **secret** (empieza con `sb_secret_…`). Si solo ves la pestaña *Legacy*, copia la **service_role**.

**b) Clave de Claude (de pago: unos 5 dólares alcanzan para miles de fotos)**
1. Entra a https://console.anthropic.com y carga saldo en **Billing**.
2. Ve a **API Keys → Create Key**. Ponle un nombre y, en espacio de trabajo, elige **Default**.
   No uses una clave de ámbito "Organización": Claude la rechaza si no le dices el espacio de trabajo.
3. En la ventana que aparece al crearla, pulsa **Copy**. Es la única vez que se muestra completa
   (unos 100 caracteres). Lo que se ve después en la lista, con "..." en medio, **no** sirve.

## 4. Crea el archivo `api/.env`

En la carpeta `api`, copia `.env.example` como `.env` (en cmd: `copy .env.example .env`) y ábrelo con el Bloc de notas:

```
SUPABASE_URL=https://boppdniulsvoyevhoerp.supabase.co
SUPABASE_SERVICE_KEY=sb_secret_...
ANTHROPIC_API_KEY=sk-ant-...
IA_MODELO=claude-haiku-5-5
CONFIANZA_MINIMA=0.7
CORS_ORIGINS=http://localhost:4200,http://localhost:8100,capacitor://localhost,http://localhost,ionic://localhost
```

Cada clave va completa, en una sola línea. **Nunca pegues este archivo en un chat.**

## 5. Prepara Supabase (una sola vez por versión)

**a) Aplica la migración nueva** (si ya la aplicaste, sáltate esto). En el panel de Supabase: **SQL Editor → New query**.
Abre con el Bloc de notas el archivo `supabase/migrations/20261014000005_rendimiento_seguridad_privacidad.sql`, copia todo,
pégalo y pulsa **Run**. Debe decir *Success*. No borra datos de nadie.

**b) Activa "entrar sin cuenta"** (modo invitado): **Authentication → Sign In / Providers → Allow anonymous sign-ins** → activar → Save.

**c) Enlaces de correo:** **Authentication → URL Configuration**
- **Site URL:** `http://localhost:4200`
- **Redirect URLs:** agrega `http://localhost:4200/**` y `http://localhost:8100/**`

Sirve para que el correo de confirmación, el de "olvidé mi contraseña" y el de un invitado que crea su cuenta regresen a la app.

Los límites (10 al día por persona, 3 por invitado, 500 en total) están en la tabla **ajustes** (Table Editor → ajustes).
Cámbialos ahí si quieres; ya no se configuran en `api/.env`.

## 6. Arranca la API (ventana 1 de cmd)

La primera vez:
```
cd C:\ruta\a\tu\proyecto\api
python -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
```

Cada vez que la quieras arrancar:
```
cd C:\ruta\a\tu\proyecto\api
.venv\Scripts\activate
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```
La línea de cmd debe empezar con `(.venv)`. Déjala abierta.

**Revisa tus claves** (en otra ventana, también con `(.venv)` activado, dentro de `api`):
```
python -m scripts.diagnostico
```
Prueba tu clave de Supabase, el bucket de fotos, que la migración nueva esté aplicada, GBIF y tu clave de Claude,
y hace una identificación de prueba.
Para probar con una foto tuya: `python -m scripts.diagnostico C:\ruta\a\foto.jpg`.

**Prueba de punta a punta (opcional).** Con la API corriendo, `python -m scripts.prueba_real C:\ruta\a\foto.jpg` hace lo mismo que la app:
crea un usuario temporal, sube la foto, llama a la API, comprueba que se guardó y al final borra todo lo que creó.

## 7. Arranca la app (ventana 2 de cmd)

```
cd C:\ruta\a\tu\proyecto\app
npm install
npm run start:red
```
`npm install` solo la primera vez. Abre `http://localhost:4200` en el navegador.

## Comprueba que todo funciona

1. En la bienvenida pulsa **Empezar sin cuenta** (o **Ya tengo cuenta** / **Crear una cuenta gratis**).
2. Toca el **botón de la cámara** (al centro, abajo) o **Galería** en Inicio y elige una foto de un animal o planta.
   El navegador pedirá tu ubicación (es opcional; si la das, ayuda a la IA a acertar).
3. En unos 3 segundos aparece el nombre; la observación se guarda en **Colección**. El contador baja (3 al día sin cuenta, 10 con cuenta).
4. En **Explorar** aparecen las especies del catálogo (empieza con 95 y crece con cada especie nueva que se identifica).
5. En **Perfil** puedes crear tu cuenta (si entraste sin cuenta), cambiar a modo oscuro y decidir si publicas tus observaciones.

## Si algo falla

| Síntoma | Causa probable |
|---|---|
| `npm install` da error de dependencias | Versión de Node vieja; instala Node 22 |
| "No pudimos conectar con el servidor" al identificar | La API (terminal 1) no está corriendo, o en el cel no la arrancaste con `--host 0.0.0.0` |
| "La API no está configurada: faltan …" | Falta el archivo `api/.env` o alguna de sus claves; agrégala y reinicia la API (Ctrl+C y vuelve a arrancarla) |
| "No pudimos conectar con la base de datos" | Clave secreta de Supabase mal copiada en `api/.env`, o el proyecto de Supabase está pausado |
| "No pudimos guardar tu foto: …" | El mensaje dice la causa; si habla de sesión o permiso, cierra sesión y vuelve a entrar |
| "No pudimos leer esa imagen" | La foto está en formato HEIC (iPhone); usa una JPG o PNG |
| "Sin conexión a internet" | Tu equipo de verdad no tiene internet en ese momento |
| "Tu clave de Claude es de ámbito «Organización»…" | Crea una clave nueva del espacio de trabajo **Default** (paso 3b) |
| "La clave de Claude no es válida" | Copiaste la clave abreviada (con "...") o le faltan caracteres. `python -m scripts.diagnostico` dice cuánto mide la que está leyendo (debe ser unos 100) |
| "Tu cuenta de Claude no tiene saldo" | Carga crédito en console.anthropic.com → Billing |
| "Falta instalar…" o `No module named anthropic` | Corriste `pip` o `uvicorn` sin `(.venv)`. Activa el entorno y usa `python -m pip install -r requirements.txt` |
| Las fotos del catálogo no aparecen (se ve un icono) | Esas fotos vienen de Wikimedia Commons; revisa que la red no bloquee `wikimedia.org` |
| "Claude tardó demasiado" o "está saturado" | Pasa muy pocas veces; vuelve a intentar en un momento |
| Cualquier otro error al identificar | La app muestra el motivo, y la ventana 1 escribe `WARNING: Fallo al identificar con Claude: …` con el detalle técnico |
| No llega el correo de confirmación | Revisa spam; el plan gratis de Supabase envía pocos correos por hora |
| "Entrar sin cuenta todavía no está activado" | Falta el paso 5b (Allow anonymous sign-ins) |
| "No pudimos conectar con la base de datos" justo al identificar, y el diagnóstico dice "Falta aplicar … la migración" | Falta el paso 5a |
| "Hoy hubo muchísimas identificaciones…" | Se alcanzó el tope global del día (tabla `ajustes`, `limite_global_diario`) |
| La foto quedó "en espera" | No había conexión o cupo: se identificará sola. En Inicio puedes pulsar **Intentar ahora** o descartarla |
| El mapa sale gris | Los mapas vienen de `tiles.openfreemap.org`; revisa tu conexión o que la red no lo bloquee |

## Hacerte administrador (opcional)

Después de registrarte, en Supabase → **SQL Editor** ejecuta (cambia el nombre):

```sql
update public.perfiles set rol = 'admin' where nombre_usuario = 'TU_USUARIO';
```

Cierra sesión y vuelve a entrar. En **Perfil** aparecerá **Panel de revisión**: ahí confirmas las especies que la IA no supo
(o que eligió la persona) y revisas las fichas que escribió la IA para las especies nuevas.

## Pruebas automáticas de punta a punta (opcional)

Prueban la app completa en un navegador sin usar tu Supabase ni tu saldo de Claude. Necesitan Postgres 16+ y PostgREST
(https://github.com/PostgREST/postgrest/releases):
```
python -m pip install -r pruebas/e2e/requirements.txt
python -m playwright install chromium
python pruebas/e2e/levantar.py --pg-bin C:\ruta\a\postgres\bin --postgrest C:\ruta\a\postgrest.exe
python pruebas/e2e/prueba_e2e.py        (en otra ventana; guarda capturas en pruebas/e2e/capturas)
```

## Probar en tu celular (misma red Wi-Fi)

1. **Averigua la IP de tu computadora.** En una terminal escribe `ipconfig` y busca *Dirección IPv4* del adaptador Wi-Fi (algo como `192.168.1.70`).
2. **API escuchando en la red** (terminal 1, detén con Ctrl+C y vuelve a arrancar así):
   ```
   python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```
3. **App escuchando en la red** (terminal 2, detén con Ctrl+C y arranca así):
   ```
   npm run start:red
   ```
4. Si Windows pregunta por el **Firewall**, pulsa *Permitir* para Python y Node.js en **redes privadas**.
   Tu Wi-Fi debe estar marcada como *red privada* (Configuración → Red e Internet → Wi-Fi → Propiedades).
5. En el navegador del cel abre `http://TU-IP:4200` (ejemplo: `http://192.168.1.70:4200`).
   Comprueba la API desde el cel con `http://TU-IP:8000/salud`.

Qué cambia en el cel en este modo de prueba:
- La foto se toma con la cámara o se elige de la galería: funciona.
- La **ubicación no funciona**: los navegadores solo la dan en páginas https. La app identifica igual, sin ubicación.
- Inicia sesión con una cuenta ya confirmada; el enlace del correo de confirmación abre `localhost`, que solo funciona en la computadora.

## Actualizar a una versión nueva

1. **Detén** la API y la app (Ctrl+C en las dos terminales).
2. **Guarda tu `api/.env`** en otro lugar (por ejemplo el Escritorio). Es el único archivo tuyo que no viene en el zip.
3. Descomprime el zip nuevo en una carpeta nueva y **copia ahí tu `api/.env`** (dentro de `api/`).
4. Arranca la API como en el paso 6 (crea el `.venv` y `python -m pip install -r requirements.txt` otra vez, porque la carpeta es nueva).
5. Arranca la app como en el paso 7 (`npm install` y luego `npm run start:red`).
6. En el navegador recarga la página con **Ctrl+Shift+R** para que no use la versión vieja guardada.

Si la versión nueva trae una migración que todavía no aplicaste (lo dice CAMBIOS.md y `python -m scripts.diagnostico`),
haz el paso 5a con ese archivo. Las migraciones anteriores ya están aplicadas en tu proyecto; quedan en
`supabase/migrations/` (con `supabase/seed.sql` y `supabase/seed_imagenes.sql`) por si algún día creas un proyecto de Supabase nuevo.
