# Despliegue de miCangrejo en Vercel (un proyecto, dos servicios)

> **Estado (12/09/2026 01:25):** desplegado en **<https://micangrejo.vercel.app>** desde el CLI
> (`vercel deploy --prod` en la raíz del repo), proyecto `micangrejo` en la cuenta `cornelio-guerra`, con
> las variables cargadas desde `backend/.env`. Webhook de Meta:
> `https://micangrejo.vercel.app/api/v1/webhooks/whatsapp`. La primera petición tras un rato sin uso
> tarda ~8 s (arranque en frío): abrir `/api/v1/health` antes de la demo.
>
> **Correo en producción: Resend por SMTP** (`SMTP_HOST=smtp.resend.com`, `SMTP_PORT=587`,
> `SMTP_USER=resend`, `SMTP_PASSWORD=<API key>`, `MAIL_FROM=onboarding@resend.dev`), verificado de punta a
> punta desde Vercel. Gmail bloquea el inicio de sesión SMTP desde las IPs de Vercel (`534 5.7.9 Please log
> in with your web browser`) y, tras varios intentos, también desde local; solo sirve como alternativa de
> pruebas con contraseña de aplicación. Sin dominio verificado, Resend entrega únicamente al correo con el
> que se creó la cuenta: por eso la cuenta es la del buzón del equipo, el mismo de `MAIL_DEMO_OVERRIDE_TO`.


Guía paso a paso para Cornelio. Objetivo: publicar **frontend y backend en un solo proyecto de
Vercel** (plan Hobby) usando **Services**, de modo que ambos compartan dominio:

| Ruta pública | Servicio | Qué es |
|---|---|---|
| `https://<proyecto>.vercel.app/` | `frontend` | React + Vite (estático, servido desde la CDN) |
| `https://<proyecto>.vercel.app/api/*` | `backend` | FastAPI (`app.main:app`) como Vercel Function, Python 3.13 |

Ventajas de esta forma: **sin CORS** (mismo origen), una sola URL fija para el **webhook de Meta**,
y un solo panel de variables de entorno.

> Fuentes consultadas (septiembre 2026): `vercel.com/docs/services`, `/docs/services/config-reference`,
> `/docs/services/routing`, `/docs/services/pricing`, `/docs/frameworks/backend/fastapi`,
> `/docs/functions/runtimes/python`, `/docs/functions/runtimes/python/python-version`,
> `/docs/project-configuration/vercel-json`, `/docs/deployments/vercel-ignore`, `/docs/cli/env`.
> Según Vercel, *"Services are available in Beta on all plans"* (incluye Hobby).

---

## 0. Qué hay ya en el repositorio

| Archivo | Para qué sirve |
|---|---|
| `vercel.json` (raíz) | Declara los dos servicios y las dos reglas de enrutamiento. Validado contra `https://openapi.vercel.sh/vercel.json`. |
| `.vercelignore` (raíz) | Evita subir `node_modules`, `.venv`, bases SQLite, pruebas y documentos de trabajo. |
| `backend/.python-version` | `3.13`. Vercel lee este archivo en la raíz del servicio para elegir la versión de Python (soporta 3.12 por defecto, 3.13 y 3.14). |
| `backend/requirements.txt` | Dependencias del backend; Vercel las instala automáticamente. |
| `backend/.env.example` | Nombres exactos de todas las variables de entorno. |

Resumen de `vercel.json`:

```json
{
  "$schema": "https://openapi.vercel.sh/vercel.json",
  "services": {
    "frontend": { "root": "frontend/", "framework": "vite",
                  "rewrites": [ { "source": "/(.*)", "destination": "/index.html" } ] },
    "backend":  { "root": "backend/", "framework": "fastapi", "entrypoint": "app.main:app",
                  "functions": { "app/main.py": { "maxDuration": 60,
                                 "excludeFiles": "{tests/**,.venv/**,data/*.db,scripts/**,**/__pycache__/**}" } } }
  },
  "rewrites": [
    { "source": "/api/(.*)", "destination": { "service": "backend" } },
    { "source": "/(.*)",     "destination": { "service": "frontend" } }
  ]
}
```

