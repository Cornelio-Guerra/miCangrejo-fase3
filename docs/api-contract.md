# Contrato de API - miCangrejo

**v1.1 — alineado con el backend implementado**

> Sustituye al contrato provisional que se escribió para trabajar en paralelo. Todo lo que aparece aquí está tomado del código del backend (`backend/app/`) y los ejemplos de respuesta son **reales**: se capturaron con `curl` contra el backend levantado en modo de contingencia (SQLite, clasificación por reglas, correo simulado, sin Storage) el 12-09-2026. En modo real solo cambian los valores que dependen de las integraciones: `classification.source` pasa a `"gemini"` y `classification.status` a `"lista"`, `email_status` a `"enviado"`, y `photo_url` deja de ser `null`. Las formas de los objetos son las mismas.
>
> La referencia interactiva siempre disponible es `http://localhost:8000/docs` (Swagger generado por FastAPI).

---

## 1. Base URL y autenticación

| Entorno | Base URL |
| --- | --- |
| Local (uvicorn) | `http://localhost:8000/api/v1` |
| Vercel | El backend se sirve en el **mismo dominio** del frontend, así que la base es **`/api/v1`** (ruta relativa, sin host). |

- Todas las rutas de este documento van debajo de esa base. Por ejemplo, `POST /reports` es `POST http://localhost:8000/api/v1/reports` en local y `POST /api/v1/reports` en Vercel.
- **Sin autenticación en el prototipo** (decisión del equipo, 8-c). Los endpoints `/admin/*` están abiertos; `require_admin()` en `backend/app/routers/admin.py` es el único punto donde se enchufaría un token después.
- CORS: en local el backend acepta `http://localhost:5173` y `http://127.0.0.1:5173` (variable `FRONTEND_ORIGINS`). En Vercel no aplica porque es el mismo dominio.
- Todo el cuerpo de entrada y salida es JSON (`Content-Type: application/json`), salvo el `PUT` de la foto (va directo a Supabase Storage, ver §4.3) y la verificación del webhook (texto plano).
- Fechas: ISO 8601 en UTC con sufijo `Z` y microsegundos, p. ej. `"2026-09-12T04:07:06.488858Z"`.

---

## 2. Cambios respecto al contrato provisional

Lista explícita de lo que **difiere** de la versión anterior de este documento. Si algo del frontend se hizo contra el contrato viejo, es aquí donde hay que mirar.

1. **`POST /reports` ya NO es `multipart/form-data`: es JSON.** Los campos `location_label`, `latitude`, `longitude` se agrupan en un objeto `location: { label, latitude, longitude }`. El campo `photo` (archivo) desaparece y se sustituye por `photo_path` (string opcional).
2. **La foto se sube antes y por separado**: `POST /uploads/sign` devuelve una URL firmada; el navegador hace un `PUT` directo a esa `upload_url` con el archivo (headers que devuelve el backend, máximo 5 MB, solo JPG/PNG/WEBP) y luego envía el `path` recibido como `photo_path` en `POST /reports`. Si Storage no está configurado, `POST /uploads/sign` responde **503** y el frontend debe **enviar el reporte sin foto**. El backend nunca recibe los bytes de la imagen (límite de cuerpo de Vercel).
3. **`id` es numérico** (`1`, `2`, …), no `"report_123"`. Las rutas del panel (`/admin/reports/{id}`) usan ese id numérico; la consulta pública usa el folio (`/reports/{folio}`).
4. **`classification.responsible_entity` desaparece.** Ahora `classification.entities` es una **lista** de `{ code, name, responsibility }`: un caso puede involucrar a varias entidades. `classification` también trae `summary`, `status` (`pendiente | lista | provisional | fallida`), `source` (`gemini | reglas | null`) y `error`.
5. **El estado del expediente se calcula, no se edita.** `PATCH /admin/reports/{id}` ya no acepta `status` (si se manda, se ignora en silencio). El tercer estado se llama **`Enviado a entidades`** (plural), no `Enviado a entidad`.
6. **Hay estados por participación** (un nivel nuevo por debajo del expediente): cada entidad dentro del caso pasa por `Asignada → Recibida → En atención → Resuelta` o `Derivada`, y hay endpoints propios para moverlas (§3.2 y §4.4).
7. **La respuesta del reporte es mucho más rica**: además de `folio`, `status` y `classification`, trae `current_entities`, `participations`, `history` (con eventos, no solo estados), `reports_count`, `source`, `photo_url`, `ticket_311`, `validated_at`, `created_at`, `updated_at`.
8. **Agrupación de duplicados**: `POST /reports` puede devolver **un expediente ya existente** (otro folio, `reports_count` incrementado) si hay un caso de la misma categoría a menos de 150 m en los últimos 7 días. El folio que ve el vecino es el de la respuesta, no uno "nuevo".
9. **Paginación** con forma fija `{ items, total, page, page_size }`; `page_size` máximo 100 (más devuelve 422). Orden: más reciente primero.
10. **`PATCH /admin/reports/{id}`** acepta solo `category`, `urgency`, `summary`, `ticket_311` y `validated` (booleano: `true` = la JDL valida la clasificación y el expediente pasa a `En gestión`).
11. **Endpoints de admin nuevos**: `POST …/classify`, `POST …/entities`, `PATCH …/entities/{ceid}`, `POST …/entities/{ceid}/derive`, `GET /admin/stats`, `GET|PUT /admin/routing`, `GET /admin/entities`, `PATCH /admin/entities/{code}`, `GET /admin/categories`.
12. **Endpoints nuevos fuera de admin**: `GET /reports` (listado público paginado), `GET|POST /webhooks/whatsapp`, `GET /health` (indica el modo de cada integración).
13. **Catálogo de categorías**: no existe `Residuos`. Las válidas son `Basura`, `Estacionamiento`, `Ruido`, `Seguridad`, `Alumbrado o aceras`, `Otro`. Urgencias: `Baja`, `Media`, `Alta`.
14. **`POST /admin/reports/{id}/send`** devuelve `{ folio, status, results[] }`, uno por entidad. Responde **503** solo si *todos* los correos fallan; el reintento es volver a llamar (solo reenvía las participaciones `pendiente` o `fallido`). Enviar valida implícitamente el expediente si aún no estaba validado.
15. **Folio**: formato `MC-{año}-{id con 4 dígitos}` (`MC-2026-0001`). `GET /reports/{folio}` no distingue mayúsculas.

---

## 3. Estados

### 3.1 Estado del expediente (`status` del reporte) — calculado

El backend lo recalcula tras cada operación a partir de las participaciones (`recalcular_estado` en `servicio_expedientes.py`). **Nunca se edita a mano.** Cada cambio queda en `history` como evento `estado_expediente`.

| Estado | Cuándo | Qué lo provoca |
| --- | --- | --- |
| `Recibido` | Sin participaciones, o con participaciones pero sin validar ni enviar. | `POST /reports`, webhook de WhatsApp. |
| `En gestión` | La JDL validó (`validated_at` tiene valor) y aún no salió ningún correo. | `PATCH /admin/reports/{id}` con `{"validated": true}`. |
| `Enviado a entidades` | Al menos una participación tiene `email_status` `enviado` o `simulado`. | `POST /admin/reports/{id}/send`, `POST …/derive` (la nueva entidad recibe correo). |
| `Resuelto` | Todas las participaciones están en estado terminal (`Resuelta` o `Derivada`) y al menos una es `Resuelta`. También un reporte **agrupado** como duplicado se cierra como `Resuelto`. | `PATCH …/entities/{ceid}` con `{"status":"Resuelta"}` sobre la última participación activa. |

Flujo normal: `Recibido → En gestión → Enviado a entidades → Resuelto`. Si se llama a `send` sin validar antes, salta directo de `Recibido` a `Enviado a entidades` (la validación se registra como implícita).

### 3.2 Estado de cada participación (`participations[].status`)

Una participación = una entidad dentro de un expediente (`ceid` = `participations[].id`).

| Estado | Significado | Transición que lo produce |
| --- | --- | --- |
| `Asignada` | Propuesta por la clasificación (o añadida por la JDL); aún no se le envió nada. | `POST /reports` (IA/reglas), `POST …/entities`. |
| `Recibida` | El correo salió: la entidad tiene el caso. Fija `received_at` y `email_sent_at`. | `POST …/send` (automático), `POST …/derive` (la entidad destino nace así), o `PATCH …/entities/{ceid}` `{"status":"Recibida"}` desde `Asignada`. |
| `En atención` | La entidad está trabajando. Fija `attention_at`. | `PATCH …/entities/{ceid}` `{"status":"En atención"}` desde `Recibida`. |
| `Resuelta` | Terminal. Fija `resolved_at`. | `PATCH …/entities/{ceid}` `{"status":"Resuelta"}` desde `Recibida` o `En atención`. |
| `Derivada` | Terminal para esta entidad. Fija `derived_at` y `derived_to`; nace una participación nueva en la entidad destino. | **Solo** `POST …/entities/{ceid}/derive` desde `Recibida` o `En atención`. |

