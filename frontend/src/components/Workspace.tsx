import { useState } from 'react'
import type { LucideIcon } from 'lucide-react'
import { BarChart3, Bell, ChevronRight, ClipboardList, Database, FilePlus2, HeartHandshake, Home, LogOut, Map, MapPin, Menu, Send, ShieldCheck, UtensilsCrossed, X } from 'lucide-react'

import { estaImplementado, etiquetaAlcance, type ClaveAlcance } from '@/alcance'
import type { AppSession, UserRole } from '@/components/LoginScreen'
import { AdminDashboard, AdminReports, AdminSummary } from '@/components/AdminReports'
import { DatabasePage } from '@/components/DatabasePage'
import { BannerAlcance, FueraDeAlcance } from '@/components/FueraDeAlcance'
import { MyReports } from '@/components/MyReports'
import { ReportForm } from '@/components/ReportForm'
import { RestaurantMap } from '@/components/RestaurantMap'
import { WasteMap } from '@/components/WasteMap'
import { Button, Marginalia, RulerTicks, mono, placeMark, sans, serif, t, todayMark } from '@/design/tokens'
import { Ficha, FichaHeader, PageIntro } from '@/design/ui'

type WorkspaceProps = {
  session: AppSession
  onLogout: () => void
}

type PageId = 'home' | 'dashboard' | 'reports' | 'waste-map' | 'restaurants' | 'notion' | 'new-report' | 'my-reports' | 'telegram' | 'voluntariado'

type NavItem = {
  id: PageId
  label: string
  icon: LucideIcon
  /** Ítem visible pero no navegable (por ejemplo, un canal que aún no está disponible). */
  disabled?: boolean
  /** Pastilla en marginalia junto a la etiqueta, por ejemplo "Próximamente". */
  badge?: string
  /** Caso de uso que pinta la pantalla; si no está implementado, el ítem se atenúa pero sigue navegable. */
  alcance?: ClaveAlcance
}

const navigationByRole: Record<UserRole, NavItem[]> = {
  admin: [
    // El Inicio de la JDL muestra el resumen de indicadores (CU-06).
    { id: 'home', label: 'Inicio', icon: Home, alcance: 'tablero' },
    { id: 'dashboard', label: 'Tablero', icon: BarChart3, alcance: 'tablero' },
    { id: 'new-report', label: 'Enviar reporte', icon: FilePlus2, alcance: 'registrarReporte' },
    { id: 'reports', label: 'Expedientes', icon: ClipboardList, alcance: 'validarYEnviar' },
    { id: 'waste-map', label: 'Mapa de basureros', icon: Map, alcance: 'basureros' },
    { id: 'restaurants', label: 'Mapa de restaurantes', icon: UtensilsCrossed, alcance: 'restaurantes' },
    { id: 'notion', label: 'Base de datos', icon: Database, alcance: 'baseDeDatos' },
  ],
  resident: [
    { id: 'home', label: 'Inicio', icon: Home },
    { id: 'new-report', label: 'Crear reporte', icon: FilePlus2, alcance: 'registrarReporte' },
    { id: 'telegram', label: 'Telegram', icon: Send, alcance: 'telegram' },
    { id: 'my-reports', label: 'Mis reportes', icon: ClipboardList, alcance: 'consultarFolio' },
    { id: 'waste-map', label: 'Mapa de basureros', icon: Map, alcance: 'basureros' },
    { id: 'restaurants', label: 'Mapa de restaurantes', icon: UtensilsCrossed, alcance: 'restaurantes' },
    { id: 'voluntariado', label: 'Voluntariado', icon: HeartHandshake, disabled: true, badge: 'Próximamente' },
  ],
  visitor: [
    { id: 'home', label: 'Inicio', icon: Home },
    { id: 'restaurants', label: 'Mapa de restaurantes', icon: UtensilsCrossed },
  ],
}

const roleLabels: Record<UserRole, string> = {
  admin: 'Administrador JDL',
  resident: 'Residente',
  visitor: 'Visitante',
}