Puntos que conviene entender:

- **El orden de los `rewrites` importa**: Vercel evalúa de arriba abajo y la primera que coincide
  gana. `/api/(.*)` va antes del comodín `/(.*)`.
- **El backend recibe la ruta original** (`/api/v1/health` llega como `/api/v1/health`, no como
  `/v1/health`). Por eso `app/main.py` monta todos los routers con `prefix="/api/v1"` y no hace
  falta ningún recorte de ruta.
- Con `services`, las claves `framework`, `functions`, `buildCommand`, `outputDirectory`, etc.
  **no pueden ir en el nivel superior**: van dentro de cada servicio (así está hecho).
- `maxDuration: 60` s (el máximo en Hobby es 300 s). Gemini tiene 20 s de timeout y cada correo
  SMTP 15 s; si un envío a varias entidades se acerca al límite, sube el valor (hasta 300).
- El `rewrite` interno del servicio `frontend` (`/(.*)` → `/index.html`) es el *fallback* típico de
  una SPA: si mañana el frontend usa rutas del navegador (`/admin`, `/reporte/MC-2026-0001`), al
  recargar la página seguirá cargando `index.html`. Los archivos reales (`/assets/*.js`) se sirven
  antes de aplicar el rewrite. Hoy el frontend no usa enrutador, así que es inofensivo.
- Límites del plan Hobby ya verificados: **300 s** de duración máxima, **4,5 MB** de cuerpo por
  petición (por eso las fotos van directas a Supabase Storage y nunca por el backend), **500 MB**
  de bundle Python.

---

## 1. Preparar Supabase (base de datos + fotos)

### 1.1 Crear el proyecto

1. Entra a <https://supabase.com/dashboard> → **New project**. Región: la más cercana a la región
   de Vercel (por defecto Vercel despliega funciones en `iad1`, Washington; elige *East US* en
   Supabase para reducir latencia).
2. Guarda la **contraseña de la base de datos** que escribas al crearlo: la necesitas en la cadena
   de conexión.

### 1.2 Cadena del pooler en modo transacción (puerto 6543)

El backend está preparado para el **pooler en modo transacción** (usa `NullPool` y desactiva los
*prepared statements* de psycopg 3, que ese modo no admite). Es el modo correcto para funciones
serverless: cada invocación abre y cierra su conexión.

1. En el panel de Supabase pulsa **Connect** (barra superior) → pestaña **Connection String**.
2. Elige **Transaction pooler** (verás que el puerto es **6543**; el *Session pooler* usa 5432 y la
   conexión directa no sirve desde Vercel porque es solo IPv6 en el plan gratuito).
3. Copia la cadena. Tiene esta forma:

   ```text
   postgresql://postgres.<ref-del-proyecto>:[YOUR-PASSWORD]@aws-0-<region>.pooler.supabase.com:6543/postgres
   ```

4. Sustituye `[YOUR-PASSWORD]` por la contraseña. Si la contraseña tiene caracteres como `@`, `#`,
   `/` o `:`, **codifícalos en URL** (`@` → `%40`, `#` → `%23`, `/` → `%2F`, `:` → `%3A`).
5. Ese valor completo es `DATABASE_URL`. No hace falta cambiar `postgresql://` por
   `postgresql+psycopg://`: `app/database.py` lo hace solo.

Las tablas (`entities`, `routing_rules`, `cases`, `case_entities`, `status_history`) se crean solas
en el primer arranque (`SQLModel.metadata.create_all`) y el catálogo se siembra desde
`backend/app/data/catalog.json`. No hay migraciones que ejecutar.

> **Importante:** en Vercel `DATABASE_URL` es, en la práctica, **obligatoria**. El modo de
> contingencia con SQLite escribe en `backend/data/micangrejo.db`, y el sistema de archivos de una
> Vercel Function es de solo lectura (salvo `/tmp`): sin `DATABASE_URL` la función fallará al
> arrancar. La contingencia con SQLite es solo para la laptop.

