// Mundo visual de miCangrejo: Expediente. Papel claro, tinta verde bosque, sello coral (colores del
// logo de la JDL), serifa en títulos, folios en monoespaciada porque son identificadores.
// Fuente de verdad de DESIGN.md.

export const t = {
  paper: '#f5f0e6',
  paper2: '#ece5d4',
  ink: '#1e2d26',
  forest: '#2f5d50',
  forestDeep: '#24493f',
  coral: '#d9432b',
  muted: '#6b7a71',
  rule: '#d6ccb6',
  white: '#fffdf8',
}

export const serif = "'Source Serif 4', Georgia, serif"
export const sans = "'Geist Variable', system-ui, sans-serif"
export const mono = "ui-monospace, 'SF Mono', Menlo, Consolas, monospace"

// Marca de lugar para la marginalia de portadas y pies.
export const placeMark = 'EL CANGREJO'

export function todayMark(date = new Date()) {
  const day = String(date.getDate()).padStart(2, '0')
  const month = date.toLocaleDateString('es-PA', { month: 'short' }).replace('.', '').slice(0, 3)
  return `${day} ${month} ${date.getFullYear()}`.toUpperCase()
}

// Marginalia: etiqueta mono diminuta para folios, fechas, coordenadas y marcas de margen.
export function Marginalia({ children, className = '', color = t.muted, exact = false }: { children: React.ReactNode; className?: string; color?: string; /** Respeta mayúsculas y minúsculas del texto (por ejemplo, la marca miCangrejo). */ exact?: boolean }) {
  return (
    <span className={`text-[10px] uppercase tracking-[.18em] ${className}`} style={{ fontFamily: mono, color, textTransform: exact ? 'none' : undefined }}>
      {children}
    </span>
  )
}

// Regla de margen: marcas cada 8 px, como una regla de expediente. Geometría, no ilustración.
export function RulerTicks({ className = '', color = 'currentColor', width = 160 }: { className?: string; color?: string; width?: number }) {
  const ticks = Math.floor(width / 8)
  return (
    <svg aria-hidden="true" className={className} height="12" viewBox={`0 0 ${width} 12`} width={width}>
      {Array.from({ length: ticks + 1 }, (_, i) => (
        <line key={i} stroke={color} strokeWidth="1" x1={i * 8 + 0.5} x2={i * 8 + 0.5} y1={i % 5 === 0 ? 0 : 6} y2="12" />
      ))}
    </svg>
  )
}

export function Button({ children, tone = 'coral', size = 'md', className = '', onClick, type = 'button', pill = false, disabled = false }: { children: React.ReactNode; tone?: 'coral' | 'forest' | 'ghost' | 'paper' | 'outline'; size?: 'md' | 'sm' | 'xs'; className?: string; onClick?: () => void; type?: 'button' | 'submit'; pill?: boolean; disabled?: boolean }) {
  const styles =
    tone === 'coral'
      ? { background: t.coral, color: t.white }
      : tone === 'forest'
        ? { background: t.forest, color: t.white }
        : tone === 'paper'
          ? { background: t.white, color: t.forest }
          : tone === 'outline'
            ? { background: t.white, color: t.ink, boxShadow: `inset 0 0 0 1px ${t.rule}` }
            : { background: 'transparent', color: t.forest, boxShadow: `inset 0 0 0 1.5px ${t.forest}` }
  const sizes = { md: 'h-12 px-5 text-[15px]', sm: 'h-10 px-4 text-[14px]', xs: 'h-8 px-3 text-[13px]' }
  return (
    <button className={`inline-flex items-center justify-center gap-2 font-semibold transition hover:brightness-95 focus-visible:outline-2 focus-visible:outline-offset-2 disabled:cursor-not-allowed disabled:opacity-50 ${sizes[size]} ${pill ? 'rounded-full' : 'rounded-lg'} ${className}`} disabled={disabled} onClick={onClick} style={{ ...styles, outlineColor: t.coral }} type={type}>
      {children}
    </button>
  )
}

// Etiqueta de estado para listas: monoespaciada diminuta con borde, sin rotación (el sello rotado
// se reserva para cabeceras de expediente).
export function Tag({ children, tone = 'muted', className = '' }: { children: React.ReactNode; tone?: 'coral' | 'forest' | 'muted' | 'ink'; className?: string }) {
  const color = tone === 'coral' ? t.coral : tone === 'forest' ? t.forest : tone === 'ink' ? t.ink : t.muted
  return (
    <span className={`inline-flex items-center whitespace-nowrap rounded-[4px] border-[1.5px] px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-[.14em] ${className}`} style={{ borderColor: color, color, fontFamily: mono }}>
      {children}
    </span>
  )
}

export function StampMark({ text, className = '', tone = 'coral' }: { text: string; className?: string; tone?: 'coral' | 'forest' }) {
  const color = tone === 'coral' ? t.coral : t.forest
  return (
    <span className={`inline-block -rotate-6 rounded-md border-[2.5px] px-2.5 py-1 text-[11px] font-bold uppercase tracking-[.16em] ${className}`} style={{ borderColor: color, color, fontFamily: sans }}>
      {text}
    </span>
  )
}

export function Folio({ value, className = '' }: { value: string; className?: string }) {
  return (
    <span className={`font-mono text-[12px] tracking-wide ${className}`} style={{ color: t.forest }}>
      {value}
    </span>
  )
}

export function Field({ label, children, hint }: { label: string; children: React.ReactNode; hint?: string }) {
  return (
    <label className="block">
      <span className="text-[13px] font-semibold" style={{ color: t.ink }}>
        {label}
      </span>
      <div className="mt-1.5">{children}</div>
      {hint && (
        <span className="mt-1.5 block text-xs" style={{ color: t.muted }}>
          {hint}
        </span>
      )}
    </label>
  )
}

export const inputClass = 'h-12 w-full rounded-lg border px-4 text-[15px] outline-none transition focus:shadow-[0_0_0_3px_rgba(47,93,80,0.18)]'
export const inputSmClass = 'h-10 w-full rounded-lg border px-3 text-[14px] outline-none transition focus:shadow-[0_0_0_3px_rgba(47,93,80,0.18)]'
export const textareaClass = 'w-full rounded-lg border px-4 py-3 text-[15px] outline-none transition focus:shadow-[0_0_0_3px_rgba(47,93,80,0.18)]'
export const inputStyle = { background: t.white, borderColor: t.rule, color: t.ink } as const