Transiciones manuales permitidas por `PATCH` (`ALLOWED_TRANSITIONS`):

```text
Asignada    → Recibida
Recibida    → En atención | Resuelta
En atención → Resuelta
```

**Devuelven 409:**

- `PATCH …/entities/{ceid}` con cualquier transición fuera de la tabla, incluido intentar `Derivada` por PATCH: `"Transición inválida: En atención → Asignada. Para derivar usa /derive"`.
- `PATCH …/entities/{ceid}` sobre una participación `Resuelta` o `Derivada`: `"La participación está Resuelta; no admite cambios"`.
- `POST …/derive` sobre una participación que no esté `Recibida` ni `En atención`: `"Solo se deriva una participación Recibida o En atención (actual: Asignada)"`.
- `POST …/derive` a la misma entidad de origen: `"No se puede derivar a la misma entidad"`.
- `POST …/entities` con una entidad que ya tiene participación activa en el expediente: `"AAUD ya participa en este expediente"`.

Campos calculados por participación: `days_in_entity` (días desde `received_at` hasta `resolved_at`/`derived_at`/ahora, 2 decimales, `null` si no se ha recibido) y `overdue` (`true` si está `Recibida` o `En atención` y lleva más de `SLA_DIAS` = 5 días).

### 3.3 Otros enumerados que llegan al frontend

| Campo | Valores |
| --- | --- |
| `classification.status` | `pendiente`, `lista` (Gemini), `provisional` (reglas), `fallida` |
| `classification.source` | `gemini`, `reglas`, `null` |
| `classification.urgency` / `urgency` | `Baja`, `Media`, `Alta` |
| `participations[].email_status` | `pendiente`, `enviado`, `simulado`, `fallido` |
| `source` | `web`, `whatsapp` |
| `history[].actor` | `sistema`, `ia`, `jdl`, `entidad` |
| `history[].event` | `creado`, `clasificado`, `duplicado`, `agrupado`, `corregido`, `validado`, `estado_expediente`, `correo`, `estado_participacion`, `participacion_agregada`, `derivado` |

---

## 4. Endpoints

30 operaciones registradas (cuenta comprobada con el esquema OpenAPI: `GET /api/v1/openapi.json`; la última
en entrar fue el webhook de Telegram). Todas bajo `/api/v1`.

### 4.1 Salud

#### `GET /health`

Sin parámetros. Indica el modo de cada integración; útil para que el frontend sepa si habrá fotos.

```json
{
  "status": "ok",
  "service": "micangrejo-api",
  "database": "sqlite (contingencia)",
  "ia": "reglas (contingencia)",
  "email": "simulado (contingencia)",
  "storage": "desactivado (fotos opcionales)",
  "whatsapp": "solo webhook local",
  "sla_dias": 5
}
```

En modo real los valores son `"postgres"`, `"gemini:gemini-3.8-flash"`, `"smtp"`, `"supabase"`, `"meta"`.

---

### 4.2 Reportes (vecino)

#### `POST /reports` — crear reporte

`201 Created`. Cuerpo JSON:

| Campo | Tipo | Obligatorio | Reglas |
| --- | --- | --- | --- |
| `description` | string | Sí | 10 a 500 caracteres (se recortan espacios). |
| `location.label` | string | Sí | 2 a 160 caracteres. Calle, edificio o referencia. |
| `location.latitude` | number \| null | No | -90 a 90. |
| `location.longitude` | number \| null | No | -180 a 180. |
| `photo_path` | string \| null | No | El `path` que devolvió `POST /uploads/sign` (máx. 300 caracteres). |
| `category` | string \| null | No | Pista opcional para el clasificador; la IA/reglas deciden. Una de las de `GET /admin/categories`. |
| `ticket_311` | string \| null | No | Referencia del 311 si el vecino ya la tiene (máx. 40). |

La clasificación ocurre **de forma síncrona dentro del POST** (Gemini con timeout de 20 s, o reglas por palabras clave si no hay clave/falla). El reporte **siempre se guarda**, aunque la clasificación falle (`classification.status = "fallida"`).

Ejemplo de petición:

```json
{
  "description": "Hay bolsas de basura acumuladas junto al tinaco de la esquina desde hace tres días y ya huele mal.",
  "location": {
    "label": "Calle 50 con Vía Argentina, frente al parque",
    "latitude": 8.9873,
    "longitude": -79.5241
  }
}
```

Respuesta real `201` (esta es la forma completa de **`ReportOut`**, la misma que devuelven `GET /reports/{folio}`, `GET /admin/reports/{id}` y todos los `PATCH`/`POST` del expediente):

```json
{
  "id": 1,
  "folio": "MC-2026-0001",
  "status": "Recibido",
  "description": "Hay bolsas de basura acumuladas junto al tinaco de la esquina desde hace tres días y ya huele mal.",
  "location": {
    "label": "Calle 50 con Vía Argentina, frente al parque",
    "latitude": 8.9873,
    "longitude": -79.5241
  },
  "photo_url": null,
  "ticket_311": null,
  "source": "web",
  "reports_count": 1,
  "classification": {
    "category": "Basura",
    "urgency": "Media",
    "summary": "Hay bolsas de basura acumuladas junto al tinaco de la esquina desde hace tres días y ya huele mal.",
    "status": "provisional",
    "source": "reglas",
    "error": "GEMINI_API_KEY no configurada (modo de contingencia)",
    "entities": [
      { "code": "AAUD", "name": "Autoridad de Aseo Urbano y Domiciliario (AAUD)", "responsibility": "Recolección y limpieza del punto" },
      { "code": "ALCALDIA", "name": "Alcaldía de Panamá", "responsibility": "Ornato y sanción por disposición indebida" }
    ]
  },
  "current_entities": [
    { "entity": { "code": "AAUD", "name": "Autoridad de Aseo Urbano y Domiciliario (AAUD)" }, "status": "Asignada", "since": "2026-09-12T04:07:06.007771Z" },
    { "entity": { "code": "ALCALDIA", "name": "Alcaldía de Panamá" }, "status": "Asignada", "since": "2026-09-12T04:07:06.008533Z" }
  ],
  "participations": [
    {
      "id": 1,
      "entity": { "code": "AAUD", "name": "Autoridad de Aseo Urbano y Domiciliario (AAUD)" },
      "responsibility": "Recolección y limpieza del punto",
      "status": "Asignada",
      "note": null,
      "received_at": null,
      "attention_at": null,
      "derived_at": null,
      "resolved_at": null,
      "derived_to": null,
      "email_status": "pendiente",
      "email_sent_at": null,
      "email_error": null,
      "days_in_entity": null,
      "overdue": false
    },
    {
      "id": 2,
      "entity": { "code": "ALCALDIA", "name": "Alcaldía de Panamá" },
      "responsibility": "Ornato y sanción por disposición indebida",
      "status": "Asignada",
      "note": null,
      "received_at": null,
      "attention_at": null,
      "derived_at": null,
      "resolved_at": null,
      "derived_to": null,
      "email_status": "pendiente",
      "email_sent_at": null,
      "email_error": null,
      "days_in_entity": null,
      "overdue": false
    }
  ],
  "history": [
    { "event": "creado", "previous": null, "new": "Recibido", "note": "Reporte recibido por web", "actor": "sistema", "entity": null, "created_at": "2026-09-12T04:07:06.000703Z" },
    { "event": "clasificado", "previous": "- / -", "new": "Basura / Media", "note": "clasificación inicial por reglas; entidades: AAUD, ALCALDIA; aviso: GEMINI_API_KEY no configurada (modo de contingencia)", "actor": "sistema", "entity": null, "created_at": "2026-09-12T04:07:06.008595Z" }
  ],
  "validated_at": null,
  "created_at": "2026-09-12T04:07:05.998853Z",
  "updated_at": "2026-09-12T04:07:06.008962Z"
}
```

Notas sobre `ReportOut`:

