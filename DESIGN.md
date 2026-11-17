# Design · miCangrejo

<!-- impeccable:design-schema 1 -->

Mundo visual elegido el 12 de septiembre de 2026: **Expediente**. El buzón de quejas del barrio como
documento de oficio: papel claro, tinta verde bosque y sello coral (los dos colores del logo real de la
JDL), serifa en los títulos, folios en monoespaciada, y el recorrido por entidad como libro de registro.
Fuente de verdad en código: `frontend/src/design/tokens.tsx`.

## Guardrails (fijados por el equipo el 12/09/2026)

- **Marginalia**: folios, fechas, horas, coordenadas y marcas de regla en monoespaciada diminuta
  (10–11 px, mayúsculas, tracking abierto) en los márgenes de cada pantalla. El expediente siempre
  muestra folio y fecha; las portadas muestran coordenadas de El Cangrejo (8.9908° N, 79.5285° O).
- **Tipografía en extremos**: display monumental en Source Serif 4 (≥ 40 px en móvil, ≥ 60 px en
  escritorio) y etiquetas mono diminutas; muy poco tamaño medio. El cuerpo se mantiene corto.
- **Casi monocromo con un acento cálido**: papel, tinta y verde bosque forman el fondo de baja croma;
  el coral es el único acento cálido y se reserva para la acción principal y el estado activo.
- **Fotografía**: solo fotos propias del barrio (por ejemplo `frontend/public/parque-andres-bello.jpg`,
  Parque Andrés Bello), nunca stock. Se usan translúcidas bajo el campo verde bosque: `opacity` 0.3,
  `mix-blend-mode: luminosity` y un degradado verde que se vuelve sólido hacia el pie, para que el
  texto y la marginalia mantengan contraste.
- **Nunca**: degradados morados, blobs 3D, fotografía de stock sin textura, todo redondeado por
  amabilidad, filas de features en grilla de íconos, tipografía solo Inter/sistema, paletas
  distribuidas uniformemente. Excepción acordada: los botones píldora del login vienen de la
  referencia elegida por el equipo.

## Color

| Token | Valor | Uso |
|---|---|---|
| `paper` | `#f5f0e6` | Fondo general de la app (papel). |
| `paper2` | `#ece5d4` | Segundo papel: fondos de control segmentado, pila de fichas, chips neutros. |
| `white` | `#fffdf8` | Fichas, tarjetas, campos. Nunca `#ffffff` puro. |
| `ink` | `#1e2d26` | Texto principal. Nunca negro puro. |
| `forest` | `#2f5d50` | Acción secundaria, folios, enlaces, selección, títulos en énfasis. |
| `forestDeep` | `#24493f` | Hover de superficies verde bosque. |
| `coral` | `#d9432b` | Acción primaria, sellos, estado activo en entidad, urgencia. |
| `muted` | `#6b7a71` | Texto secundario (contraste ≥ 4.5:1 sobre papel y blanco). |
| `rule` | `#d6ccb6` | Reglas, bordes de ficha y tabla. Un solo peso: 1 px. |

Estrategia: **Restrained**. Neutros cálidos con un acento (coral) y un secundario (verde bosque).
El coral no se usa como fondo de área; vive en botones, sellos y una línea de estado. Un campo verde
bosque completo solo se permite en la portada o el login (variación "Campo verde").

## Tipografía

- Títulos: **Source Serif 4** (400–700, cursiva permitida para un énfasis por título). Tamaños:
  60/52/40/36/32/28/26/22/20/18 px, interlineado 1.02–1.2, tracking −0.015 em en ≥ 36 px.
- Interfaz y cuerpo: **Geist** (`'Geist Variable'`), 13–16 px, interlineado 1.45–1.6, medida ≤ 70 ch.
- Identificadores y marginalia (folios `MC-2026-0010`, fechas, coordenadas): monoespaciada
  (`ui-monospace`), 10–20 px, tracking abierto; en mayúsculas cuando actúan como etiqueta.
- Etiquetas de sección: 10–11 px, mayúsculas, tracking 0.14–0.16 em, color `muted`.
- Cifras (días, conteos): `tabular-nums`.

## Forma y espacio

- Radios: controles 8 px (`rounded-lg`), fichas y tarjetas 12–16 px, portada 16 px, hoja del login
  32 px arriba. Píldoras (999 px) en chips, en el selector Ingresar/Registrarme y en los botones del
  login (estructura tomada de la referencia elegida el 12/09/2026). Sellos 6 px con borde 2.5 px y
  rotación −6°.
- Elevación: **una sola** por superficie. Fichas usan borde `rule` 1 px; la ficha protagonista añade
  sombra suave con desplazamiento (`0 24px 40px -32px rgba(30,45,38,.4)`). Nunca borde + sombra
  ancha en la misma tarjeta pequeña.
- Ritmo: 4 px base; separación entre grupos 20–24 px, entre secciones 32–48 px; más aire arriba de
  un título que abajo.
- Contenedores: máximo 6xl (72 rem) para páginas, 3xl para formularios largos, md para tarjetas
  centradas.