const pageTitles: Record<PageId, string> = {
  home: 'Inicio',
  dashboard: 'Tablero de cumplimiento',
  reports: 'Expedientes vecinales',
  'waste-map': 'Mapa de basureros',
  restaurants: 'Mapa de restaurantes',
  notion: 'Base de datos · Supabase',
  'new-report': 'Crear un reporte',
  'my-reports': 'Mis reportes',
  telegram: 'Telegram',
  voluntariado: 'Voluntariado',
}

export function Workspace({ session, onLogout }: WorkspaceProps) {
  const [activePage, setActivePage] = useState<PageId>('home')
  const [sidebarOpen, setSidebarOpen] = useState(false)
  // Expediente que el Inicio pidió abrir; lo recoge la pantalla de expedientes.
  const [reportToOpen, setReportToOpen] = useState<number | null>(null)
  const navigation = navigationByRole[session.role]

  const navigate = (page: PageId) => {
    setActivePage(page)
    setSidebarOpen(false)
  }

  const openReport = (id: number) => {
    setReportToOpen(id)
    navigate('reports')
  }

  if (session.role === 'visitor') return <VisitorWorkspace onLogout={onLogout} />

  return (
    <div className="min-h-svh" style={{ background: t.paper, color: t.ink, fontFamily: sans }}>
      <div className={`fixed inset-0 z-30 transition lg:hidden ${sidebarOpen ? 'opacity-100' : 'pointer-events-none opacity-0'}`} onClick={() => setSidebarOpen(false)} style={{ background: 'rgba(30,45,38,0.45)' }} />

      <aside className={`fixed inset-y-0 left-0 z-40 flex w-72 flex-col border-r px-4 py-5 transition-transform lg:translate-x-0 ${sidebarOpen ? 'translate-x-0' : '-translate-x-full'}`} style={{ background: t.white, borderColor: t.rule }}>
        <div className="flex items-center justify-between px-2">
          <div className="flex items-center gap-3">
            <img alt="Logo de la Junta de Desarrollo Local de El Cangrejo" className="size-10 rounded-full object-cover" src="/logo-micangrejo.jpg" />
            <div>
              <p className="text-[15px] font-semibold leading-tight">miCangrejo</p>
              <Marginalia className="block">JDL · El Cangrejo</Marginalia>
            </div>
          </div>
          <button aria-label="Cerrar menú" className="rounded-lg p-2 transition hover:bg-black/5 lg:hidden" onClick={() => setSidebarOpen(false)} type="button">
            <X size={19} />
          </button>
        </div>

        <nav aria-label="Navegación" className="mt-8 grid gap-1 px-1">
          {navigation.map((item, index) => {
            const Icon = item.icon
            const selected = item.id === activePage
            const number = String(index + 1).padStart(2, '0')
            if (item.disabled) {
              return (
                <button
                  aria-disabled="true"
                  className="flex cursor-not-allowed items-center gap-3 rounded-lg px-3 py-2.5 text-left text-[14px] font-medium"
                  key={item.id}
                  style={{ color: t.ink, opacity: 0.45 }}
                  tabIndex={-1}
                  title={item.badge ? `${item.label} · ${item.badge}` : item.label}
                  type="button"
                >
                  <span className="w-5 text-[10px] tabular-nums tracking-[.1em]" style={{ fontFamily: 'ui-monospace, monospace', color: t.muted }}>
                    {number}
                  </span>
                  <Icon size={17} />
                  {item.label}
                  {item.badge && (
                    <span className="ml-auto shrink-0 whitespace-nowrap rounded-[4px] border px-1 py-0.5" style={{ fontFamily: mono, fontSize: '9px', letterSpacing: '.06em', textTransform: 'uppercase', color: t.muted, borderColor: t.rule }}>
                      {item.badge}
                    </span>
                  )}
                </button>
              )
            }
            // Fuera de alcance: se atenúa, pero se puede abrir para ver por qué está inactivo.
            const fueraDeAlcance = item.alcance !== undefined && !estaImplementado(item.alcance)
            const etiqueta = item.alcance && fueraDeAlcance ? etiquetaAlcance(item.alcance) : undefined
            return (
              <button
                aria-current={selected ? 'page' : undefined}
                className="flex items-center gap-3 rounded-lg px-3 py-2.5 text-left text-[14px] font-medium transition"
                key={item.id}
                onClick={() => navigate(item.id)}
                style={{ ...(selected ? { background: t.forest, color: t.white } : { color: t.ink }), ...(fueraDeAlcance ? { opacity: 0.45, filter: 'grayscale(1)' } : {}) }}
                title={etiqueta ? `${item.label} · ${etiqueta}` : undefined}
                type="button"
              >
                <span className="w-5 text-[10px] tabular-nums tracking-[.1em]" style={{ fontFamily: 'ui-monospace, monospace', color: selected ? 'rgba(255,253,248,0.7)' : t.muted }}>
                  {number}
                </span>
                <Icon size={17} />
                {item.label}
                {etiqueta && (
                  <span className="ml-auto shrink-0 whitespace-nowrap rounded-[4px] border px-1 py-0.5" style={{ fontFamily: mono, fontSize: '9px', letterSpacing: '.06em', textTransform: 'uppercase', color: selected ? t.white : t.muted, borderColor: selected ? 'rgba(255,253,248,0.5)' : t.rule }}>
                    <span aria-hidden="true">Fuera</span>
                    <span className="sr-only">{etiqueta}</span>
                  </span>
                )}
              </button>
            )
          })}
        </nav>

        <div className="mt-auto rounded-xl border p-2" style={{ background: t.paper, borderColor: t.rule }}>
          <Marginalia className="block px-2 pt-1">Sesión · {roleLabels[session.role]}</Marginalia>
          <button className="mt-1 flex w-full items-center gap-2 rounded-lg px-2 py-2 text-[13px] font-semibold transition hover:bg-black/5" onClick={onLogout} style={{ color: t.forest }} type="button">
            <LogOut size={15} /> Cerrar sesión
          </button>
        </div>
      </aside>

      <div className="lg:pl-72">
        <BannerAlcance />
        <header className="sticky top-0 z-20 flex h-16 items-center justify-between border-b px-4 sm:px-7" style={{ background: 'rgba(245,240,230,0.92)', borderColor: t.rule, backdropFilter: 'blur(8px)' }}>
          <div className="flex min-w-0 items-center gap-3">
            <button aria-label="Abrir menú" className="rounded-lg p-2 transition hover:bg-black/5 lg:hidden" onClick={() => setSidebarOpen(true)} type="button">
              <Menu size={21} />
            </button>
            <div className="min-w-0">
              <Marginalia className="block">{roleLabels[session.role]}</Marginalia>
              <h1 className="truncate text-[18px] font-medium leading-tight" style={{ fontFamily: serif }}>
                {pageTitles[activePage]}
              </h1>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Marginalia className="hidden md:block">{todayMark()}</Marginalia>
            <button aria-label="Notificaciones" className="relative grid size-10 place-items-center rounded-lg transition hover:bg-black/5" type="button">
              <Bell size={19} />
              <span className="absolute right-2.5 top-2.5 size-1.5 rounded-full" style={{ background: t.coral }} />
            </button>
            <div className="ml-1 flex items-center gap-2.5 border-l pl-3" style={{ borderColor: t.rule }} title={`${session.name} · ${roleLabels[session.role]}`}>
              <span aria-hidden="true" className="grid size-9 place-items-center rounded-full text-sm font-bold" style={{ background: t.forest, color: t.white }}>
                {session.name.slice(0, 1).toUpperCase()}
              </span>
              <div className="hidden min-w-0 md:block">
                <p className="max-w-40 truncate text-[13px] font-semibold leading-tight">{session.name}</p>
                <Marginalia className="block truncate">{roleLabels[session.role]}</Marginalia>
              </div>
            </div>
          </div>
        </header>

        <main className="mx-auto w-full max-w-7xl p-4 sm:p-7">
          {activePage === 'home' && <HomePage name={session.name} onNavigate={navigate} onOpenReport={openReport} role={session.role} />}
          {activePage === 'dashboard' && <DashboardPage />}
          {activePage === 'reports' && <ReportsPage openReportId={reportToOpen} />}
          {activePage === 'waste-map' && <WasteSitesPage />}
          {activePage === 'restaurants' && <RestaurantsPage />}
          {activePage === 'notion' && (
            <FueraDeAlcance clave="baseDeDatos">
              <DatabasePage />
            </FueraDeAlcance>
          )}
          {activePage === 'new-report' && (
            <section className="mx-auto max-w-lg space-y-6">
              <PageIntro description="Describe el problema, agrega evidencia y ubícalo para que la JDL pueda darle seguimiento." marginalia="Reportes comunitarios" title="Envía un reporte" />
              <ReportForm />
            </section>
          )}
          {activePage === 'my-reports' && <MyReportsPage onNavigate={navigate} />}
          {activePage === 'telegram' && <TelegramPage />}
        </main>

        <footer className="mx-auto flex w-full max-w-7xl flex-wrap items-center gap-x-4 gap-y-2 px-4 pb-8 sm:px-7" style={{ color: t.muted }}>
          <RulerTicks width={96} />
          <Marginalia>{placeMark}</Marginalia>
          <Marginalia className="ml-auto">Junta de Desarrollo Local · Junta Comunal de Bella Vista</Marginalia>
        </footer>
      </div>
    </div>
  )
}