- `current_entities` = solo las participaciones **activas** (`Asignada`, `Recibida`, `En atención`) con `since` (= `received_at`, o `created_at` si aún no se envió). Es lo que se muestra al vecino como "quién tiene el caso ahora". Queda `[]` cuando el expediente está `Resuelto`.
- `participations` = todas, incluidas las terminales; es la vista del panel.
- `history[].entity` trae el código de la entidad cuando el evento es de una participación (`correo`, `estado_participacion`, `derivado`, `participacion_agregada`); `null` para eventos del expediente.
- En los eventos `correo`, `note` contiene el **texto completo del correo** (asunto y cuerpo, con `\n`). Es largo: conviene mostrarlo colapsado.
- `photo_url` es `null` si no hay foto o si Storage no está configurado.

**Agrupación de duplicados (RF4).** Si el nuevo reporte tiene coordenadas y categoría, y existe un expediente **no resuelto** de la **misma categoría a ≤ 150 m creado en los últimos 7 días**, el backend responde `201` pero con **el expediente existente** (`reports_count` incrementado y un evento `duplicado` en su historial). El reporte nuevo se guarda aparte como `Resuelto` con evento `agrupado` y sin participaciones. Ejemplo real: segundo reporte de basura a 30 m del anterior:

```jsonc
// POST /reports  {"description":"Basura tirada al lado del contenedor de la esquina, otra vez lleno.", "location":{"label":"Vía Argentina y Calle 50","latitude":8.9875,"longitude":-79.5243}}
// 201
{
  "id": 1,
  "folio": "MC-2026-0001",          // el folio del expediente original, no uno nuevo
  "status": "Recibido",
  "reports_count": 2,
  // …
  "history": [
    // …
    { "event": "duplicado", "previous": null, "new": null, "note": "Reporte adicional agrupado desde MC-2026-0002: Basura tirada al lado del contenedor de la esquina, otra vez lleno.", "actor": "sistema", "entity": null, "created_at": "2026-09-12T04:07:06.279174Z" }
  ]
}
```

El frontend debe mostrar al vecino el `folio` de la respuesta (y, si `reports_count > 1`, puede decir "este problema ya fue reportado por N vecinos").

Pista de categoría: `"category": "Ruido"` en el cuerpo suma peso a esa categoría en las reglas (y se pasa como sugerencia a Gemini). Ejemplo real: con la pista, una descripción neutra ("no dejan dormir a nadie los fines de semana") se clasificó como `Ruido` con entidades `JUEZ_PAZ` y `POLICIA`. Sin coincidencias, cae en `Otro` → `ALCALDIA`.

Errores:

| Código | Cuándo | `detail` real |
| --- | --- | --- |
| `422` | Descripción < 10 caracteres, `location` ausente, `label` < 2, coordenadas fuera de rango. | `[{"type":"string_too_short","loc":["body","description"],"msg":"String should have at least 10 characters","input":"corta","ctx":{"min_length":10}}]` |

#### `GET /reports` — listado público resumido

Query: `page` (≥ 1, por defecto 1), `page_size` (1–100, por defecto 20). Sin filtros. Incluye también los reportes agrupados (aparecen como `Resuelto` con `entities: []`).

Respuesta real `200` (forma **`PaginatedReports`** de `ReportSummaryOut`):

```json
{
  "items": [
    {
      "id": 2,
      "folio": "MC-2026-0002",
      "status": "Resuelto",
      "category": "Basura",
      "urgency": "Media",
      "summary": "Basura tirada al lado del contenedor de la esquina, otra vez lleno.",
      "description": "Basura tirada al lado del contenedor de la esquina, otra vez lleno.",
      "location": { "label": "Vía Argentina y Calle 50", "latitude": 8.9875, "longitude": -79.5243 },
      "photo_url": null,
      "classification_status": "provisional",
      "entities": [],
      "reports_count": 1,
      "created_at": "2026-09-12T04:07:06.276087Z"
    },
    {
      "id": 1,
      "folio": "MC-2026-0001",
      "status": "Recibido",
      "category": "Basura",
      "urgency": "Media",
      "summary": "Hay bolsas de basura acumuladas junto al tinaco de la esquina desde hace tres días y ya huele mal.",
      "description": "Hay bolsas de basura acumuladas junto al tinaco de la esquina desde hace tres días y ya huele mal.",
      "location": { "label": "Calle 50 con Vía Argentina, frente al parque", "latitude": 8.9873, "longitude": -79.5241 },
      "photo_url": null,
      "classification_status": "provisional",
      "entities": [
        { "entity": { "code": "AAUD", "name": "Autoridad de Aseo Urbano y Domiciliario (AAUD)" }, "status": "Asignada", "since": "2026-09-12T04:07:06.007771Z" },
        { "entity": { "code": "ALCALDIA", "name": "Alcaldía de Panamá" }, "status": "Asignada", "since": "2026-09-12T04:07:06.008533Z" }
      ],
      "reports_count": 2,
      "created_at": "2026-09-12T04:07:05.998853Z"
    }
  ],
  "total": 2,
  "page": 1,
  "page_size": 5
}
```

En el resumen, `entities` son las **activas** (misma forma que `current_entities` del detalle).

#### `GET /reports/{folio}` — consultar por folio

`folio` no distingue mayúsculas (`mc-2026-0001` funciona). Devuelve `ReportOut` completo. Ejemplo real **recortado** de un expediente ya enviado y derivado (AAUD → MINSA), que es lo que interesa mostrar al vecino: estado, entidad actual e historial.

```jsonc
// GET /reports/MC-2026-0001  → 200
{
  "id": 1,
  "folio": "MC-2026-0001",
  "status": "Enviado a entidades",
  "reports_count": 2,
  "classification": {
    "category": "Basura", "urgency": "Alta", "status": "provisional", "source": "reglas",
    "entities": [
      { "code": "AAUD", "name": "Autoridad de Aseo Urbano y Domiciliario (AAUD)", "responsibility": "Recolección y limpieza del punto" },
      { "code": "ALCALDIA", "name": "Alcaldía de Panamá", "responsibility": "Ornato y sanción por disposición indebida" },
      { "code": "MINSA", "name": "Ministerio de Salud (MINSA)", "responsibility": "Inspección sanitaria por foco de vectores" }
    ]
    // …
  },
  "current_entities": [
    { "entity": { "code": "ALCALDIA", "name": "Alcaldía de Panamá" }, "status": "Recibida", "since": "2026-09-12T04:07:06.489580Z" },
    { "entity": { "code": "MINSA", "name": "Ministerio de Salud (MINSA)" }, "status": "Recibida", "since": "2026-09-12T04:07:06.722710Z" }
  ],
  "participations": [
    {
      "id": 1, "entity": { "code": "AAUD", "name": "Autoridad de Aseo Urbano y Domiciliario (AAUD)" },
      "status": "Derivada", "note": "AAUD indica que el foco requiere control sanitario",
      "received_at": "2026-09-12T04:07:06.488858Z", "attention_at": "2026-09-12T04:07:06.547691Z",
      "derived_at": "2026-09-12T04:07:06.721787Z", "resolved_at": null,
      "derived_to": { "code": "MINSA", "name": "Ministerio de Salud (MINSA)" },
      "email_status": "simulado", "email_sent_at": "2026-09-12T04:07:06.488858Z", "email_error": null,
      "days_in_entity": 0.0, "overdue": false
    },
    { "id": 2, "entity": { "code": "ALCALDIA", "name": "Alcaldía de Panamá" }, "status": "Recibida", /* … */ },
    { "id": 3, "entity": { "code": "MINSA", "name": "Ministerio de Salud (MINSA)" }, "status": "Recibida", "received_at": "2026-09-12T04:07:06.722710Z", /* … */ }
  ],
  "history": [
    { "event": "creado",               "previous": null,        "new": "Recibido",             "note": "Reporte recibido por web",                          "actor": "sistema", "entity": null,   "created_at": "2026-09-12T04:07:06.000703Z" },
    { "event": "clasificado",          "previous": "- / -",     "new": "Basura / Media",       "note": "clasificación inicial por reglas; entidades: AAUD, ALCALDIA; aviso: …", "actor": "sistema", "entity": null, "created_at": "2026-09-12T04:07:06.008595Z" },
    { "event": "duplicado",            "previous": null,        "new": null,                   "note": "Reporte adicional agrupado desde MC-2026-0002: …",  "actor": "sistema", "entity": null,   "created_at": "2026-09-12T04:07:06.279174Z" },
    { "event": "corregido",            "previous": null,        "new": null,                   "note": "urgency=Alta",                                      "actor": "jdl",     "entity": null,   "created_at": "2026-09-12T04:07:06.401848Z" },
    { "event": "validado",             "previous": null,        "new": null,                   "note": "La JDL validó la clasificación",                    "actor": "jdl",     "entity": null,   "created_at": "2026-09-12T04:07:06.401892Z" },
    { "event": "estado_expediente",    "previous": "Recibido",  "new": "En gestión",           "note": null,                                                "actor": "sistema", "entity": null,   "created_at": "2026-09-12T04:07:06.402588Z" },
    { "event": "correo",               "previous": null,        "new": "simulado",             "note": "Correo simulado a aaud@demo.micangrejo.local (modo de contingencia)\n\n[miCangrejo] Caso MC-2026-0001 · Basura · urgencia Alta\n\nEstimados …", "actor": "sistema", "entity": "AAUD", "created_at": "2026-09-12T04:07:06.488911Z" },
    { "event": "correo",               "previous": null,        "new": "simulado",             "note": "Correo simulado a alcaldia@demo.micangrejo.local …", "actor": "sistema", "entity": "ALCALDIA", "created_at": "2026-09-12T04:07:06.489610Z" },
    { "event": "estado_expediente",    "previous": "En gestión","new": "Enviado a entidades",  "note": null,                                                "actor": "sistema", "entity": null,   "created_at": "2026-09-12T04:07:06.489842Z" },
    { "event": "estado_participacion", "previous": "Recibida",  "new": "En atención",          "note": "Cuadrilla programada para el jueves",               "actor": "jdl",     "entity": "AAUD", "created_at": "2026-09-12T04:07:06.547741Z" },
    { "event": "derivado",             "previous": "Recibida",  "new": "Derivada",             "note": "AAUD deriva a MINSA: AAUD indica que el foco requiere control sanitario", "actor": "jdl", "entity": "AAUD", "created_at": "2026-09-12T04:07:06.722399Z" },
    { "event": "correo",               "previous": null,        "new": "simulado",             "note": "Correo simulado a minsa@demo.micangrejo.local …",   "actor": "sistema", "entity": "MINSA", "created_at": "2026-09-12T04:07:06.722738Z" }
  ],
  "validated_at": "2026-09-12T04:07:06.401877Z",
  "created_at": "2026-09-12T04:07:05.998853Z",
  "updated_at": "2026-09-12T04:07:06.722975Z"
}
```

