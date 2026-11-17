import type { ReactNode } from 'react'

import { ALCANCE, estaImplementado, etiquetaAlcance, type ClaveAlcance } from '@/alcance'
import { mono, t } from '@/design/tokens'

/**
 * Atenúa una pantalla o sección que no forma parte del alcance de la Fase 3.
 * Si la sección está implementada, devuelve a sus hijos tal cual, sin envoltorio.
 * La etiqueta queda fuera del subárbol inerte para que los lectores de pantalla la anuncien.
 */
export function FueraDeAlcance({ clave, children, className = '' }: { clave: ClaveAlcance; children: ReactNode; className?: string }) {
  if (estaImplementado(clave)) return <>{children}</>

  const { nota } = ALCANCE[clave]

  return (
    <div className={`relative ${className}`}>
      {/* Altura cero y pegajosa: la etiqueta flota sobre el contenido atenuado y lo acompaña al desplazarse. */}
      <div className="pointer-events-none sticky top-20 z-10 flex h-0 items-start justify-center overflow-visible px-3">
        <div className="mt-3 max-w-md rounded-lg border px-4 py-2.5 text-center shadow-[0_10px_24px_-14px_rgba(30,45,38,0.55)]" role="note" style={{ background: t.white, borderColor: t.forest }}>
          <p className="text-[11px] font-bold uppercase tracking-[.14em]" style={{ fontFamily: mono, color: t.forest }}>
            {etiquetaAlcance(clave)}
          </p>
          {nota && (
            <p className="mt-1 text-[12px] leading-4" style={{ color: t.muted }}>
              {nota}
            </p>
          )}
        </div>
      </div>
      <div aria-disabled="true" inert style={{ opacity: 0.45, filter: 'grayscale(1)', pointerEvents: 'none', userSelect: 'none' }}>
        {children}
      </div>
    </div>
  )
}

/** Franja de alcance de la entrega, una sola vez por pantalla principal. */
export function BannerAlcance() {
  return (
    <div className="border-b px-4 py-2 text-[12px] leading-5 sm:px-7" role="note" style={{ background: t.paper2, borderColor: t.rule, color: t.ink }}>
      <strong>Fase 3 — Implementación.</strong> Esta entrega implementa de extremo a extremo CU-01 Registrar reporte, CU-03 Validar y enviar expediente y CU-04 Registrar seguimiento de entidad (con CU-05 Derivar). Las secciones atenuadas quedaron fuera del alcance aprobado en la Fase 1.
    </div>
  )
}