// Visitantes: solo la guía de restaurantes. Sin barra lateral, sin cuenta, sin notificaciones.
function VisitorWorkspace({ onLogout }: { onLogout: () => void }) {
  return (
    <div className="flex min-h-svh flex-col" style={{ background: t.paper, color: t.ink, fontFamily: sans }}>
      <BannerAlcance />
      <header className="sticky top-0 z-20 flex h-16 items-center justify-between border-b px-4 sm:px-7" style={{ background: 'rgba(245,240,230,0.92)', borderColor: t.rule, backdropFilter: 'blur(8px)' }}>
        <div className="flex items-center gap-3">
          <img alt="Logo de la Junta de Desarrollo Local de El Cangrejo" className="size-9 rounded-full object-cover" src="/logo-micangrejo.jpg" />
          <div>
            <p className="text-[15px] font-semibold leading-tight">miCangrejo</p>
            <Marginalia className="block">Vía Argentina · El Cangrejo</Marginalia>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <Marginalia className="hidden md:block">{todayMark()}</Marginalia>
          <Button onClick={onLogout} size="sm" tone="outline">
            Salir
          </Button>
        </div>
      </header>

      <main className="mx-auto w-full max-w-7xl flex-1 p-4 sm:p-7">
        <section className="space-y-6">
          <PageIntro description="Selecciona un marcador para ver los datos de cada restaurante." marginalia="Guía de visitantes" title="Restaurantes de El Cangrejo" />
          <FueraDeAlcance clave="restaurantes">
            <Ficha className="overflow-hidden" padded={false}>
              <RestaurantMap />
            </Ficha>
          </FueraDeAlcance>
        </section>
      </main>

      <footer className="mx-auto flex w-full max-w-7xl flex-wrap items-center gap-x-4 gap-y-2 px-4 pb-8 sm:px-7" style={{ color: t.muted }}>
        <RulerTicks width={96} />
        <Marginalia>{placeMark}</Marginalia>
        <Marginalia className="ml-auto">Junta de Desarrollo Local · Junta Comunal de Bella Vista</Marginalia>
      </footer>
    </div>
  )
}