> Detalle observado: en el evento `derivado`, `previous` siempre dice `"Recibida"` aunque la participación estuviera `En atención` (está fijo en el código). Para la línea de tiempo usa `participations[].attention_at` / `derived_at`, no ese `previous`.

Errores:

| Código | `detail` real |
| --- | --- |
| `404` | `"No existe el folio MC-2026-9999"` |

---

### 4.3 Fotos

#### `POST /uploads/sign` — URL firmada para subir la foto

Cuerpo JSON:

| Campo | Tipo | Reglas |
| --- | --- | --- |
| `filename` | string | 1–200 caracteres; se sanea (solo se conserva `[a-zA-Z0-9_-]` del nombre). |
| `content_type` | string | Exactamente `image/jpeg`, `image/png` o `image/webp`. |
| `size` | int | Bytes (> 0). Máximo `MAX_PHOTO_BYTES` = 5 MB (5 242 880). |

Respuesta `200` con Storage configurado (forma de `SignUploadOut`; no reproducible en contingencia, tomada de `storage_service.create_signed_upload`):

```json
{
  "path": "casos/3f9a1c2e4b5d4e0f8a7b6c5d4e3f2a1b-foto.jpg",
  "upload_url": "https://xxxx.supabase.co/storage/v1/object/upload/sign/evidencias/casos/3f9a…-foto.jpg?token=…",
  "method": "PUT",
  "headers": { "Content-Type": "image/jpeg", "x-upsert": "false" },
  "expires_in_s": 7200,
  "public_url": "https://xxxx.supabase.co/storage/v1/object/public/evidencias/casos/3f9a…-foto.jpg"
}
```

Flujo: `POST /uploads/sign` → `PUT upload_url` (cuerpo = el archivo, con exactamente los `headers` devueltos) → `POST /reports` con `"photo_path": path`. La URL de subida vale 2 horas. `public_url` sirve para previsualizar antes de enviar.

Errores reales:

| Código | Cuándo | `detail` |
| --- | --- | --- |
| `503` | Storage no configurado (`SUPABASE_URL`/`SUPABASE_SERVICE_ROLE_KEY` ausentes) o Supabase no responde. **El frontend debe seguir y enviar sin foto.** | `"El almacenamiento de fotos no está configurado; envía el reporte sin foto"` |
| `422` | `content_type` fuera de la lista (lo valida Pydantic antes de mirar Storage) o `size` > 5 MB. | `[{"type":"string_pattern_mismatch","loc":["body","content_type"],"msg":"String should match pattern '^image/(jpeg|png|webp)$'", …}]` / `"La imagen supera el máximo de 5 MB"` |

---

### 4.4 Panel de la JDL: expedientes

Todas las rutas usan el **id numérico** del expediente (`case_id`) y, para participaciones, `ceid` = `participations[].id`. Todas las que modifican devuelven el **`ReportOut` completo actualizado** (salvo `send`), así el panel refresca la vista con la respuesta.

#### `GET /admin/reports` — listado paginado con filtros

Query (todos opcionales):

| Parámetro | Tipo | Notas |
| --- | --- | --- |
| `status` | string | Igualdad exacta con el estado del expediente (`Recibido`, `En gestión`, `Enviado a entidades`, `Resuelto`). |
| `category` | string | Igualdad exacta (`Basura`, …). |
| `urgency` | string | `Baja` / `Media` / `Alta`. |
| `from` | datetime | `created_at >= from`. Acepta `2026-09-12`, `2026-09-12T00:00:00` o `2026-09-12T00:00:00Z`. |
| `to` | datetime | `created_at <= to`. Mismo formato. |
| `page` | int ≥ 1 | Por defecto 1. |
| `page_size` | int 1–100 | Por defecto 20. |

Orden: `created_at` descendente. Respuesta: `PaginatedReports` (misma forma que `GET /reports`, §4.2).

```jsonc
// GET /admin/reports?status=Recibido&category=Basura&page=1&page_size=5 → 200
{
  "items": [
    {
      "id": 1, "folio": "MC-2026-0001", "status": "Recibido", "category": "Basura", "urgency": "Media",
      "summary": "Hay bolsas de basura acumuladas junto al tinaco de la esquina desde hace tres días y ya huele mal.",
      "description": "Hay bolsas de basura acumuladas junto al tinaco de la esquina desde hace tres días y ya huele mal.",
      "location": { "label": "Calle 50 con Vía Argentina, frente al parque", "latitude": 8.9873, "longitude": -79.5241 },
      "photo_url": null, "classification_status": "provisional",
      "entities": [
        { "entity": { "code": "AAUD", "name": "Autoridad de Aseo Urbano y Domiciliario (AAUD)" }, "status": "Asignada", "since": "2026-09-12T04:07:06.007771Z" },
        { "entity": { "code": "ALCALDIA", "name": "Alcaldía de Panamá" }, "status": "Asignada", "since": "2026-09-12T04:07:06.008533Z" }
      ],
      "reports_count": 2, "created_at": "2026-09-12T04:07:05.998853Z"
    }
  ],
  "total": 1, "page": 1, "page_size": 5
}
```

Errores: `422` si `page_size > 100` (`"Input should be less than or equal to 100"`) o si `from`/`to` no son fecha (`"Input should be a valid datetime or date, input is too short"`).

#### `GET /admin/reports/{id}` — detalle

Devuelve `ReportOut`. `404` → `"No existe el expediente 999"`.

#### `PATCH /admin/reports/{id}` — corregir clasificación / validar

Cuerpo JSON parcial (solo lo que se manda cambia):

| Campo | Tipo | Notas |
| --- | --- | --- |
| `category` | string | Debe estar en `GET /admin/categories`; si no, `422`. |
| `urgency` | `Baja` \| `Media` \| `Alta` | Otro valor → `422`. |
| `summary` | string ≤ 600 | Resumen que va en el correo. |
| `ticket_311` | string ≤ 40 | |
| `validated` | boolean | `true` fija `validated_at` (una sola vez) y el expediente pasa a `En gestión`. `false` no hace nada. |

**`status` y `responsible_entity` (contrato viejo) se ignoran en silencio** (responde 200 sin cambios). Cada corrección deja un evento `corregido` (actor `jdl`) y la validación un evento `validado`.

