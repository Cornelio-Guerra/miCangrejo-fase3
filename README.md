# miCangrejo

**Plataforma vecinal de El Cangrejo: reportes, coordinación interinstitucional, emergencias y guía de Vía Argentina.**

**Equipo 2G** — Cornelio Guerra · Jesus Guerra
II Reto Emprende 2026 · *Construyendo soluciones digitales con API e IA* · CONTECS 2026 · FISC – Universidad Tecnológica de Panamá · 11 y 12 de septiembre de 2026

| | |
|---|---|
| **Patrocinador** | Junta de Desarrollo Local (JDL) de El Cangrejo |
| **Contraparte institucional** | Junta Comunal de Bella Vista |
| **Propósito** | Convertir cada reporte vecinal en un **expediente único** con folio, categoría, ubicación, urgencia y **un estado por cada entidad competente**, registrar cada derivación con fecha y medir dónde se detiene cada caso. |

> Basado en el *Documento de Visión miCangrejo v1.1* (11/09/2026). Las decisiones técnicas están en los issues [#3](../../issues/3) (modelo de expediente) y [#4](../../issues/4) (stack). Este README distingue lo **implementado** de lo **planificado**.

---

## Problema

Los residentes de El Cangrejo reportan los problemas del barrio (basureros desbordados, carros mal
estacionados, música excesiva de noche, alumbrado dañado…) con fotos y mensajes en el grupo de
WhatsApp de residentes. Esos reportes **no tienen ubicación precisa, categoría, responsable ni
estado**, y se pierden entre la conversación diaria:

- Un mismo problema se reporta varias veces sin identificarse como un solo caso.
- Cuando un caso involucra a varias entidades, **la responsabilidad pasa de una a otra sin que
  quede registro de dónde se detuvo**.
- El vecino no sabe si su reporte fue atendido y deja de reportar.
- La JDL no tiene registro estructurado, indicadores para priorizar ni evidencia consolidada para
  sustentar sus gestiones; las notas formales a la Alcaldía se redactan a mano.
- Las entidades responsables (AAUD, ATTT, Juez de Paz, Policía Nacional, Alcaldía de Panamá)
  reciben quejas desordenadas, duplicadas o sin evidencia.
- El plan piloto de preparación ante emergencias que la Junta Comunal de Bella Vista coordina con
  los PH se lleva por cadenas de correo y plantillas de Excel, sin registro centralizado por edificio.

## Idea retro (concepto base)

El **antiguo buzón de quejas del barrio**: el vecino deja su nota, alguien la revisa, la prioriza y
la eleva a la autoridad. miCangrejo conserva ese flujo y lo moderniza con un canal digital,
inteligencia artificial y trazabilidad completa, hasta convertirlo en una **plataforma de gestión y
coordinación interinstitucional basada en datos**.

## Solución digital

**miCangrejo** es una plataforma web con canal de WhatsApp y panel de administración que sustituye
el grupo de WhatsApp, las llamadas, las hojas de cálculo y las cadenas de correo por un canal único.
Está pensada para usarse desde el celular y permitir crear un reporte en menos de un minuto.

| Vista | Qué hace |
|---|---|
| **Residente** | Crea reportes con foto, descripción y ubicación, y consulta **en qué entidad está su caso y desde cuándo**. |
| **Administrador de la JDL** | Valida o corrige la clasificación, aprueba el envío a cada entidad, registra respuestas y derivaciones, consulta el tablero de cumplimiento y genera la nota formal. |
| **Administrador de PH** | Registra el censo de residentes y ocupantes, los brigadistas y las preguntas para la Junta Comunal. |
| **Visitante** | Consulta la guía de restaurantes de Vía Argentina en el mapa. |

**Fuera del alcance del prototipo** (evolución del producto): cobro a los negocios por fichas
destacadas, aplicaciones móviles nativas, integración directa con los sistemas de las entidades,
**acceso directo de las entidades a la plataforma** (en el prototipo la JDL registra la respuesta
de cada entidad), sistema completo de cuentas de usuario y programación y evaluación de simulacros.

**Alcance de la demo del reto:** el ciclo completo del reporte con expediente por entidad y
derivación. El módulo de censo por PH, la guía de restaurantes, la nota formal por IA y el
WhatsApp en vivo se presentan como mejoras futuras si no alcanza el tiempo.

## Funcionalidad principal

**El ciclo de vida de un reporte vecinal**, en el que intervienen las API:

1. **Captura:** el vecino envía descripción, ubicación y foto por el formulario web o por **Telegram**
   (bot [@MiCangrejoBot](https://t.me/MiCangrejoBot), activo). El canal de WhatsApp está integrado y queda
   pendiente de credenciales de Meta.
2. **Clasificación automática:** la **API de IA (Gemini)** asigna categoría, urgencia y las
   **entidades competentes** (una o varias, cada una con su responsabilidad) y genera un resumen.
   Los reportes del mismo problema y lugar se agrupan en un solo expediente.
3. **Validación:** el administrador de la JDL revisa y, si hace falta, corrige la clasificación.
4. **Envío:** al aprobar el expediente, el sistema envía un **correo a cada entidad** según la tabla
   de enrutamiento (categoría → entidades → correos), con copia al residente, y registra folio y
   fecha por entidad.
5. **Seguimiento por entidad:** cada participación tiene su estado (`Recibida → En atención →
   Derivada` o `Resuelta`). Si una entidad deriva el caso, no cierra su parte: queda `Derivada` con
   fecha, y la nueva entidad nace con fecha de recepción.
6. **Cierre** cuando todas las participaciones cierran, con evidencia.

Estados del expediente: `Recibido → En gestión → Enviado a entidades → Resuelto` (calculados a
partir de las participaciones).

## Coordinación interinstitucional (RF15–RF17)

- **Expediente único** por caso, con una **participación por cada entidad competente**.
- **Derivación registrada:** fecha de derivación en la entidad origen y fecha de recepción en la
  destino; la participación original queda `Derivada`, nunca se borra.
- **Tablero de cumplimiento por entidad:** casos abiertos, tiempo promedio de respuesta, casos
  derivados más de una vez y casos vencidos según un plazo configurable (`SLA_DIAS`).
- **Categorías iniciales del prototipo:** basura → AAUD · estacionamiento → ATTT · ruido → Juez de
  Paz · seguridad → Policía Nacional · alumbrado o aceras → Alcaldía de Panamá. ENSA, IDAAN y MINSA
  quedan como destinos adicionales.

## Posicionamiento frente al 311

miCangrejo **no sustituye** al Centro de Atención Ciudadana 311, que es la puerta de entrada nacional:
lo complementa como capa territorial de coordinación y evidencia. Cada expediente puede guardar el
**número de caso del 311** como referencia. El 311 no ofrece API pública, pero la AIG publica sus
casos como datos abiertos (licencia CC-BY) y en ellos se observa que un mismo caso cambia de
entidad asignada con frecuencia: miCangrejo convierte esa derivación en un dato medible.

## API

miCangrejo **crea** una API REST propia y **consume** servicios externos:

| API | Tipo | Papel en el sistema | Estado | Documentación |
|---|---|---|---|---|
| API REST de miCangrejo (FastAPI) | Propia | Reportes, expediente, entidades, enrutamiento, tablero, mapa comunitario | **Implementada** (30 operaciones) | `/api/v1/docs` (Swagger) al ejecutar el backend |
| Gemini Flash (Google AI Studio) | Privada, nivel gratuito | Clasifica el reporte (categoría, urgencia, entidades) y genera el resumen; con reglas de respaldo si falla | **Integrada** (activa con `GEMINI_API_KEY`) | <https://ai.google.dev/gemini-api/docs> |
| Telegram Bot API | Privada, gratuita | Recibe reportes por chat (descripción, ubicación y foto), responde con el folio y consulta el estado de un expediente | **Integrada y activa** — bot [@MiCangrejoBot](https://t.me/MiCangrejoBot) | <https://core.telegram.org/bots/api> |
| WhatsApp Cloud API (Meta) | Privada | Recibe reportes por WhatsApp mediante webhook y responde con el folio | **Integrada** (webhook listo; activa con credenciales de Meta) | <https://developers.facebook.com/docs/whatsapp/cloud-api> |
| SMTP — Resend (Gmail como alternativa en local) | Privada, nivel gratuito | Envía el caso a cada entidad; sin SMTP el envío se simula y queda en el historial | **Integrada** (activa con `SMTP_USER`/`SMTP_PASSWORD`; en producción Resend) | <https://resend.com/docs/send-with-smtp> |
| Supabase (Postgres + Storage) | Privada | Persistencia del expediente y de las fotos por URL firmada | **Integrada** (activa con `DATABASE_URL` y `SUPABASE_*`; sin ellas, SQLite y sin fotos) | <https://supabase.com/docs> |
| OpenStreetMap + Leaflet | Pública (datos abiertos) | Mapa de reportes y de puntos comunitarios | **Implementada** | <https://www.openstreetmap.org/copyright> · [uso de mosaicos](https://operations.osmfoundation.org/policies/tiles/) |
| Datos abiertos del 311 (AIG, CKAN) | Pública (datos abiertos, CC-BY) | Comparativo de derivaciones por entidad en el tablero | Opcional | <https://www.datosabiertos.gob.pa/dataset/aig-cac-311-informe-de-casos-enero-2024> |

### Endpoints

Base local: `http://localhost:8000/api/v1` · producción: `https://micangrejo.vercel.app/api/v1` (mismo dominio que el frontend). Documentación interactiva en `/docs`. El contrato completo con ejemplos reales está en [`docs/api-contract.md`](docs/api-contract.md).

**Públicos**

| Método | Ruta | Descripción | Respuestas |
|---|---|---|---|
| `GET` | `/health` | Estado del servicio y modo de cada integración (real o contingencia) | `200` |
| `POST` | `/uploads/sign` | URL firmada para subir la foto directo a Storage (`PUT` desde el navegador; el backend no recibe bytes) | `200` · `422` · `503` |
| `POST` | `/reports` | Crea el reporte (JSON: `description`, `location{label,latitude,longitude}`, `photo_path`, `ticket_311`), lo clasifica y agrupa duplicados; folio `MC-AAAA-NNNN` | `201` · `422` |
| `GET` | `/reports/{folio}` | Estado del expediente, entidad actual y desde cuándo, participaciones e historial | `200` · `404` |
| `GET` | `/reports` | Últimos reportes, paginados | `200` |
| `GET` | `/waste-sites`, `/waste-sites/geojson`, `/waste-sites/{id}` | Puntos comunitarios (28 tinacos del mapa de la JDL) | `200` · `404` |
| `GET` · `POST` | `/webhooks/whatsapp` | Verificación (`hub.challenge`) y recepción de mensajes de Meta (texto, ubicación, imagen) | `200` · `403` |

**Panel de la JDL** (`/admin`, sin autenticación en el prototipo)

| Método | Ruta | Descripción | Respuestas |
|---|---|---|---|
| `GET` | `/admin/reports` | Lista paginada con filtros `status`, `category`, `urgency`, `from`, `to` | `200` |
| `GET` | `/admin/reports/{id}` | Expediente completo | `200` · `404` |
| `PATCH` | `/admin/reports/{id}` | Corrige categoría, urgencia, resumen, `ticket_311`; `validated: true` valida | `200` · `422` |
| `POST` | `/admin/reports/{id}/classify` | Reintenta la clasificación con IA | `200` |
| `POST` | `/admin/reports/{id}/entities` | Agrega una entidad competente | `201` · `404` · `409` |
| `PATCH` | `/admin/reports/{id}/entities/{ceid}` | Cambia el estado de una participación; transición inválida → `409` | `200` · `409` |
| `POST` | `/admin/reports/{id}/entities/{ceid}/derive` | Deriva a otra entidad: origen `Derivada` con fecha, destino nace con recepción | `200` · `404` · `409` |
| `POST` | `/admin/reports/{id}/send` | Envía el correo a las participaciones pendientes; `503` solo si ninguna pudo enviarse | `200` · `503` |
| `GET` | `/admin/stats` | Tablero de cumplimiento por entidad (abiertos, tiempo promedio, derivados más de una vez, vencidos) | `200` |
| `GET` · `PUT` | `/admin/routing` | Tabla categoría → entidad → responsabilidad | `200` · `422` |
| `GET` · `PATCH` | `/admin/entities`, `/admin/entities/{code}` | Catálogo de entidades y sus correos (buzones de demo) | `200` · `404` |
| `GET` | `/admin/categories` | Categorías del catálogo | `200` |

### Manejo de respuestas no exitosas

Principio de diseño: **el reporte nunca se pierde** (RNF1).

| Situación | Qué hace el sistema | Qué ve el usuario |
|---|---|---|
| Falla o tarda la API de IA | Guarda el reporte con `classification_status = pendiente`; reintento desde el panel | "Recibimos tu reporte; la clasificación quedará lista en breve" |
| Falla el correo a una entidad | Esa participación queda `email_status = pendiente`, con reintento individual; `503` solo si ninguna pudo enviarse | Aviso en el panel con botón de reintento |
| Límite de uso de la IA (429) | Mismo tratamiento que una falla, con reintento posterior | Igual que arriba |
| Respuesta sin datos de la IA | Se aplica la clasificación por reglas de palabras clave (fallback) | Clasificación marcada como "provisional" |
| Falla la recepción por WhatsApp | El webhook responde 200 a Meta y registra el error para reintento | Mensaje automático pidiendo reenviar |
| Entrada inválida | Validación con Pydantic (`422`) y mensajes comprensibles (RNF5) | Texto claro junto al campo |

### Plan de contingencia

Si falta Internet o falla un servicio externo durante la demo: datos de respaldo precargados,
respuestas simuladas documentadas y un **video de la demostración**. Los correos de la demo van a
**buzones controlados por el equipo**, nunca a las entidades reales.

## IA o automatización

- **Clasificación** de cada reporte (categoría, urgencia, entidades competentes) y **resumen**, con
  corrección manual por la JDL.
- **Detección de duplicados** por categoría, cercanía y tiempo.
- **Borrador de la nota formal** a la Alcaldía con los casos del periodo (mejora futura si no
  alcanza el tiempo).
- **Automatización:** envío de correos según la tabla de enrutamiento; estados del expediente
  calculados; bot de WhatsApp que guía al vecino.
- **Privacidad:** a la API de IA solo se envían el texto y la imagen del reporte, nunca datos
  personales del residente (RNF6) ni datos del censo (RNF9). Si la IA no responde, un conjunto de
  reglas por palabras clave clasifica el reporte para que el flujo no se detenga.

## Impacto social o comercial

- **A quién beneficia:** residentes de El Cangrejo, administraciones de PH, directiva de la JDL,
  Junta Comunal de Bella Vista, entidades responsables, restaurantes de Vía Argentina y sus visitantes.
- **Social:** cada reporte recibe seguimiento; la JDL gestiona con evidencia e indicadores y **sabe
  dónde se traba cada caso**; las entidades reciben casos claros y sin duplicados; ninguna puede
  cerrar su parte "pasándola" a otra sin que quede registro.
- **Comercial:** la guía gastronómica aporta valor al visitante y abre ingresos (fichas destacadas y
  promociones) que sostienen el módulo cívico, gratuito para la comunidad.
- **Replicable:** categorías, entidades y correos son configurables, así que la plataforma puede
  llevarse a otra Junta de Desarrollo Local sin cambiar el código (RNF8).

## Nosotros

| Integrante | Carrera y año | Rol en el proyecto | GitHub |
|---|---|---|---|
| Cornelio Guerra | Lic. en Sistemas de Información Gerencial, 3.er año | Backend y hosting (más por definir) | [@Cornelio-Guerra](https://github.com/Cornelio-Guerra) |
| Jesus Guerra | Lic. en Sistemas de Información Gerencial, 3.er año | Frontend, APIs y chatbot (más por definir) | [@jesus12ga](https://github.com/jesus12ga) |

## Demo

- **Demostración:** en vivo sobre el despliegue. La organización no exigió video; el respaldo si falla la
  conexión son las capturas del recorrido y el modo de contingencia (SQLite, clasificación por reglas y
  correo simulado), que levanta el proyecto sin ninguna credencial.
- **Capturas:** [`docs/capturas/recorrido/`](docs/capturas/recorrido/) — recorrido completo en móvil y escritorio
  (entrada, reporte, expedientes del vecino, mapa, panel de la JDL y tablero de cumplimiento), tomado de producción.
- **Despliegue:** <https://micangrejo.vercel.app> (Vercel, plan Hobby; frontend y backend en el mismo dominio; API en `/api/v1`, documentación en `/api/v1/docs`)
- **Datos de demostración:** la base contiene seis expedientes de ejemplo (un caso con dos entidades y una vencida, una derivación Policía → Alcaldía, un caso resuelto tras derivar a ENSA, uno pendiente de validación, uno urgente de seguridad y un duplicado agrupado) para que el tablero de cumplimiento muestre información desde el primer minuto. Se restauran en cualquier momento con `python scripts/sembrar_demo.py --confirmar` (desde `backend/`; borra lo que haya y vuelve a sembrar).
- **Acceso:** la pantalla de inicio permite elegir el rol (Administrador JDL, Residente, Visitante)
  con un correo, **sin contraseña**. Es una limitación conocida del prototipo (ver *Seguridad*).
- **Probar el bot de Telegram:** escribe a [@MiCangrejoBot](https://t.me/MiCangrejoBot) lo que sucede, comparte
  tu ubicación con el clip y responderá con el folio y la categoría que asignó la IA. Para consultar un caso:
  `estado MC-2026-0001`. También está en el menú del residente dentro de la aplicación.
- **WhatsApp:** el canal está implementado en el backend (webhook `POST /api/v1/webhooks/whatsapp`, verificado
  contra Meta) pero **no activado en esta demostración**: requiere las credenciales de la aplicación de Meta
  (`META_ACCESS_TOKEN` y `META_PHONE_NUMBER_ID`) y registrar los celulares de prueba. En la aplicación aparece
  anunciado como *Próximamente*. Sin esas claves, el reporte se crea desde el formulario web.
- **Datos de demostración restaurados por última vez:** 12 de septiembre de 2026, con correos reales enviados
  al buzón del equipo (`scripts/sembrar_demo.py --confirmar --correo-real`).

---

## Tecnologías

| Capa | Tecnología | Estado |
|---|---|---|
| Frontend | React 19 + TypeScript + Vite 8, Tailwind CSS 4, shadcn/ui (Radix), lucide-react | Implementado |
| Mapa | Leaflet 1.9 + react-leaflet 5 + OpenStreetMap | Implementado |
| Backend / API | Python 3.13 + FastAPI + SQLModel + Uvicorn | Implementado |
| Base de datos | **Supabase Postgres** (pooler en modo transacción) con SQLite local como contingencia | Implementado (cambia con `DATABASE_URL`) |
| Fotos | **Supabase Storage** con URL firmada desde el navegador | Implementado en el backend |
| Inteligencia artificial | Gemini Flash (Google AI Studio, nivel gratuito) + reglas de respaldo | Implementado |
| Correo | SMTP con `smtplib`: Resend en producción (Gmail con contraseña de aplicación sirve en local) y modo simulado | Implementado |
| WhatsApp | WhatsApp Cloud API de Meta (webhook) | Implementado en el backend |
| Hosting | **Vercel** (un proyecto con *Services*: frontend + backend en el mismo dominio) | Desplegado: <https://micangrejo.vercel.app> |
| Control de versiones | Git + GitHub | Implementado |

## Arquitectura

```
Navegador: React + Vite + Leaflet/OSM      WhatsApp ─► Meta Cloud API (webhook)
          │  /api/v1  (mismo dominio)                    │
          └─────────►  FastAPI en Vercel Functions  ◄────┘
                        │        │        │
      Gemini Flash ◄────┘        │        └────► SMTP (Resend) ──► Entidades (+ copia al residente)
                                 ▼
                 Supabase: Postgres (expediente) + Storage (fotos)
                 (hoy: SQLite local)
```

## Persistencia de datos

- Tablas `entities`, `routing_rules`, `cases`, `case_entities` y `status_history` (SQLModel), creadas al
  arrancar y sembradas desde `backend/app/data/catalog.json`. Con `DATABASE_URL` van a **Supabase
  Postgres** (pooler en modo transacción); sin ella, a SQLite en `backend/data/micangrejo.db`
  (no se versiona). Los puntos del mapa se leen de `backend/app/data/waste_sites.json`.
- Fotos en **Supabase Storage** (bucket `evidencias`), subidas por el navegador con URL firmada;
  el expediente solo guarda `photo_path`. Los datos del censo de PH son de acceso restringido (RNF9).

## Seguridad y limitaciones conocidas

- Las credenciales van en variables de entorno (en Vercel, en el panel del proyecto); el repositorio
  solo incluye `.env.example` sin valores (RNF2). La clave `service_role` de Supabase nunca sale del
  servidor.
- **El panel de administración no tiene autenticación** en el prototipo: la pantalla de inicio es un
  selector de rol sin contraseña. Es una decisión consciente para el reto; en producción cada
  entidad y la JDL tendrían usuario propio.
- Los datos del mapa de tinacos provienen del mapa comunitario compartido por la JDL; deben
  validarse antes de producción.

## Instalación

### Requisitos previos

- Node.js 20 o superior y npm
- Python 3.13 (en Mac con el Python de Apple, usar `python3.13`)
- Git
- Para las integraciones reales: API key de Gemini (Google AI Studio), API key de Resend (o
  contraseña de aplicación de Gmail para pruebas locales), proyecto de Supabase y app de Meta for Developers

### 1. Clonar

```bash
git clone https://github.com/CarlosR10/2G_IIRetoEmprende.git
cd 2G_IIRetoEmprende
```

### 2. Backend

```bash
cd backend
python3.13 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env               # Windows: Copy-Item .env.example .env
```

Sin credenciales en `.env` el backend arranca igual, en **modo de contingencia** (SQLite, clasificación
por reglas, correo simulado, reportes sin foto); `GET /api/v1/health` muestra el modo de cada pieza.

Alternativa sin crear el entorno a mano (requiere [uv](https://docs.astral.sh/uv/)):

```bash
uv run --with-requirements requirements.txt uvicorn app.main:app --reload --port 8000
```

### 3. Frontend

```bash
cd ../frontend
npm install
```

## Configuración

| Archivo | Variable | Ejemplo | Para qué | Estado |
|---|---|---|---|---|
| `backend/.env` | `FRONTEND_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173` | Orígenes autorizados por CORS (solo en desarrollo local) | Implementada |
| `backend/.env` | `GEMINI_API_KEY` | `tu-clave` | Clasificación con IA | Implementada |
| `backend/.env` | `SMTP_USER`, `SMTP_PASSWORD` | correo del equipo / contraseña de aplicación | Envío a entidades | Implementada |
| `backend/.env` | `DATABASE_URL` | URL del pooler de Supabase (puerto 6543) | Postgres | Implementada |
| `backend/.env` | `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` | — | URL firmadas para fotos (solo servidor) | Implementada |
| `backend/.env` | `META_VERIFY_TOKEN`, `META_ACCESS_TOKEN`, `META_PHONE_NUMBER_ID` | — | Webhook de WhatsApp | Implementada |
| `backend/.env` | `SLA_DIAS` | `5` | Plazo para marcar casos vencidos | Implementada |
| `frontend/.env` | `VITE_API_BASE_URL` | `http://localhost:8000/api/v1` | Dirección del backend (por defecto ya apunta ahí) | Implementada |

Los `.env` están en `.gitignore` y **nunca** se suben. Solo se versiona `.env.example`.

## Ejecución

**Terminal 1 — backend** (<http://localhost:8000>, documentación en `/docs`):

```bash
cd backend && source .venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

**Terminal 2 — frontend** (<http://localhost:5173>):

```bash
cd frontend && npm run dev
```

## Uso

1. Abre <http://localhost:5173>, escribe un correo y elige el rol **Residente**.
2. Crea un reporte con descripción, referencia de ubicación (o "Usar ubicación actual") y foto.
   Guarda el **folio** que aparece.
3. Entra como **Administrador JDL** para ver el mapa comunitario y el panel de reportes.
4. Consulta el estado de un reporte en `GET /api/v1/reports/{folio}` o desde `/docs`.

> El formulario envía el reporte a `POST /api/v1/reports` y la foto se sube firmada a Storage; en el
> navegador solo se guardan los folios del vecino, para que "Mis reportes" funcione sin cuentas de usuario.

## Estructura del repositorio

```
2G_IIRetoEmprende/
├── README.md
├── .gitignore
├── vercel.json                  # un proyecto: frontend + backend (Services)
├── docs/
│   ├── api-contract.md          # contrato de la API v1.1 con ejemplos reales
│   └── DESPLIEGUE.md            # Vercel + Supabase paso a paso
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI, CORS, routers
│   │   ├── database.py          # SQLModel: Postgres (pooler) o SQLite
│   │   ├── models.py            # cases, case_entities, entities, routing_rules, status_history
│   │   ├── core/config.py       # variables de entorno y modo de contingencia
│   │   ├── routers/             # health, reports, uploads, admin, webhooks, waste_sites
│   │   ├── schemas/             # entradas y salidas (Pydantic)
│   │   ├── services/            # servicio_expedientes, classifier, mailer, storage, whatsapp, catalog
│   │   └── data/                # catalog.json (entidades, categorías, enrutamiento), waste_sites.json
│   ├── tests/                   # pruebas automáticas (pytest)
│   ├── scripts/                 # verificar_entorno.py (diagnóstico), sembrar_demo.py (datos de demostración)
│   ├── requirements.txt
│   └── .env.example
└── frontend/
    ├── src/
    │   ├── App.tsx
    │   ├── components/          # LoginScreen, ReportForm, WasteMap, Workspace, ui/
    │   └── services/            # api.ts, reportService.ts
    ├── package.json
    └── vite.config.ts
```

---

## Uso responsable de IA

> Sección obligatoria del reglamento (§6, criterio A8). Se completa con lo que realmente se use
> durante el reto.

### 1. Herramientas de IA utilizadas

| Herramienta | Modelo | Quién la usó |
|---|---|---|
| Claude Code (Anthropic) | Claude Opus 5 / Claude Fable 5.1 | Cornelio Guerra |
| Codex (OpenAI) | Codex | Jesus Guerra |

La coautoría queda registrada commit por commit. En la rama `main` hay **39 commits**, de los cuales **24
declaran la herramienta** en el pie del mensaje: 12 con Claude Opus 5, 10 con Claude Fable 5.1 y 2 con Codex
(`85852cb` y `d4c5a73`, del frontend). Se comprueba con:

```bash
git log origin/main --format='%(trailers:key=Co-authored-by,valueonly)' | grep -v '^$' | sort | uniq -c
```

### 2. Para qué se utilizaron

- Redactar y actualizar este README a partir del *Documento de Visión* (v1.0 y v1.1).
- Analizar opciones de arquitectura y redactar los issues #2, #3 y #4 con pros y contras.
- Verificar límites y documentación de servicios externos (Vercel, Supabase, Gemini, Meta, 311).
- Generar el backend del expediente (modelos, servicios, routers), su suite de pruebas y los scripts de
  diagnóstico y de datos de demostración.
- Construir el frontend: vistas por rol, mapas, exportación del expediente a PDF y el sistema visual
  (`DESIGN.md`, `PRODUCT.md`).
- Integrar los canales de mensajería (webhooks de WhatsApp y de Telegram) y el despliegue en Vercel.

### 3. Partes generadas o asistidas por IA

| Archivo o módulo | Qué hizo la IA |
|---|---|
| `README.md` | Borrador y actualización a partir de la visión y las decisiones del equipo |
| Issues #2, #3, #4 | Redacción del análisis de opciones |
| `backend/app/**` (modelos, servicios, routers) | Generación del código sobre el backend base del equipo, siguiendo las decisiones de los issues #3 y #4; revisado y probado por Cornelio |
| `backend/tests/`, `backend/scripts/`, `docs/api-contract.md`, `docs/DESPLIEGUE.md`, `vercel.json` | Generados con agentes de Claude Code a partir del código ya escrito |

### 4. Partes modificadas, revisadas o desarrolladas por el equipo

- **Desarrollado por el equipo:** la idea, el documento de visión, las decisiones de arquitectura
  (issues #3 y #4), el backend base (Jesus) y el frontend.
- **Revisado y modificado.** Cuatro correcciones reales sobre lo que propuso la IA:
  1. **Agrupación de duplicados rota.** El código generado agrupaba el reporte repetido pero dejaba sus
     participaciones vivas, así que el tablero contaba casos abiertos que no existían. Añadimos
     `merged_into_id`, borramos las participaciones del duplicado y bloqueamos su edición con un `409`.
  2. **Variables de entorno vacías.** Usaba `getenv(clave, valor_por_defecto)`, que trata `CLAVE=` como
     definida; lo cambiamos a `getenv(clave) or valor_por_defecto` para que una variable vacía active el
     modo de contingencia en vez de fallar.
  3. **Cadena de modelos de IA.** Descubrimos en producción que el nivel gratuito de Gemini permite 20
     peticiones por día **y por modelo**: con el modelo principal agotado todo caía a las reglas. Añadimos
     modelos de reserva y quitamos el razonamiento del principal, que superaba el tiempo de espera.
  4. **Correo.** La propuesta inicial era Gmail con contraseña de aplicación; Google bloquea ese inicio de
     sesión desde servidores, así que migramos a Resend por SMTP y lo verificamos desde el despliegue.

### 5. Cómo validamos que el código funciona

- Flujo completo probado con `curl` en modo de contingencia: crear, agrupar duplicados, validar, enviar,
  derivar, resolver, tablero, enrutamiento, `uploads/sign` sin Storage (503) y webhook (403/200).
- Suite `pytest` en `backend/tests/`: **69 pruebas automáticas** que cubren el ciclo del expediente, la
  agrupación de duplicados, las transiciones de estado, la derivación, el webhook y la cadena de modelos de IA.
- `backend/scripts/verificar_entorno.py` comprueba cada credencial real (base de datos, IA, correo,
  almacenamiento y WhatsApp) antes de la demo y dice en qué modo queda cada integración.
- Recorrido en producción (<https://micangrejo.vercel.app>) desde Chrome, con la consola abierta y sin errores:
  entrada como residente → reporte creado por el formulario → "Mis reportes" con entidad e historial → entrada
  como JDL → validar → marcar recibida → acciones de derivación y estado → dashboard con `/admin/stats`.

### 6. Medidas para no exponer datos sensibles

- Claves de IA, correo, Supabase y Meta solo en variables de entorno; `.env` excluido por
  `.gitignore`; `.env.example` sin valores reales (RNF2).
- A la API de IA solo se envían el texto y la imagen del reporte, sin datos personales del residente (RNF6).
- Los datos del censo de PH nunca se envían a la IA y solo los consultan la administración del PH,
  la JDL y la Junta Comunal (RNF9).
- Durante la demo, los correos van a buzones controlados por el equipo, no a las entidades reales.
- No se pegan claves ni datos personales en los prompts de las herramientas de IA.

---

## Licencia

Código bajo licencia **MIT** (ver [`LICENSE`](LICENSE)). Los datos abiertos del 311 (AIG) se usan bajo
CC-BY y los mosaicos de mapa según la [política de OpenStreetMap](https://operations.osmfoundation.org/policies/tiles/).

---

*Este README fue redactado con asistencia de Claude Code y revisado por el equipo 2G.*

Co-authored-by: Claude Fable 5.1 <noreply@anthropic.com>