### 1.3 Bucket `evidencias` en Storage

1. **Storage** → **New bucket** → nombre exactamente `evidencias` (o el valor que pongas en
   `SUPABASE_BUCKET`).
2. Márcalo como **Public bucket**. Motivo: `storage_service.read_url()` construye la URL pública
   con `get_public_url()`, que **no falla** aunque el bucket sea privado (solo devuelve un enlace que
   no abre). Con bucket público, `photo_url` en el expediente y en el correo a la entidad funciona
   directamente. Si el equipo prefiere bucket privado, hay que cambiar `read_url` para usar siempre
   `create_signed_url` (cambio de backend, fuera de esta guía).
3. Opcional pero recomendable: en el bucket, **Allowed MIME types** = `image/jpeg, image/png,
   image/webp` y **Max file size** = 5 MB (coincide con `MAX_PHOTO_BYTES` del backend).
4. No hace falta ninguna política RLS adicional para la subida: el backend firma la URL con la
   `service_role` y el navegador hace `PUT` contra esa URL firmada.

### 1.4 Claves

**Project Settings** → **API**:

- **Project URL** → `SUPABASE_URL` (por ejemplo `https://abcd1234.supabase.co`).
- **service_role** (secret) → `SUPABASE_SERVICE_ROLE_KEY`. **Solo en el servidor.** Nunca la
  pongas en una variable `VITE_*`, en el frontend ni en un mensaje del grupo: da acceso total al
  proyecto saltándose RLS.

---

## 2. Crear el proyecto en Vercel desde GitHub

1. Entra a <https://vercel.com/new> con la cuenta que va a administrar el proyecto.
2. **Import Git Repository** → conecta GitHub si no lo está → busca `CarlosR10/2G_IIRetoEmprende`
   → **Import**. (Si el repositorio es de otra cuenta/organización, esa persona debe autorizar la
   app de Vercel en GitHub o transferir el acceso.)
3. En la pantalla **Configure Project**:
   - **Project Name**: por ejemplo `micangrejo`. Ese nombre define la URL
     `https://micangrejo.vercel.app` (si está libre) que se usa para el webhook de Meta.
   - **Framework Preset**: debe quedar en **Services** (Vercel lo detecta al ver la clave
     `services` en `vercel.json`). Si aparece "Other" o "Vite", cámbialo a **Services** a mano:
     con otro preset el proyecto se construiría como un solo frontend y `/api/*` daría 404.
   - **Root Directory**: déjalo **vacío** (raíz del repo). `vercel.json` está en la raíz y las
     rutas `frontend/` y `backend/` se resuelven desde ahí. No pongas `frontend` ni `backend`.
   - **Build and Output Settings**: no toques nada; cada servicio trae su configuración.
   - **Environment Variables**: puedes cargarlas aquí o después (sección 3). Es más cómodo hacerlo
     antes del primer *deploy* para no tener que redesplegar.
4. **Deploy**. El primer despliegue es siempre de producción.
5. Cuando termine, en **Settings → Git** confirma que la **Production Branch** es la rama que el
   equipo usa como estable (`main`). Cada *push* a otra rama genera un *Preview* con su propia URL;
   el webhook de Meta debe apuntar siempre a la URL de producción.

---

## 3. Variables de entorno

**Settings → Environment Variables** del proyecto. Marca **Production** y **Preview** para todas
(así los *previews* también funcionan), y **Development** para las que quieras usar con
`vercel dev`. Marca como *Sensitive* las claves y contraseñas.

Con Services, **todas las variables del proyecto están disponibles para los dos servicios**; no
hay que duplicarlas.

### 3.1 Frontend (Vite)

| Variable | Valor en Vercel | Nota |
|---|---|---|
| `VITE_API_BASE_URL` | `/api/v1` | **Obligatoria.** Vite la incrusta **en tiempo de build**: si la cambias, hay que redesplegar. Es una ruta relativa, así que las llamadas van al mismo dominio y no hay CORS. Ver sección 4. |