```jsonc
// PATCH /admin/reports/1  {"validated": true, "urgency": "Alta"} → 200
{
  "id": 1, "folio": "MC-2026-0001",
  "status": "En gestión",                       // Recibido → En gestión
  "classification": { "category": "Basura", "urgency": "Alta", /* … */ },
  "history": [
    // …
    { "event": "corregido",         "previous": null,       "new": null,         "note": "urgency=Alta",                   "actor": "jdl",     "entity": null, "created_at": "2026-09-12T04:07:06.401848Z" },
    { "event": "validado",          "previous": null,       "new": null,         "note": "La JDL validó la clasificación", "actor": "jdl",     "entity": null, "created_at": "2026-09-12T04:07:06.401892Z" },
    { "event": "estado_expediente", "previous": "Recibido", "new": "En gestión", "note": null,                             "actor": "sistema", "entity": null, "created_at": "2026-09-12T04:07:06.402588Z" }
  ],
  "validated_at": "2026-09-12T04:07:06.401877Z"
  // …
}
```

Errores reales:

| Código | `detail` |
| --- | --- |
| `404` | `"No existe el expediente 999"` |
| `422` | `"Categoría no válida. Usa: Basura, Estacionamiento, Ruido, Seguridad, Alumbrado o aceras, Otro"` |
| `422` | `[{"type":"enum","loc":["body","urgency"],"msg":"Input should be 'Baja', 'Media' or 'Alta'","input":"Urgentísima", …}]` |

#### `POST /admin/reports/{id}/classify` — reintentar la clasificación con IA

Sin cuerpo. Vuelve a ejecutar Gemini (o reglas) sobre descripción + foto. **Sobrescribe `category`, `urgency` y `summary`** (también si la JDL los había corregido) y **añade** las entidades que falten, sin quitar las existentes. Mantiene `validated_at`. Devuelve `ReportOut` con un evento `clasificado` nuevo:

```jsonc
// POST /admin/reports/1/classify → 200
{ /* … */ "history": [ /* … */,
  { "event": "clasificado", "previous": "Basura / Alta", "new": "Basura / Media", "note": "reclasificación por reglas; aviso: GEMINI_API_KEY no configurada (modo de contingencia)", "actor": "sistema", "entity": null, "created_at": "2026-09-12T04:07:07.867941Z" }
] }
```

Úsalo cuando `classification.status` sea `fallida` o `provisional` y ya haya clave de Gemini. `404` si el id no existe.

#### `POST /admin/reports/{id}/entities` — agregar una entidad competente

`201 Created`. Cuerpo:

```json
{ "entity_code": "IDAAN", "responsibility": "Revisar filtración de aguas junto al tinaco" }
```

`entity_code` (2–40, se normaliza a mayúsculas) debe existir en `GET /admin/entities`; `responsibility` 3–240 caracteres. La participación nace `Asignada` con `email_status: "pendiente"`; hay que llamar a `send` para que reciba el correo. Devuelve `ReportOut`:

```jsonc
// 201
{ /* … */
  "classification": { "entities": [ /* AAUD, ALCALDIA, MINSA, */ { "code": "IDAAN", "name": "IDAAN (agua y alcantarillado)", "responsibility": "Revisar filtración de aguas junto al tinaco" } ] },
  "participations": [ /* …, */ { "id": 4, "entity": { "code": "IDAAN", "name": "IDAAN (agua y alcantarillado)" }, "status": "Asignada", "email_status": "pendiente", /* … */ } ],
  "history": [ /* …, */ { "event": "participacion_agregada", "previous": null, "new": "Asignada", "note": "IDAAN: Revisar filtración de aguas junto al tinaco", "actor": "jdl", "entity": "IDAAN", "created_at": "2026-09-12T04:07:06.832037Z" } ]
}
```

| Código | `detail` |
| --- | --- |
| `404` | `"No existe el expediente 999"` / `"No existe la entidad NASA"` |
| `409` | `"AAUD ya participa en este expediente"` (ya tiene participación activa; si está `Derivada`/`Resuelta` sí se puede volver a añadir) |
| `422` | Validación de longitud de campos. |

#### `PATCH /admin/reports/{id}/entities/{ceid}` — cambiar el estado de una participación

Cuerpo (ambos opcionales):

```json
{ "status": "En atención", "note": "Cuadrilla programada para el jueves" }
```

`status` ∈ `Asignada | Recibida | En atención | Derivada | Resuelta` (pero solo las transiciones de §3.2 pasan; `Derivada` siempre da 409). `note` (≤ 600) se guarda en la participación y en el evento. Mandar solo `note` actualiza la nota sin tocar el estado. Devuelve `ReportOut`:

```jsonc
// PATCH /admin/reports/1/entities/1  {"status":"En atención","note":"Cuadrilla programada para el jueves"} → 200
{
  "status": "Enviado a entidades",
  "current_entities": [
    { "entity": { "code": "AAUD", "name": "Autoridad de Aseo Urbano y Domiciliario (AAUD)" }, "status": "En atención", "since": "2026-09-12T04:07:06.488858Z" },
    { "entity": { "code": "ALCALDIA", "name": "Alcaldía de Panamá" }, "status": "Recibida", "since": "2026-09-12T04:07:06.489580Z" }
  ],
  "participations": [
    { "id": 1, "entity": { "code": "AAUD", /* … */ }, "status": "En atención", "note": "Cuadrilla programada para el jueves",
      "received_at": "2026-09-12T04:07:06.488858Z", "attention_at": "2026-09-12T04:07:06.547691Z",
      "email_status": "simulado", "email_sent_at": "2026-09-12T04:07:06.488858Z", "days_in_entity": 0.0, "overdue": false /* … */ },
    // …
  ],
  "history": [ /* …, */
    { "event": "estado_participacion", "previous": "Recibida", "new": "En atención", "note": "Cuadrilla programada para el jueves", "actor": "jdl", "entity": "AAUD", "created_at": "2026-09-12T04:07:06.547741Z" }
  ]
  // …
}
```

Cuando se resuelve la última participación activa, el expediente pasa a `Resuelto` en la misma respuesta (evento `estado_expediente` `Enviado a entidades → Resuelto`).

| Código | `detail` real |
| --- | --- |
| `404` | `"La participación 999 no pertenece al expediente MC-2026-0001"` |
| `409` | `"Transición inválida: En atención → Asignada. Para derivar usa /derive"` |
| `409` | `"Transición inválida: Asignada → Resuelta. Para derivar usa /derive"` (hay que enviar primero) |
| `409` | `"La participación está Resuelta; no admite cambios"` |
| `422` | `status` fuera del enumerado. |

#### `POST /admin/reports/{id}/entities/{ceid}/derive` — derivar a otra entidad

Cuerpo:

```json
{
  "to_entity_code": "MINSA",
  "responsibility": "Inspección sanitaria por foco de vectores",
  "note": "AAUD indica que el foco requiere control sanitario"
}
```

Efecto atómico (RF16): la participación origen pasa a `Derivada` (con `derived_at`, `derived_to` y la `note`), nace una participación nueva en la entidad destino y **se le envía el correo en el acto**, así que nace `Recibida` con `received_at`. Devuelve `ReportOut`:

```jsonc
// POST /admin/reports/1/entities/1/derive → 200
{
  "status": "Enviado a entidades",
  "current_entities": [
    { "entity": { "code": "ALCALDIA", "name": "Alcaldía de Panamá" }, "status": "Recibida", "since": "2026-09-12T04:07:06.489580Z" },
    { "entity": { "code": "MINSA", "name": "Ministerio de Salud (MINSA)" }, "status": "Recibida", "since": "2026-09-12T04:07:06.722710Z" }
  ],
  "participations": [
    { "id": 1, "entity": { "code": "AAUD", /* … */ }, "status": "Derivada", "note": "AAUD indica que el foco requiere control sanitario",
      "derived_at": "2026-09-12T04:07:06.721787Z", "derived_to": { "code": "MINSA", "name": "Ministerio de Salud (MINSA)" }, /* … */ },
    { "id": 2, "entity": { "code": "ALCALDIA", /* … */ }, "status": "Recibida", /* … */ },
    { "id": 3, "entity": { "code": "MINSA", "name": "Ministerio de Salud (MINSA)" }, "responsibility": "Inspección sanitaria por foco de vectores",
      "status": "Recibida", "received_at": "2026-09-12T04:07:06.722710Z", "email_status": "simulado", "email_sent_at": "2026-09-12T04:07:06.722710Z", /* … */ }
  ],
  "history": [ /* …, */
    { "event": "derivado", "previous": "Recibida", "new": "Derivada", "note": "AAUD deriva a MINSA: AAUD indica que el foco requiere control sanitario", "actor": "jdl", "entity": "AAUD", "created_at": "2026-09-12T04:07:06.722399Z" },
    { "event": "correo",   "previous": null, "new": "simulado", "note": "Correo simulado a minsa@demo.micangrejo.local (modo de contingencia)\n\n…", "actor": "sistema", "entity": "MINSA", "created_at": "2026-09-12T04:07:06.722738Z" }
  ]
  // …
}
```