function greetingFor(name: string) {
  return name.charAt(0).toUpperCase() + name.slice(1)
}

function HomePage({ role, name, onNavigate, onOpenReport }: { role: UserRole; name: string; onNavigate: (page: PageId) => void; onOpenReport: (id: number) => void }) {
  const greeting = greetingFor(name)

  if (role === 'admin') {
    return (
      <section className="space-y-6">
        <PageIntro marginalia={`Panel de la JDL · ${todayMark()}`} title={`Buenos días, ${greeting}.`} />
        <FueraDeAlcance clave="tablero">
          <AdminSummary onOpenReport={onOpenReport} />
        </FueraDeAlcance>
      </section>
    )
  }

  if (role === 'resident') {
    return (
      <section className="space-y-6">
        <PageIntro description="Cada reporte se convierte en un expediente con responsable, estado y fecha." marginalia={`miCangrejo · ${todayMark()}`} marginaliaExact title={`Hola, ${greeting}.`} />
        <div className="grid gap-4 md:grid-cols-3">
          <ActionCard action="Reportar ahora" description="Registra una incidencia con descripción, ubicación y evidencia." icon={FilePlus2} onClick={() => onNavigate('new-report')} title="Crear un reporte" />
          <FueraDeAlcance clave="consultarFolio">
            <ActionCard action="Ver mis reportes" description="Revisa tus folios y el recorrido de cada caso por entidad." icon={ClipboardList} onClick={() => onNavigate('my-reports')} title="Consultar mis reportes" />
          </FueraDeAlcance>
          <FueraDeAlcance clave="basureros">
            <ActionCard action="Abrir mapa de basureros" description="Ubica los puntos comunitarios de residuos y la guía de Vía Argentina." icon={Map} onClick={() => onNavigate('waste-map')} title="Ver mapas del barrio" />
          </FueraDeAlcance>
        </div>
        <Ficha className="flex gap-4">
          <span className="grid size-10 shrink-0 place-items-center rounded-lg" style={{ background: t.paper2, color: t.coral }}>
            <ShieldCheck size={20} />
          </span>
          <div>
            <h2 className="text-[20px] font-medium leading-tight" style={{ fontFamily: serif }}>
              ¿Tienes una emergencia?
            </h2>
            <p className="mt-1 text-[14px] leading-6" style={{ color: t.muted }}>
              Comunícate primero con los servicios de emergencia. Esta plataforma da seguimiento comunitario, pero no reemplaza una atención urgente.
            </p>
          </div>
        </Ficha>
      </section>
    )
  }

  return (
    <section className="space-y-6">
      <PageIntro description="Explora la oferta gastronómica de El Cangrejo y encuentra tu próxima parada." marginalia="Vía Argentina" title={`Bienvenido, ${greeting}.`} />
      <RestaurantsPage compact />
    </section>
  )
}