### 3.2 Backend: tabla completa (`backend/.env.example`)

Regla general del backend: **todas son opcionales**; lo que falte entra en modo de contingencia.
La columna "Obligatoria para" indica qué integración deja de ser real si falta.

| Variable | Obligatoria para | Valor / de dónde sale |
|---|---|---|
| `DATABASE_URL` | **Base de datos real** (en Vercel: siempre, ver 1.2) | Cadena del *Transaction pooler*, puerto 6543. |
| `FRONTEND_ORIGINS` | Nada en Vercel | Solo CORS en desarrollo local. En Vercel puedes omitirla o poner `https://<proyecto>.vercel.app`. |
| `GEMINI_API_KEY` | **Clasificación con IA** | Google AI Studio → *Get API key*. Sin ella: clasificación por reglas (palabras clave), marcada como "provisional". |
| `GEMINI_MODEL` | Opcional | Por defecto `gemini-3.8-flash`. |
| `GEMINI_TIMEOUT_S` | Opcional | Por defecto `20`. Si la IA tarda más, se usa la clasificación por reglas y el reporte no se pierde. |
| `GEMINI_FALLBACK_MODELS` | Opcional | Lista separada por comas; por defecto `gemini-3.5-flash-lite,gemini-3.5-flash,gemini-3.7-flash`. Se prueban en orden si el principal falla por timeout, `503` por demanda o `429`. **El nivel gratuito limita a 20 peticiones por día y por modelo**, así que cada reserva añade 20 clasificaciones más antes de caer a las reglas. Vacío para desactivarlas. |
| `GEMINI_THINKING_BUDGET` | Opcional | Presupuesto de razonamiento del modelo principal. Por defecto `0` (sin razonamiento: `gemini-3.8-flash` clasifica en ~5 s; con razonamiento libre supera los 20 s). `auto` deja que lo decida el modelo. |
| `SMTP_HOST` | Opcional | `smtp.resend.com` en producción; por defecto `smtp.gmail.com`. |
| `SMTP_PORT` | Opcional | Por defecto `587` (STARTTLS). |
| `SMTP_USER` | **Correo real** (junto con `SMTP_PASSWORD`) | `resend` con Resend; la cuenta Gmail del equipo si se usa Gmail en local. |
| `SMTP_PASSWORD` | **Correo real** | La **API key** de Resend (`re_…`). Con Gmail: contraseña de aplicación (requiere verificación en dos pasos), nunca la contraseña normal. |
| `MAIL_FROM` | Opcional | Remitente; si falta, se usa `SMTP_USER`. |
| `MAIL_DEMO_OVERRIDE_TO` | **Recomendada durante el reto** | Si está definida, **todo** correo va a ese buzón y el asunto indica el destinatario real. Evita escribirle a una entidad de verdad por error. |
| `MAIL_TIMEOUT_S` | Opcional (no está en `.env.example`) | Por defecto `15` s por correo. |
| `SUPABASE_URL` | **Fotos** (junto con la clave) | Project URL de Supabase. |
| `SUPABASE_SERVICE_ROLE_KEY` | **Fotos** | Clave `service_role`. **Solo servidor; nunca al navegador.** Sin las dos variables, `POST /api/v1/uploads/sign` responde `503` y los reportes van sin foto. |
| `SUPABASE_BUCKET` | Opcional | Por defecto `evidencias`. |
| `MAX_PHOTO_BYTES` | Opcional (no está en `.env.example`) | Por defecto 5 MB. |
| `META_VERIFY_TOKEN` | **Registrar el webhook de WhatsApp** | Cadena larga que inventas tú; se escribe igual en Meta (sección 5). Sin ella, Meta no puede verificar el webhook (`403`). |
| `META_ACCESS_TOKEN` | **WhatsApp real** (descargar fotos y responder al vecino) | Token permanente de *System User* en Meta Business. |
| `META_PHONE_NUMBER_ID` | **WhatsApp real** | ID del número de teléfono en la app de Meta (no el número en sí). |
| `META_GRAPH_VERSION` | Opcional | Por defecto `v22.0`. |
| `SLA_DIAS` | Opcional | Plazo en días para marcar una participación como vencida. Por defecto `5`. |
| `PUBLIC_BASE_URL` | Opcional (no está en `.env.example`) | Reservada; hoy el código no la usa. Puedes poner `https://<proyecto>.vercel.app`. |

