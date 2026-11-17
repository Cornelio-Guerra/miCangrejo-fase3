// Alcance aprobado en la Fase 1: solo CU-01, CU-03 y CU-04 se implementan
// de extremo a extremo en la Fase 3. El resto queda visible pero inactivo.
export type Alcance = 'implementado' | 'fuera-de-alcance' | 'no-implementado'

export type EntradaAlcance = { cu: string; estado: Alcance; nota: string }

export const ALCANCE = {
  registrarReporte:  { cu: 'CU-01', estado: 'implementado',     nota: '' },
  validarYEnviar:    { cu: 'CU-03', estado: 'implementado',     nota: '' },
  seguimiento:       { cu: 'CU-04', estado: 'implementado',     nota: '' },
  derivar:           { cu: 'CU-05', estado: 'implementado',     nota: 'Se implementa dentro de CU-04' },
  consultarFolio:    { cu: 'CU-02', estado: 'fuera-de-alcance', nota: 'No seleccionado para implementación en la Fase 1' },
  tablero:           { cu: 'CU-06', estado: 'fuera-de-alcance', nota: 'No seleccionado para implementación en la Fase 1' },
  iniciarSesion:     { cu: 'CU-07', estado: 'no-implementado',  nota: 'Diseñado en ADR-06; el panel del prototipo no exige credenciales' },
  restaurantes:      { cu: '—',     estado: 'fuera-de-alcance', nota: 'Funcionalidad del Reto Emprende, fuera del proyecto semestral' },
  basureros:         { cu: '—',     estado: 'fuera-de-alcance', nota: 'Funcionalidad del Reto Emprende, fuera del proyecto semestral' },
  telegram:          { cu: '—',     estado: 'fuera-de-alcance', nota: 'Canal del Reto Emprende; la Fase 2 define la mensajería por WhatsApp' },
  baseDeDatos:       { cu: '—',     estado: 'fuera-de-alcance', nota: 'Herramienta interna de desarrollo' },
} satisfies Record<string, EntradaAlcance>

export type ClaveAlcance = keyof typeof ALCANCE

const TEXTO_ESTADO: Record<Alcance, string> = {
  implementado: 'Implementado en la Fase 3',
  'fuera-de-alcance': 'Fuera del alcance de la Fase 3',
  'no-implementado': 'No implementado en la Fase 3',
}

export function estaImplementado(clave: ClaveAlcance): boolean {
  return ALCANCE[clave].estado === 'implementado'
}

/** Etiqueta legible, por ejemplo «CU-06 · Fuera del alcance de la Fase 3». */
export function etiquetaAlcance(clave: ClaveAlcance): string {
  const { cu, estado } = ALCANCE[clave]
  return cu === '—' ? TEXTO_ESTADO[estado] : `${cu} · ${TEXTO_ESTADO[estado]}`
}
