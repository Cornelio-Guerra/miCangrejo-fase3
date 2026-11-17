# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

- **Residente de El Cangrejo** (Ciudad de Panamá). Está en la calle o en su edificio, con el celular, frente a un problema del barrio (basurero desbordado, carro mal estacionado, ruido nocturno, luminaria dañada). Quiere reportarlo en menos de un minuto con foto y ubicación, y después saber **en qué entidad está su caso y desde cuándo**.
- **Administrador de la Junta de Desarrollo Local (JDL)**. Trabaja desde computadora. Valida la clasificación automática, aprueba el envío a cada entidad, registra respuestas y derivaciones, consulta el tablero de cumplimiento por entidad y genera la nota formal para la Alcaldía.
- **Administrador de PH** (propiedad horizontal): registra censo de residentes, brigadistas y preguntas para la Junta Comunal. Módulo planificado, no prioritario para la demo.
- **Visitante**: consulta la guía de restaurantes de Vía Argentina en un mapa.

## Product Purpose

miCangrejo convierte cada reporte vecinal en un **expediente único** con folio, categoría, ubicación, urgencia y **un estado por cada entidad competente**, registra cada derivación con fecha y mide dónde se detiene cada caso. Sustituye el grupo de WhatsApp, las llamadas, las hojas de cálculo y las cadenas de correo por un canal único. Éxito: el residente vuelve a reportar porque ve que su caso avanza; la JDL prioriza con datos y sustenta sus gestiones con evidencia consolidada.

## Positioning

Un buzón de quejas de barrio modernizado: el vecino deja su nota, la JDL la revisa y la eleva a la autoridad. Lo que ningún grupo de WhatsApp ni formulario 311 hace: **trazabilidad por entidad**. Cuando una entidad deriva el caso, no cierra su parte: queda `Derivada` con fecha y la nueva entidad nace con fecha de recepción. Eso hace visible dónde se estanca cada caso.

## Operating Context

- Concurso **II Reto Emprende 2026** (CONTECS 2026, FISC – Universidad Tecnológica de Panamá), 11 y 12 de septiembre de 2026. Equipo 2G: Cornelio Guerra y Jesús Guerra. Patrocinador: JDL de El Cangrejo. Contraparte: Junta Comunal de Bella Vista.
- Demo del reto: el ciclo completo del reporte con expediente por entidad y derivación. El jurado ve la app proyectada (escritorio) y en celular.
- Ciclo de vida del reporte: captura (web o WhatsApp) → clasificación automática por IA (Gemini: categoría, urgencia, entidades competentes, resumen; agrupa duplicados) → validación de la JDL → envío por correo a cada entidad con copia al residente → seguimiento por entidad → resolución.
- Entidades competentes reales: AAUD (aseo), ATTT (tránsito), Juez de Paz, Policía Nacional, Alcaldía de Panamá.
- Stack existente: React 19 + Vite + Tailwind 4 + shadcn (frontend), FastAPI + SQLite/Supabase (backend), desplegado en Vercel como un solo proyecto con dos servicios.

## Capabilities and Constraints

- Estados del caso (`CaseStatus`): `Recibido`, `En gestión`, `Enviado a entidades`, `Resuelto`.
- Estados por entidad (`ParticipationStatus`): `Asignada`, `Recibida`, `En atención`, `Derivada`, `Resuelta`. Cada participación tiene fechas (`received_at`, `attention_at`, `derived_at`, `resolved_at`), `days_in_entity` y `overdue` según un SLA en días.
- Urgencia: `Baja`, `Media`, `Alta`. Folio con formato `MC-2026-0012`.
- El reporte incluye descripción, ubicación (etiqueta + coordenadas opcionales), foto opcional, fuente (`web` o `whatsapp`), conteo de reportes agrupados, clasificación, entidades actuales, participaciones e historial.
- Módulos existentes: formulario de reporte, mis reportes por folio, panel admin (validar, enviar, derivar), tablero de cumplimiento, mapa de basureros y tinacos, mapa de restaurantes de Vía Argentina.
- Fuera de alcance del prototipo: cobro a negocios, apps nativas, integración directa con sistemas de entidades, acceso directo de las entidades, cuentas de usuario completas, simulacros.
- Restricción de trabajo: el diseñador no hace commit ni push; los cambios quedan en el árbol de trabajo.

## Brand Commitments

- Nombre: **miCangrejo**. Logo existente de la JDL: círculo verde bosque oscuro con un cangrejo rojo-coral y el texto "Junta de Desarrollo Local" (`frontend/public/logo-micangrejo.jpg`).
- **Referencia visual vinculante aportada por el usuario (12/09/2026):** app móvil de bienes raíces sobre fondo verde oliva oscuro con degradado, acento lima brillante en botones píldora, tarjetas translúcidas con borde fino claro, radios grandes, fotografía a sangre en la portada, chips de filtro, barra de detalle con métricas en cajas. El usuario quiere "un diseño como este" para miCangrejo, con versión escritorio y móvil.
- Decisión del usuario para la ronda de direcciones: **5 versiones**, cada una con pantallas de bienvenida, inicio de residente y detalle de reporte; mezcla libre de variaciones de estructura y de paleta; entregadas directamente en el código React.
- Idioma de la interfaz: español de Panamá, tuteo.
- **Guardrails de diseño (12/09/2026):** marginalia (coordenadas, IDs, ruler ticks, timestamps); tipografía en extremos (display monumental o mono diminuta, poco medio); fondo casi monocromo con un solo acento cálido. Nunca: degradados morados, blobs 3D, stock sin textura, todo redondeado, filas de íconos, solo Inter/sistema, paletas uniformes.
- **Mundo visual elegido (12/09/2026): Expediente** (papel claro, verde bosque y coral del logo, serifa en títulos). Documentado en `DESIGN.md` y `.impeccable/design.json`; tokens en `frontend/src/design/tokens.tsx`.

## Evidence on Hand

- README con problema, solución y ciclo de vida documentados (`README.md`).
- Contrato de API con tipos reales (`frontend/src/services/api.ts`, `docs/api-contract.md`).
- Logos de restaurantes de Vía Argentina (`frontend/public/restaurant-logos/`).
- No hay fotografías propias de El Cangrejo ni testimonios; no inventar cifras de impacto ni clientes. Los folios y reportes de demostración son sintéticos y deben etiquetarse como tales.

## Product Principles

1. Reportar debe tomar menos de un minuto desde el celular.
2. El estado por entidad y el "desde cuándo" son la información más importante de cada expediente.
3. La JDL valida; la IA propone. La interfaz siempre deja corregir la clasificación.
4. Nada se pierde: cada derivación queda con fecha y responsable.
5. Un solo canal para vecinos, JDL y visitantes, con lo que cada rol necesita y nada más.
