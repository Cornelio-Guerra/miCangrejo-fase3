import { useState } from 'react'
import type { FormEvent, ReactNode } from 'react'
import type { LucideIcon } from 'lucide-react'
import { ArrowRight, Compass, Eye, EyeOff, House, Lock, Mail, Medal, ShieldCheck, User } from 'lucide-react'

import { FueraDeAlcance } from '@/components/FueraDeAlcance'
import { Marginalia, RulerTicks, placeMark, sans, serif, t, todayMark } from '@/design/tokens'

export type UserRole = 'admin' | 'resident' | 'visitor'

export type AppSession = {
  name: string
  role: UserRole
}

type LoginScreenProps = {
  onLogin: (session: AppSession) => void
}

type Mode = 'login' | 'register'

const REMEMBER_KEY = 'micangrejo.correo'

function rememberedEmail(): string {
  try {
    return window.localStorage.getItem(REMEMBER_KEY) ?? ''
  } catch {
    return ''
  }
}

function persistEmail(email: string, remember: boolean) {
  try {
    if (remember) window.localStorage.setItem(REMEMBER_KEY, email)
    else window.localStorage.removeItem(REMEMBER_KEY)
  } catch {
    // El almacenamiento local puede no estar disponible; el acceso sigue funcionando.
  }
}

function nameFromEmail(email: string) {
  return email.split('@')[0].replace(/[._-]+/g, ' ').trim() || 'Residente'
}

// Confeti por el 1.er lugar en el II Reto Emprende 2026. Decorativo: no recibe clics ni lo anuncian los
// lectores de pantalla, y se apaga con prefers-reduced-motion (index.css).
function Confeti({ piezas = 70 }: { piezas?: number }) {
  const [lista] = useState(() =>
    Array.from({ length: piezas }, (_, id) => ({
      id,
      izquierda: Math.random() * 100,
      color: [t.coral, '#e8b84b', t.white, '#9dbbac', t.forestDeep][id % 5],
      ancho: 5 + Math.random() * 5,
      alto: 9 + Math.random() * 8,
      duracion: 4.5 + Math.random() * 5,
      retraso: -Math.random() * 9,
      deriva: `${Math.round(Math.random() * 160 - 80)}px`,
      giro: `${Math.round(360 + Math.random() * 720)}deg`,
    })),
  )
  return (
    <div aria-hidden="true" className="pointer-events-none absolute inset-0 overflow-hidden">
      {lista.map((p) => (
        <span
          className="confeti-pieza"
          key={p.id}
          style={{ left: `${p.izquierda}%`, width: p.ancho, height: p.alto, background: p.color, ['--duracion' as string]: `${p.duracion}s`, ['--retraso' as string]: `${p.retraso}s`, ['--deriva' as string]: p.deriva, ['--giro' as string]: p.giro }}
        />
      ))}
    </div>
  )
}