Comprobación rápida tras desplegar: abre `https://<proyecto>.vercel.app/api/v1/health`. Verás
qué integraciones están en modo real y cuáles en contingencia:

```json
{ "status": "ok", "database": "postgres", "ia": "gemini:gemini-3.8-flash", "email": "smtp",
  "storage": "supabase", "whatsapp": "meta", "sla_dias": 5 }
```

La documentación interactiva queda en `https://<proyecto>.vercel.app/api/v1/docs`... **no**: FastAPI
sirve Swagger en `/docs` respecto de la raíz de la app, es decir `https://<proyecto>.vercel.app/docs`
sería capturado por el frontend. Para verla en Vercel usa el JSON del esquema en
`https://<proyecto>.vercel.app/api/v1/openapi.json`? Tampoco: FastAPI lo publica en `/openapi.json`.
**En Vercel, Swagger solo es accesible si se enruta `/docs` y `/openapi.json` al backend** (se puede
añadir en `vercel.json` dos rewrites antes del comodín) o si el backend cambia `docs_url` a
`/api/v1/docs`. Hoy no está enrutado a propósito: en la demo se usa el frontend, y Swagger se
consulta en local (`http://localhost:8000/docs`). Si quieren Swagger público, es un cambio de dos
líneas en `vercel.json` (avisar a Cornelio).

---

## 4. Cómo llega el frontend al backend (mismo dominio)

`frontend/src/services/api.ts` construye la URL base así:

```ts
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api/v1"
```

- En **local** funciona sin configurar nada: Vite en `:5173` llama a Uvicorn en `:8000` y el
  backend permite ese origen por CORS (`FRONTEND_ORIGINS`).
- En **Vercel** la variable `VITE_API_BASE_URL=/api/v1` (sección 3.1) hace que las llamadas sean
  relativas (`/api/v1/reports`), y el rewrite `/api/(.*)` las manda al servicio `backend`.

**Cambio pendiente para Jesus (frontend), sin urgencia pero conviene hacerlo:** el valor por
defecto (`http://localhost:8000/api/v1`) es un riesgo si algún día se despliega sin la variable:
la página cargaría pero llamaría a `localhost` del visitante. Opciones, de menos a más cambio:

1. Añadir `frontend/.env.production` con `VITE_API_BASE_URL=/api/v1` (Vite lo aplica en
   `npm run build`; en local `npm run dev` sigue usando `localhost:8000`). Es la opción más simple
   y se versiona sin riesgo porque no contiene secretos.
2. Cambiar el *fallback* del código a `"/api/v1"` y dejar `frontend/.env.development` con
   `VITE_API_BASE_URL=http://localhost:8000/api/v1`.
3. (Opcional) Configurar `server.proxy` en `vite.config.ts` para que `/api` apunte a `:8000`; así
   el frontend usa `/api/v1` también en local y desaparece CORS por completo.

Mientras tanto, con la variable cargada en Vercel todo funciona.

---

## 5. Webhook de WhatsApp (Meta Cloud API)

URL fija del webhook (producción):

```text
https://<proyecto>.vercel.app/api/v1/webhooks/whatsapp
```

1. En <https://developers.facebook.com> → tu app → **WhatsApp → Configuration**.
2. **Callback URL**: la URL de arriba. **Verify token**: el mismo valor que cargaste en
   `META_VERIFY_TOKEN` en Vercel (tiene que estar desplegado antes de pulsar *Verify and save*).
   Meta hace `GET ...?hub.mode=subscribe&hub.verify_token=...&hub.challenge=...` y el backend
   responde el `challenge` en texto plano si el token coincide.