const TELEGRAM_BOT_URL = 'https://t.me/MiCangrejoBot'

function TelegramPage() {
  const pasos = [
    ['01', 'Escribe lo que sucede', 'Por ejemplo: "Hay basura acumulada frente al parque Andrés Bello".'],
    ['02', 'Comparte tu ubicación', 'Con el clip de Telegram, para que el caso llegue con coordenadas.'],
    ['03', 'Recibe tu folio', 'El bot responde con el folio y la categoría que asignó la clasificación automática.'],
  ]
  return (
    <section className="space-y-6">
      <PageIntro
        description="Reporta desde el chat, sin instalar nada más. El caso entra al mismo expediente que el formulario web."
        marginalia="Canal activo"
        title="Reporta por Telegram"
      />
      <FueraDeAlcance clave="telegram">
      <Ficha className="space-y-5">
        <div className="flex flex-wrap items-center gap-3">
          <span className="grid size-11 shrink-0 place-items-center rounded-lg" style={{ background: t.paper2, color: t.forest }}>
            <Send size={20} />
          </span>
          <div className="min-w-0">
            <p className="text-[20px] font-medium leading-tight" style={{ fontFamily: serif }}>@MiCangrejoBot</p>
            <Marginalia className="block">Bot oficial de la JDL de El Cangrejo</Marginalia>
          </div>
          <a
            className="ml-auto inline-flex h-11 items-center justify-center rounded-full px-5 text-[15px] font-semibold transition"
            href={TELEGRAM_BOT_URL}
            rel="noopener noreferrer"
            style={{ background: t.forest, color: t.white }}
            target="_blank"
          >
            Abrir en Telegram
          </a>
        </div>
        <div className="grid gap-4 border-t pt-5 md:grid-cols-3" style={{ borderColor: t.rule }}>
          {pasos.map(([numero, titulo, detalle]) => (
            <div key={numero}>
              <Marginalia className="block" color={t.coral}>{numero}</Marginalia>
              <p className="mt-1 text-[16px] font-medium">{titulo}</p>
              <p className="mt-1 text-[14px] leading-6" style={{ color: t.muted }}>{detalle}</p>
            </div>
          ))}
        </div>
        <p className="border-t pt-4 text-[14px] leading-6" style={{ borderColor: t.rule, color: t.muted }}>
          ¿Ya tienes un folio? Escríbele al bot <strong style={{ color: t.ink }}>estado MC-2026-0001</strong> y te
          responde en qué estado está el expediente.
        </p>
      </Ficha>
      </FueraDeAlcance>
    </section>
  )
}