export function LoginScreen({ onLogin }: LoginScreenProps) {
  const [mode, setMode] = useState<Mode>('login')
  const [name, setName] = useState('')
  const [email, setEmail] = useState(() => rememberedEmail())
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [remember, setRemember] = useState(() => rememberedEmail() !== '')
  const [error, setError] = useState('')

  const clearError = () => {
    if (error) setError('')
  }

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (mode === 'register' && name.trim().length < 2) {
      setError('Escribe tu nombre para crear la cuenta.')
      return
    }
    if (!email.trim() || !email.includes('@')) {
      setError('Escribe un correo válido, por ejemplo mariela@correo.com.')
      return
    }
    if (!password) {
      setError('Escribe tu contraseña. En esta demostración cualquiera es válida.')
      return
    }
    persistEmail(email.trim(), remember)
    onLogin({ name: mode === 'register' ? name.trim() : nameFromEmail(email), role: 'resident' })
  }

  return (
    <div className="@container">
      <main className="relative flex min-h-svh flex-col *:min-w-0 @3xl:flex-row" style={{ background: t.forest, color: t.white, fontFamily: sans }}>
        <Confeti />
        <section className="relative flex min-h-[26svh] flex-col justify-between overflow-hidden px-6 pb-10 pt-6 @3xl:min-h-0 @3xl:flex-1 @3xl:px-14 @3xl:py-12">
          <img alt="" aria-hidden="true" className="pointer-events-none absolute inset-0 size-full object-cover" src="/parque-andres-bello.jpg" style={{ opacity: 0.32, mixBlendMode: 'luminosity' }} />
          <div aria-hidden="true" className="pointer-events-none absolute inset-0" style={{ background: `linear-gradient(180deg, rgba(47,93,80,0.25) 0%, rgba(47,93,80,0.55) 55%, ${t.forest} 100%)` }} />
          <div className="relative flex items-center gap-3">
            <span className="grid size-14 shrink-0 place-items-center overflow-hidden rounded-full border" style={{ borderColor: 'rgba(255,253,248,0.35)', background: 'rgba(255,253,248,0.08)' }}>
              <img alt="Logo de la Junta de Desarrollo Local de El Cangrejo" className="size-full rounded-full object-cover" src="/logo-micangrejo.jpg" />
            </span>
            <div className="min-w-0 flex-1">
              <p className="truncate text-[15px] font-semibold">miCangrejo</p>
              <p className="truncate text-xs" style={{ color: 'rgba(255,253,248,0.7)' }}>
                Junta de Desarrollo Local · El Cangrejo
              </p>
            </div>
            <Marginalia className="hidden shrink-0 whitespace-nowrap text-right @5xl:block" color="rgba(255,253,248,0.55)">
              {placeMark}
            </Marginalia>
          </div>

          <div className="relative mt-6 @3xl:mt-0">
            <div className="mb-4 inline-flex items-center gap-2.5 rounded-full border py-1.5 pl-2 pr-4 @3xl:mb-6" style={{ borderColor: 'rgba(232,184,75,0.55)', background: 'rgba(232,184,75,0.14)' }}>
              <span className="medalla-premio grid size-8 shrink-0 place-items-center rounded-full" style={{ background: '#e8b84b', color: t.forestDeep }}>
                <Medal aria-hidden="true" size={18} />
              </span>
              <span className="min-w-0">
                <span className="block text-[14px] font-semibold leading-tight @3xl:text-[15px]">1.er lugar</span>
                <span className="block text-[11px] leading-tight @3xl:text-xs" style={{ color: 'rgba(255,253,248,0.78)' }}>
                  II Reto Emprende 2026 · CONTECS · UTP
                </span>
              </span>
            </div>
            <h1 className="max-w-none text-[31px] font-medium leading-[1.05] tracking-[-0.02em] text-balance @3xl:max-w-[12ch] @3xl:text-[76px] @3xl:leading-[1]" style={{ fontFamily: serif }}>
              Una solución tecnológica
            </h1>
            <p className="mt-4 hidden max-w-sm text-[14px] leading-6 @3xl:mt-6 @3xl:block" style={{ color: 'rgba(255,253,248,0.72)' }}>
              Reporta, sigue tu caso en cada entidad y consulta la guía de Vía Argentina en un solo lugar.
            </p>
          </div>

          <div className="relative mt-8 hidden flex-wrap items-end gap-x-4 gap-y-2 @3xl:flex" style={{ color: 'rgba(255,253,248,0.5)' }}>
            <RulerTicks className="shrink-0" width={96} />
            <Marginalia className="whitespace-nowrap" color="rgba(255,253,248,0.55)">
              Registro de acceso · {todayMark()}
            </Marginalia>
          </div>
        </section>

        <section className="relative z-10 -mt-6 flex flex-1 flex-col rounded-t-[32px] px-5 pb-6 pt-5 @3xl:z-auto @3xl:mt-0 @3xl:max-w-[540px] @3xl:justify-start @3xl:rounded-none @3xl:px-12 @3xl:pb-10 @3xl:pt-[14svh]" style={{ background: t.paper, color: t.ink }}>
          {/* Selector de rol: la única forma de entrar mientras CU-07 (inicio de sesión) no esté implementado. */}
          <div className="flex items-center gap-3">
            <span className="h-px flex-1" style={{ background: t.rule }} />
            <Marginalia>Entra como</Marginalia>
            <span className="h-px flex-1" style={{ background: t.rule }} />
          </div>

          <div className="mt-3 grid grid-cols-2 gap-3 @3xl:mt-4">
            <AltEntry className="col-span-2" icon={House} label="Residente" onClick={() => onLogin({ name: 'Residente', role: 'resident' })} primary />
            <AltEntry icon={Compass} label="Visitante" onClick={() => onLogin({ name: 'Visitante', role: 'visitor' })} />
            <AltEntry icon={ShieldCheck} label="Administrativo" onClick={() => onLogin({ name: 'Administración JDL', role: 'admin' })} />
          </div>

          <div className="mb-3 mt-5 flex items-center gap-3 @3xl:mb-4 @3xl:mt-7">
            <span className="h-px flex-1" style={{ background: t.rule }} />
            <Marginalia>Con correo y contraseña</Marginalia>
            <span className="h-px flex-1" style={{ background: t.rule }} />
          </div>

          <FueraDeAlcance clave="iniciarSesion">
          <div className="grid grid-cols-2 rounded-full p-1" role="tablist" aria-label="Ingresar o registrarme" style={{ background: t.paper2 }}>
            {(
              [
                ['login', 'Ingresar'],
                ['register', 'Registrarme'],
              ] as const
            ).map(([value, label]) => {
              const selected = mode === value
              return (
                <button
                  aria-selected={selected}
                  className="h-11 rounded-full text-[15px] font-semibold transition @3xl:h-12"
                  key={value}
                  onClick={() => {
                    setMode(value)
                    clearError()
                  }}
                  role="tab"
                  style={selected ? { background: t.white, color: t.ink, boxShadow: '0 6px 16px -10px rgba(30,45,38,.45)' } : { color: t.muted }}
                  type="button"
                >
                  {label}
                </button>
              )
            })}
          </div>

          <form className="mt-4 grid gap-2.5 @3xl:mt-6 @3xl:gap-3" noValidate onSubmit={handleSubmit}>
            <IconField icon={Mail} label="Correo electrónico">
              <input aria-invalid={Boolean(error)} autoComplete="email" className="w-full bg-transparent text-[16px] outline-none" onChange={(e) => { setEmail(e.target.value); clearError() }} placeholder="tu.nombre@correo.com" style={{ color: t.ink }} type="email" value={email} />
            </IconField>
            <IconField
              icon={Lock}
              label="Contraseña"
              trailing={
                <button aria-label={showPassword ? 'Ocultar contraseña' : 'Mostrar contraseña'} aria-pressed={showPassword} className="grid size-10 place-items-center rounded-full transition hover:bg-black/5" onClick={() => setShowPassword((v) => !v)} style={{ color: t.forest }} type="button">
                  {showPassword ? <EyeOff size={20} /> : <Eye size={20} />}
                </button>
              }
            >
              <input autoComplete={mode === 'register' ? 'new-password' : 'current-password'} className="w-full bg-transparent text-[16px] outline-none" onChange={(e) => { setPassword(e.target.value); clearError() }} placeholder="Tu contraseña" style={{ color: t.ink }} type={showPassword ? 'text' : 'password'} value={password} />
            </IconField>

            {/* El nombre se despliega debajo al elegir Registrarme; correo y contraseña no se mueven. */}
            <div aria-hidden={mode !== 'register'} className="-mt-2.5 grid transition-[grid-template-rows] duration-200 ease-out @3xl:-mt-3" style={{ gridTemplateRows: mode === 'register' ? '1fr' : '0fr' }}>
              <div className="min-h-0 overflow-hidden">
                <div className="pt-2.5 @3xl:pt-3">
                  <IconField icon={User} label="Nombre">
                    <input autoComplete="name" className="w-full bg-transparent text-[16px] outline-none" onChange={(e) => { setName(e.target.value); clearError() }} placeholder="Tu nombre" style={{ color: t.ink }} tabIndex={mode === 'register' ? 0 : -1} type="text" value={name} />
                  </IconField>
                </div>
              </div>
            </div>

            {error && (
              <p className="text-[13px] font-medium" role="alert" style={{ color: t.coral }}>
                {error}
              </p>
            )}

            <div className="mt-1 flex items-center justify-between gap-3">
              <label className="inline-flex cursor-pointer items-center gap-2.5 text-[14px]">
                <input checked={remember} className="peer sr-only" onChange={(e) => setRemember(e.target.checked)} type="checkbox" />
                <span aria-hidden="true" className="grid size-5 place-items-center rounded-[5px] border-[1.5px] transition peer-checked:[&>svg]:opacity-100 peer-focus-visible:shadow-[0_0_0_3px_rgba(47,93,80,0.25)]" style={{ borderColor: remember ? t.forest : t.rule, background: remember ? t.forest : t.white }}>
                  <svg className="opacity-0" fill="none" height="12" stroke={t.white} strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" viewBox="0 0 12 12" width="12">
                    <path d="M2.5 6.5 5 9l4.5-6" />
                  </svg>
                </span>
                Recordarme
              </label>
              <button className="text-[14px] font-semibold" onClick={() => setError('La recuperación de contraseña llegará con las cuentas reales. En la demostración, cualquier contraseña es válida.')} style={{ color: t.forest }} type="button">
                ¿Olvidaste tu contraseña?
              </button>
            </div>

            <button className="mt-2 inline-flex h-[52px] w-full items-center justify-center gap-2 rounded-full text-[16px] font-semibold @3xl:mt-3 @3xl:h-14 transition hover:brightness-95 focus-visible:outline-2 focus-visible:outline-offset-2" style={{ background: t.coral, color: t.white, outlineColor: t.coral }} type="submit">
              {mode === 'login' ? 'Ingresar' : 'Crear cuenta'} <ArrowRight size={18} />
            </button>
          </form>
          </FueraDeAlcance>

          <p className="mt-auto pt-6 text-center text-[11px] leading-4 [@media(max-height:780px)]:hidden @3xl:mt-6 @3xl:block @3xl:pt-0" style={{ color: t.muted }}>
            Acceso de demostración por rol. El inicio de sesión con credenciales (CU-07, ADR-06) no está implementado en la Fase 3.
          </p>
        </section>
      </main>
    </div>
  )
}

