import { useCallback, useEffect, useState } from "react"
import type { FormEvent } from "react"
import { ChevronRight, ClipboardList, Download, LoaderCircle, Mail, RefreshCw, ShieldCheck, Sparkles } from "lucide-react"

import {
  ApiError,
  deriveParticipation,
  getAdminCategories,
  getAdminEntities,
  getAdminReport,
  getAdminReports,
  getAdminStats,
  patchAdminReport,
  reclassifyAdminReport,
  sendReportToEntities,
  updateParticipation,
  type AdminStats,
  type EntityCatalogItem,
  type Participation,
  type ParticipationStatus,
  type Report,
  type ReportSummary,
} from "@/services/api"
import { downloadReportPdf } from "@/lib/reportPdf"
import { Button, Marginalia, Tag, inputSmClass, inputStyle, mono, serif, t, textareaClass } from "@/design/tokens"
import { CaseStamp, CaseTag, EmptyState, ErrorState, Ficha, FichaHeader, Folio, Info, LoadingState, Metric, Notice, SectionTitle, participationTone } from "@/design/ui"

/** Inicio de la JDL: qué necesita atención hoy. Una sola consulta de estadísticas por pantalla. */
export function AdminSummary({ onOpenReport }: { onOpenReport: (id: number) => void }) {
  const [stats, setStats] = useState<AdminStats | null>(null)
  const [pending, setPending] = useState<ReportSummary[]>([])
  const [pendingTotal, setPendingTotal] = useState(0)
  const [error, setError] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  const load = useCallback(async () => {
    setIsLoading(true)
    setError(null)
    try {
      const [summary, page] = await Promise.all([getAdminStats(), getAdminReports({ status: "Recibido", pageSize: 5 })])
      setStats(summary)
      setPending(page.items)
      setPendingTotal(page.total)
    } catch (caughtError) {
      setError(messageFor(caughtError, "No fue posible cargar el panel."))
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    // oxlint-disable-next-line react/set-state-in-effect -- El panel se hidrata con consultas remotas al entrar.
    void load()
  }, [load])

  if (isLoading) return <LoadingState label="Cargando el panel de la JDL…" />
  if (error) return <ErrorState error={error} onRetry={load} />
  if (!stats) return null

  const resolved = stats.by_status.Resuelto ?? 0
  const sent = stats.by_status["Enviado a entidades"] ?? 0
  const open = Math.max(stats.total_cases - resolved, 0)
  const overdue = stats.entities.filter((entity) => entity.overdue > 0)
  const overdueTotal = overdue.reduce((total, entity) => total + entity.overdue, 0)

  const titular = [
    pendingTotal > 0 ? `${pendingTotal} ${pendingTotal === 1 ? "expediente espera" : "expedientes esperan"} validación` : "Nada pendiente de validar",
    overdueTotal > 0 ? `${overdueTotal} ${overdueTotal === 1 ? "vencido" : "vencidos"} en ${overdue.map((entity) => entity.entity.code).join(", ")}` : null,
  ].filter(Boolean).join(" · ")

  return (
    <section className="space-y-6">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Metric detail="registrados en la plataforma" label="Expedientes" value={stats.total_cases} />
        <Metric detail="aún requieren seguimiento" label="Activos" value={open} />
        <Metric detail="a una o más entidades" label="Enviados" value={sent} />
        <Metric detail={`SLA configurado: ${stats.sla_dias} días`} label="Resueltos" value={resolved} />
      </div>

      <Ficha className="overflow-hidden" padded={false}>
        <FichaHeader className="border-b px-5 py-4" description={titular} title="Requiere tu atención" />
        {pending.length === 0 ? (
          <p className="px-5 py-6 text-[14px]" style={{ color: t.muted }}>No hay expedientes esperando validación.</p>
        ) : (
          <div className="divide-y" style={{ borderColor: t.rule }}>
            {pending.map((report) => (
              <button className="flex w-full items-center gap-3 px-5 py-3.5 text-left transition hover:bg-black/[.03]" key={report.id} onClick={() => onOpenReport(report.id)} style={{ borderColor: t.rule }} type="button">
                <span className="min-w-0 flex-1">
                  <span className="flex flex-wrap items-center gap-x-2">
                    <Folio value={report.folio} />
                    <Marginalia>{report.category ?? "Sin categoría"}</Marginalia>
                    <Marginalia>{antiguedad(report.created_at)}</Marginalia>
                  </span>
                  <span className="mt-1 block truncate text-[15px] font-medium">{report.description}</span>
                  <span className="mt-1 flex flex-wrap gap-1.5">
                    {report.entities.length > 0 ? report.entities.map((item) => (
                      <Tag key={`${item.entity.code}-${item.status}`} tone={participationTone(item.status)}>{item.entity.code}</Tag>
                    )) : <Tag tone="ink">Sin entidad asignada</Tag>}
                  </span>
                </span>
                <ChevronRight className="size-4 shrink-0" style={{ color: t.muted }} />
              </button>
            ))}
          </div>
        )}
      </Ficha>
    </section>
  )
}

/** Días transcurridos desde que entró el expediente, para la marginalia del Inicio. */
function antiguedad(createdAt: string): string {
  const days = Math.floor((Date.now() - new Date(createdAt).getTime()) / 86_400_000)
  if (days <= 0) return "hoy"
  return `hace ${days} ${days === 1 ? "día" : "días"}`
}

/** Tablero de cumplimiento: el análisis por categoría y por entidad. */
export function AdminDashboard() {
  const [stats, setStats] = useState<AdminStats | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  const loadStats = useCallback(async () => {
    setIsLoading(true)
    setError(null)
    try {
      setStats(await getAdminStats())
    } catch (caughtError) {
      setError(messageFor(caughtError, "No fue posible cargar el tablero."))
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    // oxlint-disable-next-line react/set-state-in-effect -- El tablero se hidrata con una consulta remota al entrar.
    void loadStats()
  }, [loadStats])

  if (isLoading) return <LoadingState label="Cargando métricas del tablero…" />
  if (error) return <ErrorState error={error} onRetry={loadStats} />
  if (!stats) return null

  return (
    <section className="grid gap-4 lg:grid-cols-[.9fr_1.1fr]">
      <Ficha>
        <FichaHeader description="Distribución calculada por el backend." title="Casos por categoría" />
        <div className="mt-5 space-y-4">
          {Object.entries(stats.by_category).length > 0 ? Object.entries(stats.by_category).map(([category, value]) => <CategoryBar category={category} key={category} total={stats.total_cases} value={value} />) : <p className="text-[14px]" style={{ color: t.muted }}>Aún no hay casos clasificados.</p>}
        </div>
      </Ficha>

      <Ficha className="overflow-hidden" padded={false}>
        <FichaHeader className="border-b px-5 py-4" description={`Casos abiertos, vencidos y tiempos de respuesta · SLA configurado: ${stats.sla_dias} días.`} title="Cumplimiento por entidad" />
        {/* En móvil la tabla no cabe sin desplazamiento horizontal: se apila en filas. */}
        <div className="divide-y sm:hidden" style={{ borderColor: t.rule }}>
          {stats.entities.map((entity) => (
            <div className="px-5 py-3" key={entity.entity.code} style={{ borderColor: t.rule }}>
              <p className="text-[13px] font-semibold uppercase tracking-[.08em]" style={{ fontFamily: mono }}>{entity.entity.code}</p>
              <p className="mt-0.5 text-[12px] leading-4" style={{ color: t.muted }}>{entity.entity.name}</p>
              <div className="mt-2 grid grid-cols-4 gap-2">
                {[
                  ['Abiertos', String(entity.open_cases), t.ink],
                  ['Vencidos', String(entity.overdue), entity.overdue > 0 ? t.coral : t.ink],
                  ['Promedio', entity.avg_response_days === null ? '—' : `${entity.avg_response_days.toFixed(1)} d`, t.muted],
                  ['Resueltos', String(entity.resolved), t.forest],
                ].map(([label, value, color]) => (
                  <div key={label}>
                    <Marginalia className="block">{label}</Marginalia>
                    <p className="mt-0.5 text-[15px] font-medium tabular-nums" style={{ color }}>{value}</p>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>

        <div className="hidden overflow-x-auto sm:block">
          <table className="w-full text-left text-[13px]">
            <thead>
              <tr>
                {["Entidad", "Abiertos", "Vencidos", "Promedio", "Resueltos"].map((head) => (
                  <th className="px-3 py-3 font-normal first:pl-5 last:pr-5" key={head}>
                    <Marginalia>{head}</Marginalia>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {stats.entities.map((entity) => (
                <tr className="border-t" key={entity.entity.code} style={{ borderColor: t.rule }}>
                  <td className="px-3 py-3 pl-5 font-semibold uppercase tracking-[.08em]" style={{ fontFamily: mono }} title={entity.entity.name}>{entity.entity.code}</td>
                  <td className="px-3 py-3 tabular-nums">{entity.open_cases}</td>
                  <td className="px-3 py-3 font-semibold tabular-nums" style={{ color: entity.overdue > 0 ? t.coral : t.ink }}>{entity.overdue}</td>
                  <td className="px-3 py-3 tabular-nums" style={{ color: t.muted }}>{entity.avg_response_days === null ? "—" : `${entity.avg_response_days.toFixed(1)} d`}</td>
                  <td className="px-3 py-3 pr-5 tabular-nums" style={{ color: t.forest }}>{entity.resolved}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Ficha>
    </section>
  )
}

export function AdminReports({ openReportId }: { openReportId?: number | null } = {}) {
  const [reports, setReports] = useState<ReportSummary[]>([])
  const [categories, setCategories] = useState<string[]>([])
  const [entities, setEntities] = useState<EntityCatalogItem[]>([])
  const [selected, setSelected] = useState<Report | null>(null)
  const [statusFilter, setStatusFilter] = useState("")
  const [categoryFilter, setCategoryFilter] = useState("")
  const [error, setError] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [isWorking, setIsWorking] = useState(false)
  const [isExporting, setIsExporting] = useState(false)

  const load = useCallback(async () => {
    setIsLoading(true)
    setError(null)
    try {
      const [page, categoryList, entityList] = await Promise.all([
        getAdminReports({ status: statusFilter || undefined, category: categoryFilter || undefined, pageSize: 50 }),
        getAdminCategories(),
        getAdminEntities(),
      ])
      setReports(page.items)
      setCategories(categoryList)
      setEntities(entityList.filter((entity) => entity.is_active))
    } catch (caughtError) {
      setError(messageFor(caughtError, "No fue posible cargar los reportes."))
    } finally {
      setIsLoading(false)
    }
  }, [categoryFilter, statusFilter])

  useEffect(() => {
    // oxlint-disable-next-line react/set-state-in-effect -- Los filtros actualizan la consulta remota de expedientes.
    void load()
  }, [load])

  useEffect(() => {
    // oxlint-disable-next-line react/set-state-in-effect -- Abre el expediente que se eligió en el Inicio.
    if (openReportId) void selectReport(openReportId)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [openReportId])

  const selectReport = async (id: number) => {
    setIsWorking(true)
    setError(null)
    try {
      setSelected(await getAdminReport(id))
    } catch (caughtError) {
      setError(messageFor(caughtError, "No fue posible abrir el expediente."))
    } finally {
      setIsWorking(false)
    }
  }

  const applyReportChange = async (operation: () => Promise<Report>) => {
    setIsWorking(true)
    setError(null)
    try {
      const updated = await operation()
      setSelected(updated)
      await load()
    } catch (caughtError) {
      setError(messageFor(caughtError, "No fue posible actualizar el expediente."))
    } finally {
      setIsWorking(false)
    }
  }

  const sendToEntities = async () => {
    if (!selected) return
    setIsWorking(true)
    setError(null)
    try {
      const result = await sendReportToEntities(selected.id)
      const updated = await getAdminReport(selected.id)
      setSelected(updated)
      await load()
      const failures = result.results.filter((item) => item.email_status === "fallido")
      if (failures.length > 0) setError(`Se registraron ${failures.length} envío(s) fallido(s). Puedes reintentar.`)
    } catch (caughtError) {
      setError(messageFor(caughtError, "No fue posible enviar el expediente."))
    } finally {
      setIsWorking(false)
    }
  }

  const exportSelectedReport = async () => {
    if (!selected) return
    setIsExporting(true)
    setError(null)
    try {
      await downloadReportPdf(selected)
    } catch (caughtError) {
      setError(messageFor(caughtError, "No fue posible generar el PDF del expediente."))
    } finally {
      setIsExporting(false)
    }
  }

  return (
    <section className="space-y-5">
      <Ficha className="flex flex-wrap items-end gap-3" padded>
        <label className="grid gap-1.5">
          <Marginalia>Estado</Marginalia>
          <select className={`${inputSmClass} min-w-44`} onChange={(event) => setStatusFilter(event.target.value)} style={inputStyle} value={statusFilter}>
            <option value="">Todos</option>
            {CASE_STATUSES.map((status) => <option key={status} value={status}>{status}</option>)}
          </select>
        </label>
        <label className="grid gap-1.5">
          <Marginalia>Categoría</Marginalia>
          <select className={`${inputSmClass} min-w-44`} onChange={(event) => setCategoryFilter(event.target.value)} style={inputStyle} value={categoryFilter}>
            <option value="">Todas</option>
            {categories.map((category) => <option key={category} value={category}>{category}</option>)}
          </select>
        </label>
        <Button onClick={() => void load()} size="sm" tone="outline"><RefreshCw className="size-4" /> Actualizar</Button>
      </Ficha>

      {error && <Notice>{error}</Notice>}

      {isLoading ? <LoadingState label="Cargando reportes de la JDL…" /> : (
        <div className="grid gap-5 xl:grid-cols-[minmax(0,1.05fr)_minmax(0,.95fr)]">
          <ReportsTable onSelect={selectReport} reports={reports} selectedId={selected?.id ?? null} />
          <ReportDetail categories={categories} entities={entities} isExporting={isExporting} isWorking={isWorking} onApply={applyReportChange} onExport={() => void exportSelectedReport()} onSend={() => void sendToEntities()} report={selected} />
        </div>
      )}
    </section>
  )
}

function ReportsTable({ reports, selectedId, onSelect }: { reports: ReportSummary[]; selectedId: number | null; onSelect: (id: number) => void }) {
  return (
    <Ficha className="overflow-hidden self-start" padded={false}>
      <FichaHeader aside={<Marginalia>{reports.length} {reports.length === 1 ? "expediente" : "expedientes"}</Marginalia>} className="border-b px-5 py-4" description="Selecciona uno para gestionarlo." title="Expedientes" />
      <div className="divide-y" style={{ borderColor: t.rule }}>
        {reports.length === 0 ? (
          <p className="p-6 text-[14px]" style={{ color: t.muted }}>No hay reportes para estos filtros.</p>
        ) : (
          reports.map((report) => {
            const selected = selectedId === report.id
            return (
              <button className="flex w-full gap-3 px-5 py-4 text-left transition hover:bg-black/[.03]" key={report.id} onClick={() => void onSelect(report.id)} style={{ borderColor: t.rule, background: selected ? t.paper : undefined, boxShadow: selected ? `inset 3px 0 0 ${t.forest}` : undefined }} type="button">
                <span className="min-w-0 flex-1">
                  <span className="flex flex-wrap items-center justify-between gap-2">
                    <span className="flex items-center gap-2">
                      <Folio value={report.folio} />
                      <Tag tone={report.source === "whatsapp" ? "forest" : "muted"}>{report.source === "whatsapp" ? "WhatsApp" : "Web"}</Tag>
                    </span>
                    <CaseTag status={report.status} />
                  </span>
                  <span className="mt-1 block truncate text-[15px] font-medium">{report.description}</span>
                  <span className="mt-1 block text-[12px]" style={{ color: t.muted }}>{report.category ?? "Sin categoría"} · {report.location.label}</span>
                </span>
                <ChevronRight className="mt-2 size-4 shrink-0" style={{ color: t.muted }} />
              </button>
            )
          })
        )}
      </div>
    </Ficha>
  )
}

function ReportDetail({ report, categories, entities, isWorking, isExporting, onApply, onExport, onSend }: { report: Report | null; categories: string[]; entities: EntityCatalogItem[]; isWorking: boolean; isExporting: boolean; onApply: (operation: () => Promise<Report>) => void; onExport: () => void; onSend: () => void }) {
  if (!report) {
    return <EmptyState description="Desde aquí podrás validar la clasificación, enviar a entidades y registrar avances." icon={ClipboardList} title="Selecciona un expediente" />
  }

  return (
    <Ficha className="self-start" hero>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <Folio value={report.folio} />
          <h3 className="mt-1 text-[24px] font-medium leading-tight" style={{ fontFamily: serif }}>Expediente vecinal</h3>
          <p className="mt-1.5 text-[14px] leading-6" style={{ color: t.muted }}>{report.description}</p>
        </div>
        <CaseStamp status={report.status} />
      </div>

      <div className="mt-5 grid gap-4 border-y py-4 sm:grid-cols-2" style={{ borderColor: t.rule }}>
        <Info label="Categoría" value={report.classification.category ?? "Pendiente"} />
        <Info label="Urgencia" value={report.classification.urgency ?? "Pendiente"} />
        <Info label="Clasificación" value={report.classification.status} />
        <Info label="Validación JDL" value={report.validated_at ? "Validada" : "Pendiente"} />
      </div>
      {report.classification.summary && <p className="mt-3 text-[14px] leading-6" style={{ color: t.muted }}>{report.classification.summary}</p>}

      <div className="mt-4 flex flex-wrap gap-2">
        <Button disabled={isWorking || Boolean(report.validated_at)} onClick={() => onApply(() => patchAdminReport(report.id, { validated: true }))} size="xs" tone="forest"><ShieldCheck className="size-3.5" /> {report.validated_at ? "Clasificación validada" : "Validar"}</Button>
        <Button disabled={isWorking} onClick={() => onApply(() => reclassifyAdminReport(report.id))} size="xs" tone="outline"><Sparkles className="size-3.5" /> Reclasificar</Button>
        <Button disabled={isWorking || report.participations.length === 0} onClick={onSend} size="xs"><Mail className="size-3.5" /> Enviar a entidades</Button>
        <Button disabled={isWorking || isExporting} onClick={onExport} size="xs" tone="outline">{isExporting ? <LoaderCircle className="size-3.5 animate-spin" /> : <Download className="size-3.5" />} {isExporting ? "Generando PDF..." : "Exportar PDF"}</Button>
      </div>

      <section className="mt-6 border-t pt-5" style={{ borderColor: t.rule }}>
        <SectionTitle>Participaciones por entidad</SectionTitle>
        <div className="mt-3 space-y-3">
          {report.participations.length === 0 ? <p className="text-[14px]" style={{ color: t.muted }}>Aún no hay entidades asignadas.</p> : report.participations.map((participation) => <ParticipationCard entities={entities} isWorking={isWorking} key={participation.id} onApply={onApply} participation={participation} reportId={report.id} />)}
        </div>
      </section>

      <details className="mt-5 border-t pt-4" style={{ borderColor: t.rule }}>
        <summary className="cursor-pointer text-[14px] font-semibold" style={{ color: t.forest }}>Corregir clasificación</summary>
        <ClassificationEditor categories={categories} isWorking={isWorking} onSave={(patch) => onApply(() => patchAdminReport(report.id, patch))} report={report} />
      </details>
    </Ficha>
  )
}

function ClassificationEditor({ report, categories, isWorking, onSave }: { report: Report; categories: string[]; isWorking: boolean; onSave: (patch: { category?: string; urgency?: string; summary?: string }) => void }) {
  const [category, setCategory] = useState(report.classification.category ?? "")
  const [urgency, setUrgency] = useState(report.classification.urgency ?? "")
  const [summary, setSummary] = useState(report.classification.summary ?? "")

  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    onSave({ category: category || undefined, urgency: urgency || undefined, summary: summary || undefined })
  }

  return (
    <form className="mt-3 grid gap-3" onSubmit={submit}>
      <div className="grid gap-3 sm:grid-cols-2">
        <select aria-label="Categoría" className={inputSmClass} onChange={(event) => setCategory(event.target.value)} style={inputStyle} value={category}>
          <option value="">Sin categoría</option>
          {categories.map((item) => <option key={item} value={item}>{item}</option>)}
        </select>
        <select aria-label="Urgencia" className={inputSmClass} onChange={(event) => setUrgency(event.target.value)} style={inputStyle} value={urgency}>
          <option value="">Sin urgencia</option>
          {["Baja", "Media", "Alta"].map((item) => <option key={item} value={item}>{item}</option>)}
        </select>
      </div>
      <textarea aria-label="Resumen" className={`${textareaClass} min-h-20`} onChange={(event) => setSummary(event.target.value)} placeholder="Resumen para la JDL" style={inputStyle} value={summary} />
      <Button className="w-fit" disabled={isWorking} size="xs" tone="ghost" type="submit">Guardar correcciones</Button>
    </form>
  )
}

function ParticipationCard({ reportId, participation, entities, isWorking, onApply }: { reportId: number; participation: Participation; entities: EntityCatalogItem[]; isWorking: boolean; onApply: (operation: () => Promise<Report>) => void }) {
  const [target, setTarget] = useState("")
  const [responsibility, setResponsibility] = useState("Entidad competente derivada")
  const transitions = VALID_TRANSITIONS[participation.status] ?? []
  const canDerive = participation.status === "Recibida" || participation.status === "En atención"

  return (
    <article className="rounded-lg border p-3.5" style={{ borderColor: t.rule, background: t.paper }}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="min-w-0">
          <p className="text-[15px] font-semibold">{participation.entity.name}</p>
          <p className="mt-0.5 text-[12px]" style={{ color: t.muted }}>{participation.responsibility} · correo {participation.email_status}{participation.days_in_entity !== null ? ` · ${participation.days_in_entity} d en la entidad` : ""}</p>
        </div>
        <Tag tone={participationTone(participation.status, participation.overdue)}>{participation.status}{participation.overdue ? " · vencido" : ""}</Tag>
      </div>
      {transitions.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-2">
          {transitions.map((status) => <Button disabled={isWorking} key={status} onClick={() => onApply(() => updateParticipation(reportId, participation.id, { status }))} size="xs" tone="outline">Marcar {status}</Button>)}
        </div>
      )}
      {canDerive && (
        <div className="mt-3 grid gap-2 sm:grid-cols-[1fr_1fr_auto]">
          <select aria-label={`Derivar ${participation.entity.name} a`} className={`${inputSmClass} !h-9 text-[13px]`} onChange={(event) => setTarget(event.target.value)} style={inputStyle} value={target}>
            <option value="">Derivar a…</option>
            {entities.filter((entity) => entity.code !== participation.entity.code).map((entity) => <option key={entity.code} value={entity.code}>{entity.name}</option>)}
          </select>
          <input aria-label="Responsabilidad de la entidad destino" className={`${inputSmClass} !h-9 text-[13px]`} onChange={(event) => setResponsibility(event.target.value)} style={inputStyle} value={responsibility} />
          <Button disabled={isWorking || !target || responsibility.trim().length < 3} onClick={() => onApply(() => deriveParticipation(reportId, participation.id, { to_entity_code: target, responsibility: responsibility.trim() }))} size="xs" tone="forest">Derivar</Button>
        </div>
      )}
    </article>
  )
}

const CASE_STATUSES = ["Recibido", "En gestión", "Enviado a entidades", "Resuelto"]
const VALID_TRANSITIONS: Record<ParticipationStatus, ParticipationStatus[]> = { Asignada: ["Recibida"], Recibida: ["En atención", "Resuelta"], "En atención": ["Resuelta"], Derivada: [], Resuelta: [] }

function CategoryBar({ category, value, total }: { category: string; value: number; total: number }) {
  const percent = total > 0 ? Math.round((value / total) * 100) : 0
  return (
    <div>
      <div className="mb-1.5 flex justify-between text-[13px]">
        <span className="font-medium">{category}</span>
        <Marginalia>{value} · {percent}%</Marginalia>
      </div>
      <div className="h-1.5 overflow-hidden rounded-sm" style={{ background: t.paper2 }}>
        <div className="h-full rounded-sm" style={{ width: `${percent}%`, background: t.forest }} />
      </div>
    </div>
  )
}

function messageFor(error: unknown, fallback: string): string {
  return error instanceof ApiError ? error.message : fallback
}