function DashboardPage() {
  return (
    <section className="space-y-6">
      <PageIntro description="Indicadores reales para priorizar la atención y presentar avances ante las entidades." marginalia="Administrador JDL" title="Tablero de cumplimiento" />
      <FueraDeAlcance clave="tablero">
        <AdminDashboard />
      </FueraDeAlcance>
    </section>
  )
}

function ReportsPage({ openReportId }: { openReportId: number | null }) {
  return (
    <section className="space-y-6">
      <PageIntro description="Revisa, valida, envía y da seguimiento a cada expediente por entidad." marginalia="Administrador JDL" title="Expedientes vecinales" />
      <AdminReports openReportId={openReportId} />
    </section>
  )
}

function MyReportsPage({ onNavigate }: { onNavigate: (page: PageId) => void }) {
  return (
    <section className="space-y-6">
      <PageIntro description="Consulta el estado, las entidades responsables y el historial real de tus casos." marginalia="Residentes" title="Mis reportes" />
      <FueraDeAlcance clave="consultarFolio">
        <MyReports onCreateReport={() => onNavigate('new-report')} />
      </FueraDeAlcance>
    </section>
  )
}

function RestaurantsPage({ compact = false }: { compact?: boolean }) {
  return (
    <section className="space-y-6">
      {!compact && <PageIntro description="Explora los locales de la lista gastronómica compartida. Selecciona un marcador para consultar sus datos." marginalia="Visitantes y JDL" title="Mapa de restaurantes" />}
      <FueraDeAlcance clave="restaurantes">
        <Ficha className="overflow-hidden" padded={false}>
          <FichaHeader className="border-b px-5 py-4" description="Cada marcador abre la información disponible del restaurante." icon={UtensilsCrossed} title="Guía gastronómica de El Cangrejo" />
          <RestaurantMap compact={compact} />
        </Ficha>
      </FueraDeAlcance>
    </section>
  )
}

function WasteSitesPage() {
  return (
    <section className="space-y-6">
      <PageIntro description="Puntos comunitarios registrados para apoyar la identificación y gestión de residuos en El Cangrejo." marginalia="Mapa interactivo" title="Mapa de basureros y tinacos" />
      <FueraDeAlcance clave="basureros">
        <Ficha className="overflow-hidden" padded={false}>
          <FichaHeader className="border-b px-5 py-4" description="Datos cargados desde la API de miCangrejo." icon={MapPin} title="Puntos comunitarios" />
          <WasteMap />
        </Ficha>
      </FueraDeAlcance>
    </section>
  )
}

function ActionCard({ icon: Icon, title, description, action, onClick }: { icon: LucideIcon; title: string; description: string; action: string; onClick: () => void }) {
  return (
    <Ficha>
      <span className="grid size-10 place-items-center rounded-lg" style={{ background: t.paper2, color: t.forest }}>
        <Icon size={20} />
      </span>
      <h2 className="mt-4 text-[22px] font-medium leading-tight" style={{ fontFamily: serif }}>
        {title}
      </h2>
      <p className="mt-2 text-[14px] leading-6" style={{ color: t.muted }}>
        {description}
      </p>
      <button className="mt-4 inline-flex items-center gap-1.5 text-[14px] font-semibold" onClick={onClick} style={{ color: t.forest }} type="button">
        {action} <ChevronRight size={16} />
      </button>
    </Ficha>
  )
}
