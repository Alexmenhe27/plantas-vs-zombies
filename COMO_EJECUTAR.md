# Cómo ejecutar la app en tu computadora

¿Ya lo tenías funcionando y descargaste una versión nueva? Ve a [Actualizar a una versión nueva](#actualizar-a-una-versión-nueva).

Son 7 pasos. La base de datos ya está lista en Supabase; tú solo instalas programas, pones dos claves y arrancas dos procesos.

## 1. Instala los programas (una sola vez)

| Programa | Versión | Dónde |
|---|---|---|
| Node.js | 22 LTS (mínimo 20.19) | https://nodejs.org |
| Python | 3.11 o más nuevo | https://www.python.org/downloads (en Windows marca **"Add Python to PATH"**) |
| Un editor (opcional) | VS Code | https://code.visualstudio.com |

Comprueba en una terminal (en Windows: PowerShell):

```bash
node -v      # v22.x
npm -v
python --version   # en Mac/Linux puede ser: python3 --version
```

## 2. Descomprime el proyecto

Descarga o clona el proyecto en una carpeta, por ejemplo `Documentos/fauna-y-flora`.
Adentro verás `app/`, `api/`, `supabase/`, `pruebas/` y `README.md`.

## 3. Consigue tus dos claves secretas

**a) Clave secreta de Supabase**
1. Entra a https://supabase.com/dashboard y abre tu proyecto (el de la URL `boppdniulsvoyevhoerp`).
2. Ve a **Project Settings → API Keys**.
3. Copia la clave **secret** (empieza con `sb_secret_…`). Si solo ves la pestaña *Legacy*, copia la **service_role**.

**b) Clave de Google Gemini (gratis, no pide tarjeta)**
1. Entra a https://aistudio.google.com/apikey con tu cuenta de Google.
2. Acepta los términos y pulsa **Create API key**.
3. Copia la clave (empieza con `AIza…`).

El plan gratuito tiene un límite de usos por minuto y por día; si se agota, la app avisa que el servicio no responde y vuelve a funcionar más tarde. Ojo: en el plan gratuito Google puede usar las fotos enviadas para mejorar sus productos.

Estas dos claves **nunca** se comparten ni se pegan en el chat.

## 4. Crea el archivo `api/.env`

1. Dentro de `api/`, copia `.env.example` y renombra la copia a `.env`.
2. Ábrelo y reemplaza estas dos líneas con tus claves:

```
SUPABASE_SERVICE_KEY=sb_secret_xxxxxxxxxxxx
GEMINI_API_KEY=AIzaxxxxxxxxxxxx
```

Lo demás (URL de Supabase, modelo, límite de 10 al día) ya viene lleno.

## 5. Configura los enlaces de correo en Supabase

En el panel de Supabase: **Authentication → URL Configuration**
- **Site URL:** `http://localhost:4200`
- **Redirect URLs:** agrega `http://localhost:4200/**` y `http://localhost:8100/**`

Sirve para que el correo de confirmación y el de "olvidé mi contraseña" regresen a la app.

## 6. Arranca la API (terminal 1)

**Windows (PowerShell):**
```powershell
cd ruta\a\fauna-y-flora\api
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```
Si PowerShell no deja activar el entorno, ejecuta una vez:
`Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`

**Mac / Linux:**
```bash
cd ruta/a/fauna-y-flora/api
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Comprueba: abre http://localhost:8000/salud en el navegador. Debe decir `"estado": "ok"`. Si dice `"incompleto"`, la lista `faltan_variables` indica qué clave falta en `.env`.
**Si no dice "ok", la app no podrá identificar fotos.**
Deja esta terminal abierta.

**Diagnóstico completo (recomendado).** En otra terminal, dentro de `api/` y con el entorno activado:
```
python -m scripts.diagnostico
```
Prueba de verdad tu clave de Supabase, el bucket de fotos, tu clave de Gemini y los modelos, y hace una identificación de prueba.
Debe terminar con *"Todo listo: la API puede identificar fotos."*. Si algo falla, lo marca con `[FALLA]` y dice la causa. Nunca muestra tus claves.
Para probar con una foto tuya: `python -m scripts.diagnostico rutaoto.jpg`.

**Prueba de punta a punta (opcional).** Con la API corriendo, `python -m scripts.prueba_real rutaoto.jpg` hace lo mismo que la app:
crea un usuario temporal, sube la foto, llama a la API, comprueba que se guardó y al final borra todo lo que creó. Gasta 1 identificación de Gemini.

## 7. Arranca la app (terminal 2)

```bash
cd ruta/a/fauna-y-flora/app
npm install
npm start
```

Abre http://localhost:4200. Para verla como teléfono: F12 → icono de móvil (modo dispositivo).

## Comprueba que todo funciona

1. **Regístrate** con tu correo, un nombre de usuario y contraseña.
2. Abre el correo de Supabase y **confirma tu cuenta**; luego inicia sesión.
3. En **Explorar** deben aparecer las especies del catálogo (empieza con 95 y crece con cada especie nueva que identifiques).
4. En **Identificar**, sube una foto de un animal o planta. El navegador pedirá tu ubicación (es opcional; si la das, ayuda a la IA a acertar).
5. Debe aparecer el resultado de la IA y guardarse en **Historial**. El contador baja de 10 a 9.

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
| "El servicio de identificación no responde" | Clave de Gemini mal copiada, o se agotó la cuota gratuita del día (la terminal 1 dice "cuota") |
| Las fotos del catálogo no aparecen (se ve un icono) | Esas fotos vienen de Wikimedia Commons; revisa que la red no bloquee `wikimedia.org` |
| "Gemini tardó demasiado" | Todos los modelos (el principal y los de respaldo) tardaron más de 110 s en total; vuelve a intentar. Corre `python -m scripts.diagnostico` para ver cuánto tarda cada uno |
| "El modelo de Gemini … no está disponible" | Ni el modelo de `IA_MODELO` ni los de respaldo existen para tu clave. `python -m scripts.diagnostico` lista los que sí tienes |
| Cualquier otro error al identificar | Mira la terminal de la API: cada fallo de Gemini se escribe como `WARNING: Gemini (modelo) falló: …` con la causa técnica |
| No llega el correo de confirmación | Revisa spam; el plan gratis de Supabase envía pocos correos por hora |

## Hacerte administrador (opcional)

Después de registrarte, en Supabase → **SQL Editor** ejecuta (cambia el nombre):

```sql
update public.perfiles set rol = 'admin' where nombre_usuario = 'TU_USUARIO';
```

## Probar en tu celular (misma red Wi-Fi)

1. **Averigua la IP de tu computadora.** En una terminal escribe `ipconfig` y busca *Dirección IPv4* del adaptador Wi-Fi (algo como `192.168.1.70`).
2. **API escuchando en la red** (terminal 1, detén con Ctrl+C y vuelve a arrancar así):
   ```
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
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
4. Arranca la API como en el paso 6 (crea el `.venv` y `pip install -r requirements.txt` otra vez, porque la carpeta es nueva).
5. Arranca la app como en el paso 7 (`npm install` y luego `npm start`).
6. En el navegador recarga la página con **Ctrl+Shift+R** para que no use la versión vieja guardada.

La base de datos de Supabase **ya está actualizada**: no tienes que ejecutar ningún SQL. Los scripts quedan en
`supabase/migrations/` y `supabase/seed_imagenes.sql` solo por si algún día creas un proyecto de Supabase nuevo.