| Código | `detail` real |
| --- | --- |
| `404` | `"La participación 999 no pertenece al expediente MC-2026-0001"` / `"No existe la entidad NASA"` |
| `409` | `"Solo se deriva una participación Recibida o En atención (actual: Asignada)"` |
| `409` | `"Solo se deriva una participación Recibida o En atención (actual: Derivada)"` |
| `409` | `"No se puede derivar a la misma entidad"` |
| `422` | `to_entity_code` o `responsibility` fuera de longitud. |

#### `POST /admin/reports/{id}/send` — enviar el correo a las entidades

Sin cuerpo. Envía un correo a **cada participación con `email_status` `pendiente` o `fallido`** (las ya enviadas no se repiten). Si el expediente no estaba validado, lo valida implícitamente (evento `validado` con nota "Validación implícita al enviar"). Las participaciones que reciben correo pasan de `Asignada` a `Recibida`. El texto del correo queda en `history` (evento `correo`). Respuesta `200` (**`SendOut`**, no `ReportOut`):

```json
{
  "folio": "MC-2026-0001",
  "status": "Enviado a entidades",
  "results": [
    { "participation_id": 1, "entity": "AAUD", "email_status": "simulado", "error": null },
    { "participation_id": 2, "entity": "ALCALDIA", "email_status": "simulado", "error": null }
  ]
}
```

Volver a llamar sin nada pendiente es inofensivo: `{"folio":"MC-2026-0001","status":"Enviado a entidades","results":[]}`. Tras añadir una entidad con `POST …/entities`, un segundo `send` solo envía a esa (`"results":[{"participation_id":4,"entity":"IDAAN","email_status":"simulado","error":null}]`).

Con SMTP real, `email_status` es `"enviado"`; si `MAIL_DEMO_OVERRIDE_TO` está definido, todo correo va a ese buzón (nunca a una entidad real durante el reto).

Errores:

| Código | Cuándo | `detail` |
| --- | --- | --- |
| `404` | Id inexistente. | `"No existe el expediente 999"` |
| `503` | Había pendientes y **todos** fallaron (SMTP caído). El expediente se conserva; reintentar = volver a llamar. Forma (de `servicio_expedientes.enviar_a_entidades`, no reproducible en contingencia): | `{"message": "No se pudo enviar ningún correo; el expediente se conserva con envío pendiente", "results": [{"participation_id": 1, "entity": "AAUD", "email_status": "fallido", "error": "SMTPAuthenticationError: … (destino aaud@…)"}]}` |

Si solo falla una parte, responde `200` y el fallo se ve en `results[].email_status = "fallido"` con `error`.

---

### 4.5 Tablero

#### `GET /admin/stats` — cumplimiento por entidad

Sin parámetros. Respuesta real `200` (recortada a 3 entidades; siempre vienen las 8 del catálogo, en el orden del catálogo):

```json
{
  "sla_dias": 5,
  "total_cases": 4,
  "by_status": { "Resuelto": 2, "Recibido": 2 },
  "by_category": { "Basura": 2, "Estacionamiento": 1, "Otro": 1 },
  "entities": [
    { "entity": { "code": "AAUD", "name": "Autoridad de Aseo Urbano y Domiciliario (AAUD)" }, "open_cases": 0, "avg_response_days": null, "derived_more_than_once": 0, "overdue": 0, "resolved": 0 },
    { "entity": { "code": "ATTT", "name": "Autoridad del Tránsito y Transporte Terrestre (ATTT)" }, "open_cases": 1, "avg_response_days": null, "derived_more_than_once": 0, "overdue": 0, "resolved": 0 },
    { "entity": { "code": "MINSA", "name": "Ministerio de Salud (MINSA)" }, "open_cases": 0, "avg_response_days": 0.0, "derived_more_than_once": 0, "overdue": 0, "resolved": 1 }
  ]
}
```

| Campo | Significado |
| --- | --- |
| `by_status` / `by_category` | Conteo de expedientes (incluye los agrupados). Categoría `null` se agrupa como `"Sin categoría"`. Solo aparecen las claves con al menos un caso. |
| `open_cases` | Participaciones activas (`Asignada`, `Recibida`, `En atención`) de esa entidad. |
| `avg_response_days` | Promedio de días entre `received_at` y `resolved_at` de las participaciones resueltas; `null` si no hay ninguna. |
| `derived_more_than_once` | Expedientes en los que participa la entidad y que acumulan ≥ 2 derivaciones. |
| `overdue` | Participaciones `Recibida`/`En atención` con más de `sla_dias` días desde `received_at`. |
| `resolved` | Participaciones `Resuelta` de esa entidad. |

---

### 4.6 Enrutamiento categoría → entidad

#### `GET /admin/routing`

Lista ordenada por categoría y posición. Respuesta real (recortada):

```json
[
  { "category": "Alumbrado o aceras", "entity_code": "ALCALDIA", "responsibility": "Reparación de acera o luminaria municipal", "id": 7, "entity_name": "Alcaldía de Panamá", "entity_email": "alcaldia@demo.micangrejo.local" },
  { "category": "Basura", "entity_code": "AAUD", "responsibility": "Recolección y limpieza del punto", "id": 1, "entity_name": "Autoridad de Aseo Urbano y Domiciliario (AAUD)", "entity_email": "aaud@demo.micangrejo.local" },
  { "category": "Basura", "entity_code": "ALCALDIA", "responsibility": "Ornato y sanción por disposición indebida", "id": 2, "entity_name": "Alcaldía de Panamá", "entity_email": "alcaldia@demo.micangrejo.local" },
  { "category": "Estacionamiento", "entity_code": "ATTT", "responsibility": "Grúa, infracción y control vial", "id": 3, "entity_name": "Autoridad del Tránsito y Transporte Terrestre (ATTT)", "entity_email": "attt@demo.micangrejo.local" },
  { "category": "Otro", "entity_code": "ALCALDIA", "responsibility": "Canalizar a la entidad competente", "id": 8, "entity_name": "Alcaldía de Panamá", "entity_email": "alcaldia@demo.micangrejo.local" },
  { "category": "Ruido", "entity_code": "JUEZ_PAZ", "responsibility": "Proceso comunitario por ruido", "id": 4, "entity_name": "Juez de Paz de Bella Vista", "entity_email": "juezdepaz@demo.micangrejo.local" },
  { "category": "Ruido", "entity_code": "POLICIA", "responsibility": "Atención inmediata en horario nocturno", "id": 5, "entity_name": "Policía Nacional", "entity_email": "policia@demo.micangrejo.local" },
  { "category": "Seguridad", "entity_code": "POLICIA", "responsibility": "Patrullaje y atención del incidente", "id": 6, "entity_name": "Policía Nacional", "entity_email": "policia@demo.micangrejo.local" }
]
```

#### `PUT /admin/routing` — reemplazar la tabla completa

Cuerpo: **lista completa** de reglas (lo que no venga, desaparece). El orden de la lista define la posición.

```json
[
  { "category": "Basura", "entity_code": "AAUD", "responsibility": "Recolección y limpieza del punto" },
  { "category": "Basura", "entity_code": "ALCALDIA", "responsibility": "Ornato y sanción por disposición indebida" },
  { "category": "Otro", "entity_code": "ALCALDIA", "responsibility": "Canalizar a la entidad competente" }
]
```

Responde `200` con la misma forma que el `GET` (los `id` se regeneran). Se valida todo antes de tocar nada: si una regla falla, no se cambia ninguna.

| Código | `detail` real |
| --- | --- |
| `422` | `"No existe la entidad NASA"` |
| `422` | `"Categoría no válida: Residuos"` |

Nota: la tabla se usa por las **reglas** de contingencia y como guía en el prompt de Gemini. Si una categoría se queda sin reglas, se usan las de `Otro`.

---

### 4.7 Catálogo

#### `GET /admin/entities`