3. **Webhook fields** → suscribirse a **`messages`**.
4. **API Setup**: copia el **Phone number ID** → `META_PHONE_NUMBER_ID`. Para el token, crea un
   **System User** en Meta Business Suite con permiso `whatsapp_business_messaging` y genera un
   **token permanente** → `META_ACCESS_TOKEN` (el token temporal de la consola caduca en 24 h).
5. En modo de pruebas de Meta solo reciben mensajes los números registrados como *test numbers*;
   añade los celulares del equipo y del jurado si aplica.
6. Prueba: envía un texto, una ubicación o una foto al número de prueba. El backend crea el
   expediente (`source = "whatsapp"`) y responde con el folio. El `POST` del webhook **siempre
   devuelve 200** aunque algo falle internamente, para que Meta no reintente en bucle; los
   errores quedan en los *logs* de la función (Vercel → proyecto → **Logs**).

Sin `META_ACCESS_TOKEN`/`META_PHONE_NUMBER_ID` el webhook igual acepta mensajes (útil con `curl`),
pero no descarga imágenes ni responde al vecino.

---

## 6. Probar en local con la CLI de Vercel

Requisitos: Node 20+, Vercel CLI **≥ 48.1.8** (la mínima para FastAPI con `vercel dev`):

```bash
npm i -g vercel
vercel --version
```

### 6.1 Vincular la carpeta con el proyecto (una sola vez)

Desde la raíz del repo:

```bash
vercel link        # elige el equipo/cuenta y el proyecto ya creado en la sección 2
```

Crea `.vercel/` (ya ignorado por Git; no lo subas).

### 6.2 Bajar las variables de entorno al backend

```bash
vercel env pull backend/.env                      # variables del entorno Development
vercel env pull backend/.env --environment=preview  # o las de Preview/Production si quieres probar con datos reales
```

El backend lee `backend/.env` con `python-dotenv`, así que Uvicorn y `vercel dev` las verán. Este
archivo está en `.gitignore`: **no se sube**. Si solo cargaste variables en Production/Preview,
usa `--environment=production` (ten cuidado: trabajarás contra la base de datos real).

### 6.3 Levantar los dos servicios juntos

Antes prepara el entorno de Python del backend (Vercel CLI ejecuta la app con el Python del
entorno activo):

```bash
cd backend && python3.13 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt && cd ..
```

Luego, desde la raíz:

```bash
vercel dev          # usa la configuración del proyecto vinculado
vercel dev -L       # --local: sin autenticarse ni consultar la nube (útil sin internet)
```

`vercel dev` lee `vercel.json`, levanta Vite y FastAPI y aplica los mismos `rewrites` que en
producción, así que puedes probar `http://localhost:3000/` y `http://localhost:3000/api/v1/health`
con el mismo dominio. Si `vercel dev` da problemas con Python, la alternativa de siempre es correr
Vite (`npm run dev` en `frontend/`) y Uvicorn (`uvicorn app.main:app --reload --port 8000` en
`backend/`) por separado, como describe `backend/README.md`.

### 6.4 Desplegar a mano (opcional)

Normalmente basta con hacer *push* a GitHub. Si necesitas un despliegue manual:

```bash
vercel            # preview
vercel --prod     # producción
```

---

## 7. Si falla el build o el arranque

Revisa en Vercel → **Deployments** → el despliegue → **Build Logs** / **Functions Logs**. Casos
típicos:

