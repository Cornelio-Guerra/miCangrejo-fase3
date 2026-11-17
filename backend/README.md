# API de miCangrejo

Backend del expediente vecinal (Visión v1.1): **FastAPI + SQLModel** en un solo proceso. Los
routers atienden HTTP, los servicios concentran la lógica y la base de datos guarda el expediente
con **un estado por cada entidad competente**, cada derivación con fecha y el historial completo.

```text
React + Leaflet/OSM ──/api/v1──► FastAPI (routers → services) ──► Postgres (Supabase) | SQLite local
WhatsApp (Meta) ──webhook──►         │         │         │
                              Gemini │   SMTP (Resend) Supabase Storage (fotos)
```

Todas las rutas cuelgan de `/api/v1`. La documentación interactiva (Swagger) está en
<http://localhost:8000/docs> al ejecutar en local.

## Ejecutar en local

Requiere **Python 3.13** (`.python-version` lo fija; Vercel usa el mismo archivo).

```bash
cd backend
python3.13 -m venv .venv
source .venv/bin/activate          # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp .env.example .env               # Windows: Copy-Item .env.example .env
uvicorn app.main:app --reload --port 8000
```

Alternativa con [uv](https://docs.astral.sh/uv/) (no hace falta crear el entorno a mano):

```bash
cd backend
cp .env.example .env
uv run --python 3.13 --with-requirements requirements.txt uvicorn app.main:app --reload --port 8000
```

Comprueba que arrancó y en qué modo está cada integración:

```bash
curl http://localhost:8000/api/v1/health
```

## Modo de contingencia (sin credenciales)

**Todas las variables de `.env.example` son opcionales.** Sin ellas el backend arranca igual y cada
pieza pasa a un modo de respaldo, para que la demo nunca se detenga (RNF1):

| Integración | Variables que la activan | Sin ellas |
|---|---|---|
| Base de datos | `DATABASE_URL` (pooler de Supabase en modo transacción, puerto 6543) | **SQLite** en `backend/data/micangrejo.db` (se crea solo; no se versiona) |
| Clasificación | `GEMINI_API_KEY` (+ `GEMINI_MODEL`, `GEMINI_TIMEOUT_S`) | **Reglas por palabras clave** de `app/data/catalog.json`; el resultado queda como `provisional` |
| Correo a entidades | `SMTP_USER` + `SMTP_PASSWORD` (+ `SMTP_HOST`, `SMTP_PORT`, `MAIL_FROM`, `MAIL_DEMO_OVERRIDE_TO`) | **Correo simulado**: no sale nada, pero el texto completo queda en el historial del expediente y la participación pasa a `Recibida` igual |
| Fotos | `SUPABASE_URL` + `SUPABASE_SERVICE_ROLE_KEY` (+ `SUPABASE_BUCKET`) | `POST /uploads/sign` responde `503` y **los reportes van sin foto** |
| WhatsApp | `META_ACCESS_TOKEN` + `META_PHONE_NUMBER_ID` (+ `META_VERIFY_TOKEN` para registrar el webhook) | El webhook acepta mensajes (probable con `curl`) pero **no descarga imágenes ni responde** al vecino |

`GET /api/v1/health` informa el modo activo de cada una. Con las variables reales, cada pieza pasa
a modo real sin tocar código. En Vercel, `DATABASE_URL` es obligatoria en la práctica: el sistema
de archivos de la función es de solo lectura y SQLite no puede crearse ahí (ver
`docs/DESPLIEGUE.md`).

Otras variables: `SLA_DIAS` (plazo en días para marcar una participación como vencida, por defecto
5), `FRONTEND_ORIGINS` (orígenes permitidos por CORS en desarrollo; en Vercel el frontend comparte
dominio y no hace falta), `MAX_PHOTO_BYTES` (5 MB por defecto), `MAIL_TIMEOUT_S` (15 s).

## Endpoints

Base: `/api/v1`. Sin autenticación en el prototipo (decisión 8-c del equipo); `require_admin` en
`routers/admin.py` es el punto único donde enchufar un token más adelante.

### Públicos

| Método | Ruta | Propósito |
|---|---|---|
| `GET` | `/health` | Estado del servicio y modo (real o contingencia) de base de datos, IA, correo, fotos y WhatsApp. |
| `POST` | `/uploads/sign` | Devuelve una URL firmada para subir la foto directo a Supabase Storage (ver flujo más abajo). `422` si el formato o tamaño no es válido; `503` si Storage no está configurado. |
| `POST` | `/reports` | Crea el reporte (JSON), lo clasifica de forma síncrona, propone las entidades competentes y agrupa duplicados (misma categoría, ≤ 150 m, ≤ 7 días). Responde `201` con el expediente completo y folio `MC-AAAA-NNNN`. |
| `GET` | `/reports` | Últimos reportes, paginados (`page`, `page_size` ≤ 100), vista resumida pública. |
| `GET` | `/reports/{folio}` | Estado del expediente, entidades actuales y desde cuándo, participaciones e historial. `404` si el folio no existe. |
| `GET` | `/waste-sites` | Puntos comunitarios (tinacos) para el mapa. |
| `GET` | `/waste-sites/geojson` | Los mismos puntos como `FeatureCollection` GeoJSON. |
| `GET` | `/waste-sites/{site_id}` | Un punto por id. `404` si no existe. |
| `GET` | `/webhooks/whatsapp` | Verificación del webhook de Meta (`hub.mode`, `hub.verify_token`, `hub.challenge`). `403` si el token no coincide con `META_VERIFY_TOKEN`. |
| `POST` | `/webhooks/whatsapp` | Recepción de mensajes de WhatsApp (texto, ubicación, imagen). Crea un expediente por mensaje y responde al vecino con el folio. Siempre devuelve `200` para que Meta no reintente. |

### Panel de la JDL (`/admin`)

| Método | Ruta | Propósito |
|---|---|---|
| `GET` | `/admin/reports` | Listado paginado con filtros `status`, `category`, `urgency`, `from`, `to`, `page`, `page_size` (mapa, filtros e indicadores). |
| `GET` | `/admin/reports/{case_id}` | Expediente completo por id numérico. |
| `PATCH` | `/admin/reports/{case_id}` | Corrige `category`, `urgency`, `summary`, `ticket_311`; con `validated: true` la JDL valida la clasificación. `422` si la categoría no está en el catálogo. |
| `POST` | `/admin/reports/{case_id}/classify` | Reintenta la clasificación (IA si está configurada; si no, reglas). |
| `POST` | `/admin/reports/{case_id}/entities` | Agrega una entidad competente (`entity_code`, `responsibility`). `201`; `404` si la entidad no existe; `409` si ya participa y no está cerrada. |
| `PATCH` | `/admin/reports/{case_id}/entities/{ceid}` | Cambia el estado de una participación (`status`, `note`). `409` si la transición no es válida o la participación ya está cerrada. |
| `POST` | `/admin/reports/{case_id}/entities/{ceid}/derive` | Deriva a otra entidad (`to_entity_code`, `responsibility`, `note`): la origen queda `Derivada` con fecha y la destino nace con fecha de recepción y correo enviado. `409` si la origen no está `Recibida`/`En atención` o es la misma entidad. |
| `POST` | `/admin/reports/{case_id}/send` | Envía el correo a las participaciones con correo pendiente o fallido (valida el expediente si aún no lo estaba). `503` solo si **ninguna** pudo enviarse; el expediente se conserva con envío pendiente. |
| `GET` | `/admin/stats` | Tablero de cumplimiento por entidad: casos abiertos, tiempo promedio de respuesta, derivados más de una vez, vencidos según `SLA_DIAS`, resueltos; totales por estado y categoría. |
| `GET` | `/admin/routing` | Tabla categoría → entidad → responsabilidad. |
| `PUT` | `/admin/routing` | Reemplaza la tabla completa. `422` si una entidad o categoría no existe. |
| `GET` | `/admin/entities` | Catálogo de entidades (código, nombre, correo, activa). |
| `PATCH` | `/admin/entities/{code}` | Edita nombre, correo o `is_active` de una entidad (útil para apuntar a buzones de demo). `404` si no existe. |
| `GET` | `/admin/categories` | Categorías del catálogo. |

Cuerpo mínimo de `POST /api/v1/reports`:

```json
{
  "description": "Contenedor desbordado junto a la acera principal desde hace dos días.",
  "location": { "label": "Vía Argentina con calle 51", "latitude": 8.990082, "longitude": -79.527106 },
  "photo_path": "casos/3f2a…-foto.jpg",
  "category": "Basura",
  "ticket_311": null
}
```

`description` va de 10 a 500 caracteres; `latitude`/`longitude`, `photo_path`, `category` (pista
opcional, la IA decide) y `ticket_311` son opcionales.

## Estados

### Del expediente (`status` en `cases`)

Se **calcula** a partir de las participaciones; nunca se edita a mano (decisión 10-a).

| Estado | Cuándo |
|---|---|
| `Recibido` | Reporte creado; aún sin validar ni enviar. |
| `En gestión` | La JDL validó la clasificación (`validated_at`) y todavía no se envió ningún correo. |
| `Enviado a entidades` | Al menos una participación tiene correo enviado (o simulado). |
| `Resuelto` | Todas las participaciones están cerradas (`Derivada` o `Resuelta`) y al menos una es `Resuelta`. También se usa para un reporte que se agrupó como duplicado de otro expediente. |

### De cada participación (`status` en `case_entities`)

Una fila por entidad competente dentro del expediente (RF15–RF17).

| Estado | Significado | Transiciones permitidas |
|---|---|---|
| `Asignada` | Propuesta por la clasificación o agregada por la JDL; aún sin enviar. | → `Recibida` (automática al enviarse el correo, o manual). |
| `Recibida` | El correo salió: la entidad tiene el caso (`received_at`). | → `En atención`, → `Resuelta`, o derivar. |
| `En atención` | La entidad está trabajando (`attention_at`). | → `Resuelta`, o derivar. |
| `Derivada` | Terminal para esta entidad: pasó el caso a otra (`derived_at`, `derived_to`). Solo por `POST …/derive`; la nueva participación nace y recibe correo. | Ninguna. |
| `Resuelta` | Terminal: la entidad cerró su parte (`resolved_at`). | Ninguna. |

Cualquier otra transición responde `409`. Cada cambio queda en `status_history` con actor
(`sistema`, `ia`, `jdl`), estado anterior, nuevo y nota. `days_in_entity` y `overdue` (según
`SLA_DIAS`) se calculan por participación.

## Flujo de la foto (URL firmada)

El backend **nunca recibe los bytes de la imagen**: Vercel limita el cuerpo de la petición a
4,5 MB y así el reporte se crea igual de rápido con o sin foto.

1. `POST /api/v1/uploads/sign` con `{ "filename": "foto.jpg", "content_type": "image/jpeg", "size": 1234567 }`
   (solo `image/jpeg`, `image/png`, `image/webp`; máximo `MAX_PHOTO_BYTES`, 5 MB). Respuesta:

   ```json
   {
     "path": "casos/3f2a…-foto.jpg",
     "upload_url": "https://xxxx.supabase.co/storage/v1/object/upload/sign/evidencias/casos/…?token=…",
     "method": "PUT",
     "headers": { "Content-Type": "image/jpeg", "x-upsert": "false" },
     "expires_in_s": 7200,
     "public_url": "https://xxxx.supabase.co/storage/v1/object/public/evidencias/casos/…"
   }
   ```

2. El navegador hace `PUT` a `upload_url` con el archivo como cuerpo y los `headers` devueltos
   (al menos `Content-Type`). La URL vale 2 horas.
3. `POST /api/v1/reports` con `photo_path` = el `path` recibido. El expediente guarda solo la
   ruta; `photo_url` en las respuestas se resuelve desde Storage (bucket `evidencias`) y la IA
   recibe la imagen para clasificar cuando Gemini está configurado.

Si Storage no está configurado, el paso 1 responde `503` y el frontend envía el reporte sin foto.

## Datos del mapa

El archivo `app/data/waste_sites.json` contiene 28 coordenadas extraídas del mapa comunitario compartido, cuya capa se identifica como **Tinacos**. Las etiquetas se normalizaron a `Punto de tinaco NN`; no se importaron descripciones, fotografías ni metadatos del mapa. Antes de producción, la JDL debe validar cada punto y actualizar el catálogo desde una fuente administrada por ella.

## Catálogo y datos

- `app/data/catalog.json`: entidades (AAUD, ATTT, JUEZ_PAZ, POLICIA, ALCALDIA, ENSA, IDAAN, MINSA
  con buzones de demo), categorías (`Basura`, `Estacionamiento`, `Ruido`, `Seguridad`, `Alumbrado
  o aceras`, `Otro`), tabla de enrutamiento inicial y palabras clave para la clasificación por
  reglas. Se siembra al arrancar solo si falta (nunca pisa correos editados desde el panel).
- Tablas: `entities`, `routing_rules`, `cases`, `case_entities`, `status_history` (`app/models.py`),
  creadas con `SQLModel.metadata.create_all` en el arranque.
- Privacidad: a la IA solo se envían el texto y la foto del reporte; `reporter_contact` (teléfono o
  correo del vecino) nunca sale del servidor salvo como copia en el correo a la entidad (RNF6).

## Estructura

```text
app/
├── main.py            # FastAPI, CORS, lifespan (crea tablas y siembra catálogo), routers en /api/v1
├── core/config.py     # Settings desde variables de entorno, con valores de contingencia
├── database.py        # Motor: Postgres (NullPool, sin prepared statements) o SQLite
├── models.py          # Tablas y enumeraciones de estado
├── schemas/           # Entradas y salidas (Pydantic)
├── routers/           # health, reports, uploads, admin, webhooks, waste_sites
├── services/          # servicio_expedientes, classifier, mailer, storage_service, whatsapp_service, catalog_service, waste_site_service
└── data/              # catalog.json, waste_sites.json
```

## Despliegue

En Vercel, el backend se publica como servicio `backend` del mismo proyecto que el frontend
(`vercel.json` en la raíz, entrypoint `app.main:app`, Python 3.13). La guía completa, con las
variables de entorno y el webhook de Meta, está en [`docs/DESPLIEGUE.md`](../docs/DESPLIEGUE.md).