Ordenadas por `code`. Respuesta real:

```json
[
  { "code": "AAUD", "name": "Autoridad de Aseo Urbano y Domiciliario (AAUD)", "email": "aaud@demo.micangrejo.local", "is_active": true },
  { "code": "ALCALDIA", "name": "Alcaldía de Panamá", "email": "alcaldia@demo.micangrejo.local", "is_active": true },
  { "code": "ATTT", "name": "Autoridad del Tránsito y Transporte Terrestre (ATTT)", "email": "attt@demo.micangrejo.local", "is_active": true },
  { "code": "ENSA", "name": "ENSA (distribución eléctrica y alumbrado)", "email": "ensa@demo.micangrejo.local", "is_active": true },
  { "code": "IDAAN", "name": "IDAAN (agua y alcantarillado)", "email": "idaan@demo.micangrejo.local", "is_active": true },
  { "code": "JUEZ_PAZ", "name": "Juez de Paz de Bella Vista", "email": "juezdepaz@demo.micangrejo.local", "is_active": true },
  { "code": "MINSA", "name": "Ministerio de Salud (MINSA)", "email": "minsa@demo.micangrejo.local", "is_active": true },
  { "code": "POLICIA", "name": "Policía Nacional", "email": "policia@demo.micangrejo.local", "is_active": true }
]
```

Es la fuente del select "Derivar a…" y "Agregar entidad" del panel. (`is_active` existe pero hoy el backend no filtra por él.)

#### `PATCH /admin/entities/{code}` — editar nombre/correo (buzones de demo)

Cuerpo parcial: `name` (≤ 160), `email` (≤ 160, debe tener forma de correo), `is_active` (bool).

```jsonc
// PATCH /admin/entities/MINSA  {"email":"minsa.demo@gmail.com"} → 200
{ "code": "MINSA", "name": "Ministerio de Salud (MINSA)", "email": "minsa.demo@gmail.com", "is_active": true }
```

| Código | `detail` real |
| --- | --- |
| `404` | `"No existe la entidad NASA"` |
| `422` | `[{"type":"string_pattern_mismatch","loc":["body","email"],"msg":"String should match pattern '^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$'","input":"no-es-correo", …}]` |

#### `GET /admin/categories`

```json
["Basura", "Estacionamiento", "Ruido", "Seguridad", "Alumbrado o aceras", "Otro"]
```

Fuente del select de categoría en el panel y de la pista opcional en el formulario del vecino.

---

### 4.8 WhatsApp (Meta Cloud API)

No los llama el frontend; se documentan para que se entienda de dónde salen los reportes con
`source: "whatsapp"` y `source: "telegram"`.

#### `POST /webhooks/telegram` — mensajes del bot **(canal activo)**