| Síntoma | Causa probable | Qué revisar |
|---|---|---|
| El build solo construye el frontend; `/api/v1/health` da 404 o devuelve HTML | El proyecto no se construyó en modo Services | *Settings → Build and Deployment → Framework Preset* debe ser **Services** y *Root Directory* vacío. Confirma que `vercel.json` está en la raíz del repo y en la rama desplegada. |
| `Error: No Python entrypoint found` o similar | Vercel no encontró `app` | `entrypoint` es `app.main:app` (módulo `backend/app/main.py`, variable `app`). Comprueba que `backend/app/__init__.py` existe y que el `root` del servicio es `backend/`. |
| Usa Python 3.12 y falla alguna dependencia | No leyó `.python-version` | El archivo debe estar en `backend/` (raíz del servicio) con el contenido `3.13`. |
| `Bundle size exceeds 500 MB` | Dependencias o archivos de más | `requirements.txt` solo debe listar lo necesario en producción. `excludeFiles` ya excluye `tests/`, `.venv/`, `data/*.db`, `scripts/` y `__pycache__/`. Verifica que `.venv` no esté versionado. |
| `Function invocation timed out` | Gemini + varios correos superan 60 s | Sube `maxDuration` en `vercel.json` (máximo 300 en Hobby) o baja `GEMINI_TIMEOUT_S` / `MAIL_TIMEOUT_S`. |
| Error al arrancar la función: `OSError: Read-only file system` o `unable to open database file` | Falta `DATABASE_URL` y el backend intentó crear SQLite | Carga `DATABASE_URL` (sección 1.2) y redespliega. |
| `password authentication failed` / `Tenant or user not found` | Cadena del pooler mal armada | Usuario `postgres.<ref>` (con el punto), puerto **6543**, contraseña codificada en URL. |
| `prepared statement ... already exists` | Se usó el pooler en modo sesión o conexión directa con el mismo código | Usa la cadena de **Transaction pooler**; el backend ya desactiva *prepared statements*. |
| El frontend carga pero las llamadas van a `localhost:8000` | Falta `VITE_API_BASE_URL` en el build | Añádela (`/api/v1`) en Production y Preview y **redespliega** (Vite la incrusta al construir). |
| `POST /api/v1/uploads/sign` responde 503 | Faltan `SUPABASE_URL`/`SUPABASE_SERVICE_ROLE_KEY` o el bucket no existe | Sección 1.3 y 1.4. |
| Meta dice "The callback URL or verify token couldn't be validated" | Token distinto o despliegue no listo | `META_VERIFY_TOKEN` idéntico en Vercel y en Meta; espera a que el despliegue de producción termine. |
| El build del frontend falla por TypeScript | `npm run build` ejecuta `tsc -b` antes de `vite build` | Corrige los errores de tipos en local (`cd frontend && npm run build`). |

Herramienta útil: en la página del despliegue, la pestaña **Source**/**Output** muestra qué
archivos entraron en cada servicio; sirve para confirmar que `excludeFiles` y `.vercelignore`
hicieron efecto.

---

## 8. Riesgos y decisiones a tener presentes

- **Services está en beta.** La clave `services` y los `rewrites` con `destination: { service }`
  están en la documentación y en el esquema oficial de `vercel.json`, pero al ser beta el
  comportamiento puede cambiar. Si Vercel llegara a exigir Pro, el plan B es dos proyectos
  (frontend y backend) con `FRONTEND_ORIGINS` para CORS y `VITE_API_BASE_URL` apuntando al dominio
  del backend; el código ya lo soporta sin cambios.
- **`.vercelignore`** está documentado para lo que se *sube* a Vercel; en despliegues desde Git el
  origen es el clon del repositorio. Por eso las exclusiones importantes están **también** en
  `.gitignore` (nunca se suben) y en `excludeFiles` (no entran al bundle de la función).
- **Arranque en frío**: cada arranque ejecuta `create_all` y siembra el catálogo (idempotente).
  Con Postgres son milisegundos; no requiere acción.
- **Correo en la demo**: mantén `MAIL_DEMO_OVERRIDE_TO` mientras los correos de las entidades en
  `catalog.json` sean de demostración; así nadie escribe a una entidad real por accidente.
- **Sin autenticación en `/api/v1/admin/*`** (decisión del equipo para el prototipo). En una URL
  pública cualquiera podría modificar expedientes: no compartas la URL fuera del jurado y del
  equipo, y considera Deployment Protection de Vercel (en Hobby protege *previews* con cuenta de
  Vercel) si hace falta.
- **Bucket público**: las fotos son visibles por URL. No se suben datos personales; el contacto
  del vecino (`reporter_contact`) nunca se manda a Storage ni a la IA.