- Responsivo por container queries: `@lg` (512 px) para filas en dos columnas de formulario,
  `@3xl` (768 px) para el paso a escritorio.

## Componentes

- **Button**: alto 48 px, radio 8 px, texto 15 px semibold. `coral` primario, `forest` secundario o
  firma, `ghost` (borde interior 1.5 px verde bosque), `paper` sobre campo verde. Foco visible con
  outline coral de 2 px desplazado.
- **StampMark**: sello de estado (borde 2.5 px, mayúsculas, −6°). Coral para estados de caso; verde
  bosque para etiquetas administrativas.
- **Folio**: monoespaciada verde bosque; siempre acompaña al título de una ficha.
- **Slip / ficha**: tarjeta blanca con borde `rule`, folio + fecha, título en serifa, ubicación con
  ícono, línea de estado ("Entidad · días") en coral si está activa, en verde si el caso está cerrado.
- **Libro de registro**: tabla con cabeceras en mayúsculas 10 px, filas separadas por `rule`, columna
  de días alineada a la derecha y tabular.
- **Historial**: lista con regla vertical 1.5 px y puntos huecos verde bosque; fecha · actor en 11 px.
- **Campos**: alto 48 px, borde `rule`, fondo `white`; foco con halo verde bosque al 18 %. Variante
  "con ícono" (login): caja de 16 px de radio, ícono verde bosque a la izquierda, etiqueta 12 px
  `muted` sobre el valor 16 px; foco cambia el borde a verde bosque.
- **Login**: panel verde bosque con la promesa en serifa blanca, hoja de papel con esquinas de 32 px,
  selector píldora Ingresar/Registrarme sobre `paper2`, botón píldora coral de 56 px, separador "O
  entra como" y dos accesos alternos en píldora blanca con borde `rule` (Visitante entra sin
  credenciales; Administrativo también en la demostración).
- **Selector de rol**: control segmentado (3 posiciones sobre `paper2`) o carnets (fila con ícono,
  descripción y radio). Siempre `role="radiogroup"`.
- **Tag**: etiqueta de estado para listas (mono 10 px, mayúsculas, borde 1.5 px, radio 4 px, sin
  rotación). Coral = activo/vencido, verde bosque = resuelto, tinta = en revisión, `muted` = derivada.
- **Metric**: cifra en serifa 40 px con etiqueta mono diminuta arriba y detalle 12 px debajo.
- **Marco de la app**: barra lateral blanca con regla, ítems numerados en mono (01, 02…), ítem activo
  en verde bosque y "Cerrar sesión" al pie de la barra; cabecera de papel con marginalia de rol,
  título en serifa 18 px, fecha, campana y la identidad del usuario (inicial en disco verde bosque,
  nombre y rol) en la esquina superior derecha. Sin botones de acción en la cabecera: las acciones
  viven en el menú lateral. Pie con regla de marcas, coordenadas y patrocinadores en marginalia.
- **Visitante**: sin barra lateral, sin cuenta ni notificaciones. Cabecera con logo, fecha y un
  botón "Salir" (outline); el contenido es solo la guía de restaurantes a altura completa.
- **Login (detalle)**: el logo de la JDL llena su círculo (56 px); la hoja se ancla arriba en
  escritorio para que el selector y los campos de correo y contraseña no se muevan al registrarse.
- **Mapas**: marcadores sobre `paper2` con borde `white`; el de residuos en coral; popups con radio
  12 px y tipografía de la app.
- Íconos: lucide, trazo 2 px, 14–18 px en línea, 20 px en pozos circulares.
- Primitivas en código: `frontend/src/design/ui.tsx` (PageIntro, Ficha, FichaHeader, SectionTitle,
  Metric, CaseTag, CaseStamp, Folio, Info, Notice, LoadingState, ErrorState, EmptyState).

## Estados y voz

- Estados del caso: Recibido → En revisión por la JDL → En entidades → Resuelto. Por entidad:
  Asignada, Recibida, En atención, Derivada, Resuelta. `Derivada` siempre en `muted`; estados activos
  en coral; `Resuelta`/`Resuelto` en verde bosque. Nunca color como única señal: siempre con texto.
- Errores en coral, 13 px, nombran el problema y la salida ("Escribe un correo válido, por ejemplo…").
- Voz: español de Panamá, tuteo, frases cortas, los nombres reales de las entidades (AAUD, ATTT,
  Juez de Paz, Policía Nacional, Alcaldía de Panamá).

## Movimiento

Una sola familia: `transition` de 150–200 ms con `hover:brightness-95` en botones y sombra que
aparece al pasar por una ficha. Sin entradas animadas por sección. `prefers-reduced-motion` respeta
lo mismo porque no hay más movimiento que ese.

## Evitar

Negro puro, blanco puro, degradados de fondo, vidrio, borde lateral de color en tarjetas, píldoras en
botones grandes, kickers sobre títulos, tarjetas anidadas, emoji como ícono, monoespaciada fuera de
folios y cifras.