function IconField({ icon: Icon, label, children, trailing }: { icon: LucideIcon; label: string; children: ReactNode; trailing?: ReactNode }) {
  return (
    <label className="flex items-center gap-4 rounded-2xl border px-4 py-2.5 transition @3xl:py-3 focus-within:border-[color:var(--forest)] focus-within:shadow-[0_0_0_3px_rgba(47,93,80,0.16)]" style={{ background: t.white, borderColor: t.rule, ['--forest' as string]: t.forest }}>
      <Icon className="shrink-0" size={22} strokeWidth={1.8} style={{ color: t.forest }} />
      <span className="min-w-0 flex-1">
        <Marginalia className="block">{label}</Marginalia>
        <span className="mt-1 block">{children}</span>
      </span>
      {trailing}
    </label>
  )
}

function AltEntry({ icon: Icon, label, onClick, primary = false, className = '' }: { icon: LucideIcon; label: string; onClick: () => void; primary?: boolean; className?: string }) {
  return (
    <button className={`inline-flex h-12 items-center justify-center gap-2 rounded-full border text-[15px] font-semibold transition @3xl:h-14 focus-visible:outline-2 focus-visible:outline-offset-2 ${primary ? 'hover:brightness-95' : 'hover:bg-white'} ${className}`} onClick={onClick} style={primary ? { background: t.forest, borderColor: t.forest, color: t.white, outlineColor: t.forest } : { background: t.white, borderColor: t.rule, color: t.ink, outlineColor: t.forest }} type="button">
      <Icon size={20} strokeWidth={1.9} style={{ color: primary ? t.white : t.forest }} /> {label}
    </button>
  )
}