Lo llama Telegram con cada mensaje del bot [@MiCangrejoBot](https://t.me/MiCangrejoBot). Exige la cabecera
`X-Telegram-Bot-Api-Secret-Token` con el valor de `TELEGRAM_WEBHOOK_SECRET`; si no coincide responde `403`.
El bot acepta `/start`, `/reporte`, `estado MC-AAAA-NNNN`, texto libre, foto y mensajes de ubicación; guarda
un borrador por chat hasta tener descripción y ubicación, y entonces crea el expediente y contesta con el
folio y la clasificación. Responde `200` siempre que el secreto sea válido, para que Telegram no reintente.
Detalles de configuración y registro del webhook en [`TELEGRAM.md`](TELEGRAM.md).

#### `GET /webhooks/whatsapp` — verificación de Meta

Query: `hub.mode=subscribe`, `hub.verify_token`, `hub.challenge`. Si el token coincide con `META_VERIFY_TOKEN`, responde **texto plano** con el `challenge`:

```text
GET /webhooks/whatsapp?hub.mode=subscribe&hub.verify_token=prueba&hub.challenge=1158201444
→ 200  Content-Type: text/plain
1158201444
```

`403` → `{"detail": "Token de verificación inválido"}` (también si `META_VERIFY_TOKEN` no está definido).

#### `POST /webhooks/whatsapp` — recepción de mensajes

Cuerpo: el payload estándar de Meta. Cada mensaje `text`, `image` (usa el `caption` como descripción y guarda la foto si hay Storage) o `location` se convierte en un expediente con `source: "whatsapp"`; el número del remitente se guarda como contacto interno (no se expone en la API ni se manda a la IA). **Siempre responde 200** (Meta reintenta si no), aunque el payload esté vacío o falle algo por dentro.

```jsonc
// POST /webhooks/whatsapp
{ "object": "whatsapp_business_account", "entry": [ { "id": "1", "changes": [ { "value": { "messaging_product": "whatsapp",
  "messages": [ { "from": "50760000000", "id": "wamid.X", "type": "text", "text": { "body": "Hay un carro mal parqueado bloqueando la acera en Calle Eusebio A. Morales" } } ] } } ] } ] }
// → 200
{ "received": true, "folios": ["MC-2026-0003"] }

// Mensaje de ubicación → 200  { "received": true, "folios": ["MC-2026-0004"] }
// Payload no reconocido {"hola":1} → 200  { "received": true, "folios": [] }
```

El expediente creado por texto queda con `location.label = "Ubicación pendiente (WhatsApp)"` y coordenadas `null`; el creado por ubicación usa `name`/`address` de Meta como `label` y las coordenadas reales. Sin `META_ACCESS_TOKEN`/`META_PHONE_NUMBER_ID` el backend no descarga imágenes ni responde al vecino con el folio, pero el webhook funciona igual.

---

### 4.9 Puntos comunitarios (tinacos)

Ya existían y no cambian. Datos estáticos de `backend/app/data/waste_sites.json` (28 puntos).

#### `GET /waste-sites`

```jsonc
{
  "source": "Mapa comunitario de tinacos compartido por la JDL",
  "total": 28,
  "sites": [
    { "id": "tinaco-01", "name": "Punto de tinaco 01", "kind": "tinaco", "latitude": 8.9872807, "longitude": -79.5286362 },
    { "id": "tinaco-02", "name": "Punto de tinaco 02", "kind": "tinaco", "latitude": 8.9871239, "longitude": -79.5295659 }
    // … hasta tinaco-28
  ]
}
```

#### `GET /waste-sites/geojson`

```jsonc
{
  "type": "FeatureCollection",
  "features": [
    { "type": "Feature", "id": "tinaco-01", "geometry": { "type": "Point", "coordinates": [-79.5286362, 8.9872807] }, "properties": { "name": "Punto de tinaco 01", "kind": "tinaco" } }
    // …
  ]
}
```

(GeoJSON: `coordinates` es `[longitud, latitud]`.)

#### `GET /waste-sites/{site_id}`

```json
{ "id": "tinaco-01", "name": "Punto de tinaco 01", "kind": "tinaco", "latitude": 8.9872807, "longitude": -79.5286362 }
```

`404` → `{"detail": "Punto no encontrado"}`.

---

## 5. Qué tiene que cambiar el frontend

Para Jesus. Concreto y en orden.

### 5.1 Configuración

- `frontend/src/services/api.ts` ya lee `import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api/v1"`. En Vercel la variable **`VITE_API_BASE_URL` debe valer `/api/v1`** (sin host): el backend vive en el mismo dominio. En local no hace falta definirla.
- Al arrancar el panel, opcionalmente `GET /health` para mostrar si hay fotos/IA/correo reales o simulados.

### 5.2 Formulario del vecino: reemplazar el mock de `reportService.ts`

`createMockReport` (localStorage) se sustituye por un `POST /reports` en JSON. La foto va antes por URL firmada. Un solo snippet cubre el flujo completo `POST sign → PUT file → POST reports`:

```ts
const API = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api/v1"

export type CreateReportPayload = {
  description: string                                   // 10–500 caracteres
  location: { label: string; latitude: number | null; longitude: number | null }
  category?: string                                     // pista opcional
}

/** Sube la foto a Storage y devuelve el photo_path. null = seguir sin foto. */
async function uploadPhoto(file: File): Promise<string | null> {
  const sign = await fetch(`${API}/uploads/sign`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ filename: file.name, content_type: file.type, size: file.size }),
  })
  if (sign.status === 503) return null                  // Storage no configurado: enviar sin foto
  if (!sign.ok) throw new ApiError("La foto no es válida (JPG, PNG o WEBP, máximo 5 MB).") // 422
  const { upload_url, headers, path } = await sign.json()
  const put = await fetch(upload_url, { method: "PUT", headers, body: file })   // directo a Supabase
  if (!put.ok) return null                              // no bloquear el reporte por la foto
  return path
}

export async function createReport(payload: CreateReportPayload, photo?: File): Promise<Report> {
  const photo_path = photo ? await uploadPhoto(photo) : null
  const res = await fetch(`${API}/reports`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ...payload, photo_path }),
  })
  if (res.status === 422) throw new ApiError("Revisa la descripción (10 a 500 caracteres) y la referencia del lugar.")
  if (!res.ok) throw new ApiError("No fue posible enviar el reporte. Inténtalo de nuevo.")
  return (await res.json()) as Report                   // 201: ReportOut
}
```

Detalles a tener en cuenta en la pantalla de confirmación:

- Mostrar `folio`, `status`, `classification.category`, `classification.urgency` y la lista `classification.entities` (varias).
- Si `reports_count > 1`, el reporte se agrupó con uno existente: decirlo ("Este problema ya fue reportado por N vecinos; tu folio es …").
- Validar en el cliente antes de firmar: `file.type` ∈ `image/jpeg|png|webp` y `file.size <= 5 * 1024 * 1024`; así se evita el 422.
- No hay que mandar `Content-Type: multipart/form-data` en ningún punto.

### 5.3 Consulta por folio (vecino)

`GET /reports/{folio}` → `ReportOut`. Mostrar:

- `status` del expediente (4 valores de §3.1) y `validated_at`.
- **`current_entities`**: quién tiene el caso ahora, con `status` de la participación y `since` (fecha desde la que lo tiene). Si está vacío y `status = "Resuelto"`, mostrar "Caso resuelto".
- **`history`** como línea de tiempo: `created_at`, `event`, `entity` (código) y `note`. Los eventos `correo` traen el correo completo en `note`; mostrarlo colapsado. Los eventos `estado_expediente` y `estado_participacion` traen `previous → new`.
- `404` → "No encontramos ese folio".

### 5.4 Panel de la JDL

| Pantalla / acción | Llamada | Notas |
| --- | --- | --- |
| Listado paginado + filtros + mapa | `GET /admin/reports?status=&category=&urgency=&from=&to=&page=&page_size=` | Respuesta `{items,total,page,page_size}`. `items[].entities` son las activas; `items[].location` para los pines. `page_size` ≤ 100. |
| Selects de filtro | `GET /admin/categories`; estados y urgencias fijos de §3 | |
| Detalle | `GET /admin/reports/{id}` | `ReportOut` completo. |
| Botón **Validar** | `PATCH /admin/reports/{id}` `{"validated": true}` | Puede ir junto con correcciones: `{"validated":true,"category":"Basura","urgency":"Alta","summary":"…"}`. Refrescar con la respuesta. |
| Corregir clasificación | `PATCH /admin/reports/{id}` `{category, urgency, summary, ticket_311}` | `422` si la categoría no está en el catálogo. No mandar `status`. |
| Botón **Reclasificar con IA** | `POST /admin/reports/{id}/classify` | Sobrescribe categoría/urgencia/resumen. |
| Botón **Enviar a entidades** | `POST /admin/reports/{id}/send` | Devuelve `SendOut`, **no** `ReportOut`: después volver a `GET /admin/reports/{id}`. Mostrar `results[]` por entidad. `503` = ningún correo salió, ofrecer "Reintentar" (misma llamada). |
| Cambiar estado de una participación | `PATCH /admin/reports/{id}/entities/{ceid}` `{"status": "…", "note": "…"}` | Ofrecer solo las transiciones válidas según `participations[].status` (§3.2): `Asignada`→[Recibida]; `Recibida`→[En atención, Resuelta]; `En atención`→[Resuelta]; terminales→nada. `409` = mostrar `detail` tal cual. |
| **Derivar a…** | `POST /admin/reports/{id}/entities/{ceid}/derive` `{"to_entity_code","responsibility","note"}` | Select de entidades desde `GET /admin/entities` excluyendo la de origen. Solo habilitar si la participación está `Recibida` o `En atención`. |
| Agregar entidad | `POST /admin/reports/{id}/entities` `{"entity_code","responsibility"}` | `201`. Luego `send` para que le llegue el correo. `409` si ya participa. |
| Tablero | `GET /admin/stats` | Tarjetas: `total_cases`, `by_status`, `by_category`; tabla por entidad con `open_cases`, `avg_response_days`, `overdue`, `derived_more_than_once`, `resolved`. `sla_dias` para la leyenda. |
| Enrutamiento | `GET /admin/routing` / `PUT /admin/routing` (lista completa) | Editor de tabla categoría → entidad → responsabilidad. |
| Buzones de demo | `GET /admin/entities` / `PATCH /admin/entities/{code}` `{email}` | Para apuntar cada entidad a un correo del equipo durante el reto. |

Indicadores visuales útiles ya calculados por el backend: `participations[].overdue` (rojo), `participations[].days_in_entity`, `classification.status = "provisional"` (badge "clasificado por reglas, revisar") y `classification.status = "fallida"` (badge + botón Reclasificar).

### 5.5 Tipos TypeScript (resumen de `ReportOut`)

```ts
type EntityRef = { code: string; name: string }
type CaseStatus = "Recibido" | "En gestión" | "Enviado a entidades" | "Resuelto"
type ParticipationStatus = "Asignada" | "Recibida" | "En atención" | "Derivada" | "Resuelta"

type Participation = {
  id: number; entity: EntityRef; responsibility: string; status: ParticipationStatus; note: string | null
  received_at: string | null; attention_at: string | null; derived_at: string | null; resolved_at: string | null
  derived_to: EntityRef | null
  email_status: "pendiente" | "enviado" | "simulado" | "fallido"; email_sent_at: string | null; email_error: string | null
  days_in_entity: number | null; overdue: boolean
}

type Report = {
  id: number; folio: string; status: CaseStatus; description: string
  location: { label: string; latitude: number | null; longitude: number | null }
  photo_url: string | null; ticket_311: string | null; source: "web" | "whatsapp"; reports_count: number
  classification: {
    category: string | null; urgency: "Baja" | "Media" | "Alta" | null; summary: string | null
    status: "pendiente" | "lista" | "provisional" | "fallida"; source: "gemini" | "reglas" | null; error: string | null
    entities: { code: string; name: string; responsibility: string }[]
  }
  current_entities: { entity: EntityRef; status: ParticipationStatus; since: string | null }[]
  participations: Participation[]
  history: { event: string; previous: string | null; new: string | null; note: string | null; actor: string; entity: string | null; created_at: string }[]
  validated_at: string | null; created_at: string; updated_at: string
}

type ReportSummary = Pick<Report, "id" | "folio" | "status" | "description" | "location" | "photo_url" | "reports_count" | "created_at"> & {
  category: string | null; urgency: string | null; summary: string | null; classification_status: string
  entities: Report["current_entities"]
}
type Paginated<T> = { items: T[]; total: number; page: number; page_size: number }
```

---

## 6. Códigos de respuesta

| Código | Uso en esta API |
| --- | --- |
| `200` | Consulta o actualización exitosa. También `POST …/classify`, `…/derive`, `…/send`, `PUT /admin/routing` y `POST /webhooks/whatsapp` (siempre). |
| `201` | `POST /reports` (incluso cuando devuelve un expediente existente por agrupación) y `POST /admin/reports/{id}/entities`. |
| `404` | Folio, expediente, participación (o participación de otro expediente), entidad o punto comunitario inexistente. `detail` es un string. |
| `409` | Conflicto de estado: transición de participación inválida, participación terminal, derivación desde un estado no permitido o a la misma entidad, entidad que ya participa. `detail` es un string listo para mostrar. |
| `422` | Datos inválidos. Dos formas de `detail`: **lista** de errores de Pydantic (`[{type, loc, msg, input, ctx}]`) cuando falla la validación del cuerpo/query, o **string** cuando lo rechaza la lógica (categoría fuera del catálogo, entidad inexistente en routing, foto > 5 MB). |
| `503` | Servicio externo no disponible: `POST /uploads/sign` sin Storage (enviar sin foto) y `POST …/send` cuando ningún correo pudo salir (el expediente se conserva; reintentar). En `send` el `detail` es un objeto `{message, results}`. |
| `403` | Solo `GET /webhooks/whatsapp` con token de verificación incorrecto. |

Forma general de un error: `{"detail": <string | lista | objeto>}`. Para la UI: si `detail` es string, mostrarlo tal cual; si es lista, mostrar `detail[0].msg` o mapear por `loc`.
