import type { ReactNode } from 'react'
import type { LucideIcon } from 'lucide-react'
import { AlertCircle, LoaderCircle, RefreshCw } from 'lucide-react'

import type { CaseStatus, ParticipationStatus } from '@/services/api'
import { Button, Marginalia, StampMark, Tag, mono, serif, t } from '@/design/tokens'

// Primitivas compartidas por todas las vistas de la app. Mantienen un solo estilo: papel, fichas
// blancas con regla, títulos en serifa, marginalia en monoespaciada, coral solo para la acción.

export function PageIntro({ title, description, marginalia, marginaliaExact = false, action }: { title: string; description?: string; marginalia?: string; marginaliaExact?: boolean; action?: ReactNode }) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-4">
      <div className="min-w-0">
        {marginalia && <Marginalia className="block" exact={marginaliaExact}>{marginalia}</Marginalia>}
        <h1 className="mt-1 text-[30px] font-medium leading-[1.05] tracking-[-0.015em] sm:text-[38px]" style={{ fontFamily: serif }}>
          {title}
        </h1>
        {description && (
          <p className="mt-2 max-w-2xl text-[14px] leading-6" style={{ color: t.muted }}>
            {description}
          </p>
        )}
      </div>
      {action}
    </div>
  )
}

export function Ficha({ children, className = '', padded = true, hero = false }: { children: ReactNode; className?: string; padded?: boolean; hero?: boolean }) {
  return (
    <section className={`rounded-xl border ${padded ? 'p-5' : ''} ${hero ? 'shadow-[0_24px_40px_-32px_rgba(30,45,38,.4)]' : ''} ${className}`} style={{ background: t.white, borderColor: t.rule }}>
      {children}
    </section>
  )
}

export function FichaHeader({ title, description, icon: Icon, aside, className = '' }: { title: string; description?: string; icon?: LucideIcon; aside?: ReactNode; className?: string }) {
  return (
    <div className={`flex items-start justify-between gap-3 ${className}`}>
      <div className="flex min-w-0 items-start gap-3">
        {Icon && (
          <span className="grid size-9 shrink-0 place-items-center rounded-lg" style={{ background: t.paper2, color: t.forest }}>
            <Icon size={18} />
          </span>
        )}
        <div className="min-w-0">
          <h2 className="text-[20px] font-medium leading-tight" style={{ fontFamily: serif }}>
            {title}
          </h2>
          {description && (
            <p className="mt-0.5 text-[13px]" style={{ color: t.muted }}>
              {description}
            </p>
          )}
        </div>
      </div>
      {aside}
    </div>
  )
}

export function SectionTitle({ children, aside }: { children: ReactNode; aside?: ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-3">
      <h2 className="text-[20px] font-medium leading-tight" style={{ fontFamily: serif }}>
        {children}
      </h2>
      {aside}
    </div>
  )
}

// Cuadrado con la cifra grande en serifa y la etiqueta en marginalia: tipografía en extremos.
// El detalle se oculta en móvil para que el cuadrado no se deforme.
export function Metric({ label, value, detail }: { label: string; value: string | number; detail?: string }) {
  return (
    <Ficha className="flex aspect-square flex-col justify-center" padded={false}>
      <div className="px-3 sm:px-4">
        <p className="text-[32px] font-medium leading-none tabular-nums tracking-[-0.02em] sm:text-[40px]" style={{ fontFamily: serif }}>
          {value}
        </p>
        <Marginalia className="mt-2 block">{label}</Marginalia>
        {detail && (
          <p className="mt-2 hidden text-[12px] leading-4 sm:block" style={{ color: t.muted }}>
            {detail}
          </p>
        )}
      </div>
    </Ficha>
  )
}

export const caseStatusLabel: Record<CaseStatus, string> = {
  Recibido: 'Recibido',
  'En gestión': 'En revisión JDL',
  'Enviado a entidades': 'En entidades',
  Resuelto: 'Resuelto',
}

function caseTone(status: string): 'coral' | 'forest' | 'muted' | 'ink' {
  if (status === 'Enviado a entidades') return 'coral'
  if (status === 'Resuelto') return 'forest'
  if (status === 'En gestión') return 'ink'
  return 'muted'
}

export function CaseTag({ status }: { status: string }) {
  return <Tag tone={caseTone(status)}>{caseStatusLabel[status as CaseStatus] ?? status}</Tag>
}

export function CaseStamp({ status, className = '' }: { status: string; className?: string }) {
  const tone = status === 'Resuelto' || status === 'En gestión' || status === 'Recibido' ? 'forest' : 'coral'
  return <StampMark className={className} text={caseStatusLabel[status as CaseStatus] ?? status} tone={tone} />
}

export function participationTone(status: ParticipationStatus, overdue = false): 'coral' | 'forest' | 'muted' | 'ink' {
  if (overdue) return 'coral'
  if (status === 'Derivada') return 'muted'
  if (status === 'Resuelta') return 'forest'
  if (status === 'Asignada') return 'ink'
  return 'coral'
}

export function Folio({ value, className = '' }: { value: string; className?: string }) {
  return (
    <span className={`text-[12px] tracking-wide ${className}`} style={{ fontFamily: mono, color: t.forest }}>
      {value}
    </span>
  )
}

export function Info({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="min-w-0">
      <Marginalia className="block">{label}</Marginalia>
      <p className="mt-1 text-[14px] leading-5">{value}</p>
    </div>
  )
}

export function Notice({ children, tone = 'coral', icon: Icon = AlertCircle }: { children: ReactNode; tone?: 'coral' | 'forest'; icon?: LucideIcon }) {
  const color = tone === 'coral' ? t.coral : t.forest
  return (
    <p className="flex items-start gap-2 rounded-lg border px-4 py-3 text-[14px] leading-5" role={tone === 'coral' ? 'alert' : 'status'} style={{ borderColor: t.rule, background: t.white, color: t.ink }}>
      <Icon className="mt-0.5 shrink-0" size={16} style={{ color }} /> <span>{children}</span>
    </p>
  )
}

export function LoadingState({ label }: { label: string }) {
  return (
    <div className="flex min-h-40 items-center justify-center gap-2 text-[14px]" style={{ color: t.muted }}>
      <LoaderCircle className="size-4 animate-spin" /> {label}
    </div>
  )
}

export function ErrorState({ error, onRetry }: { error: string; onRetry: () => void }) {
  return (
    <Ficha>
      <p className="flex items-center gap-2 text-[14px]">
        <AlertCircle size={16} style={{ color: t.coral }} /> {error}
      </p>
      <Button className="mt-3" onClick={onRetry} size="xs" tone="outline">
        <RefreshCw size={14} /> Reintentar
      </Button>
    </Ficha>
  )
}

export function EmptyState({ icon: Icon, title, description, action }: { icon: LucideIcon; title: string; description: string; action?: ReactNode }) {
  return (
    <section className="flex flex-col items-center rounded-xl border border-dashed p-10 text-center" style={{ borderColor: t.rule, background: t.white }}>
      <span className="grid size-12 place-items-center rounded-full" style={{ background: t.paper2, color: t.forest }}>
        <Icon size={22} />
      </span>
      <h2 className="mt-4 text-[22px] font-medium" style={{ fontFamily: serif }}>
        {title}
      </h2>
      <p className="mx-auto mt-2 max-w-sm text-[14px] leading-6" style={{ color: t.muted }}>
        {description}
      </p>
      {action && <div className="mt-5">{action}</div>}
    </section>
  )
}

export function formatDateTime(value: string): string {
  return new Intl.DateTimeFormat('es-PA', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value))
}
