import { useCallback, useEffect, useState } from "react"
import type { FormEvent } from "react"
import { Building2, ChevronDown, ClipboardList, Download, LoaderCircle, RefreshCw, Search } from "lucide-react"

import { ApiError, getReport, type Report } from "@/services/api"
import { downloadReportPdf } from "@/lib/reportPdf"
import { getRememberedFolios, rememberReport } from "@/services/reportService"
import { Button, Marginalia, Tag, inputSmClass, inputStyle, serif, t } from "@/design/tokens"
import { CaseStamp, CaseTag, EmptyState, Ficha, Folio, Info, LoadingState, Notice, formatDateTime, participationTone } from "@/design/ui"

type MyReportsProps = {
  onCreateReport: () => void
}

export function MyReports({ onCreateReport }: MyReportsProps) {
  const [reports, setReports] = useState<Report[]>([])
  const [folio, setFolio] = useState("")
  const [error, setError] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [isSearching, setIsSearching] = useState(false)

  const loadRememberedReports = useCallback(async (showLoading = true) => {
    if (showLoading) {
      setIsLoading(true)
      setError(null)
    }
    const folios = getRememberedFolios()

    try {
      const results = await Promise.all(folios.map(async (savedFolio) => {
        try {
          return await getReport(savedFolio)
        } catch {
          return null
        }
      }))
      setReports(results.filter((report): report is Report => report !== null))
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    // oxlint-disable-next-line react/set-state-in-effect -- La petición asíncrona hidrata el historial persistido.
    void loadRememberedReports(false)
  }, [loadRememberedReports])

  const searchByFolio = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const normalizedFolio = folio.trim()
    if (!normalizedFolio) return

    setIsSearching(true)
    setError(null)
    try {
      const report = await getReport(normalizedFolio)
      rememberReport(report)
      setReports((current) => [report, ...current.filter((item) => item.folio !== report.folio)])
      setFolio("")
    } catch (caughtError) {
      setError(caughtError instanceof ApiError ? caughtError.message : "No fue posible consultar el folio.")
    } finally {
      setIsSearching(false)
    }
  }

  return (
    <section className="space-y-6">
      <Ficha>
        <form className="flex gap-2 sm:gap-3" onSubmit={searchByFolio}>
          <label className="sr-only" htmlFor="report-folio">Folio del reporte</label>
          <div className="relative flex-1">
            <Search className="absolute left-3 top-3 size-4" style={{ color: t.muted }} />
            <input className={`${inputSmClass} pl-9`} id="report-folio" onChange={(event) => setFolio(event.target.value)} placeholder="Consulta un folio, por ejemplo MC-2026-0001" style={inputStyle} value={folio} />
          </div>
          <Button aria-label="Consultar folio" className="shrink-0" disabled={isSearching} size="sm" tone="forest" type="submit">
            {isSearching ? <LoaderCircle className="size-4 animate-spin" /> : <Search className="size-4" />}
            <span className="hidden sm:inline">Consultar</span>
          </Button>
        </form>
      </Ficha>

      {error && <Notice>{error}</Notice>}

      {isLoading ? <LoadingState label="Consultando tus reportes…" /> : reports.length === 0 ? (
        <EmptyState action={<Button onClick={onCreateReport} size="sm">Crear mi primer reporte</Button>} description="Al enviar un reporte o consultar un folio, el expediente aparecerá aquí con su estado real." icon={ClipboardList} title="Todavía no tienes reportes guardados" />
      ) : (
        <div className="space-y-4">
          <div className="flex items-center justify-between gap-3">
            <Marginalia>{reports.length} expediente{reports.length === 1 ? "" : "s"} guardado{reports.length === 1 ? "" : "s"} en este navegador</Marginalia>
            <button className="inline-flex items-center gap-1 text-[13px] font-semibold" onClick={() => void loadRememberedReports()} style={{ color: t.forest }} type="button"><RefreshCw className="size-3.5" /> Actualizar</button>
          </div>
          {reports.map((report) => <ReportCard key={report.folio} report={report} />)}
        </div>
      )}
    </section>
  )
}

// En móvil la ficha se resume en una línea por dato (folio, categoría, dónde está y desde cuándo)
// y el resto se pliega; desde sm se muestra completa.
function useIsWide() {
  const query = "(min-width: 640px)"
  const [wide, setWide] = useState(() => typeof window !== "undefined" && window.matchMedia(query).matches)

  useEffect(() => {
    const media = window.matchMedia(query)
    const update = () => setWide(media.matches)
    media.addEventListener("change", update)
    return () => media.removeEventListener("change", update)
  }, [])

  return wide
}

function formatShortDate(value: string | null): string {
  if (!value) return ""
  return new Intl.DateTimeFormat("es-PA", { day: "numeric", month: "short" }).format(new Date(value)).replace(".", "")
}

/** "En qué entidad está y desde cuándo", con el acrónimo de la entidad para que quepa en una línea. */
function whereIsIt(report: Report): string {
  if (report.status === "Resuelto") return "Caso resuelto"
  const current = report.current_entities[0]
  if (!current) return "En revisión por la JDL"
  const since = formatShortDate(current.since)
  return `${current.entity.code} · ${current.status}${since ? ` · ${since}` : ""}`
}

function ReportCard({ report }: { report: Report }) {
  const [isExporting, setIsExporting] = useState(false)
  const wide = useIsWide()
  const resolved = report.status === "Resuelto"

  const exportPdf = async () => {
    setIsExporting(true)
    try {
      await downloadReportPdf(report)
    } finally {
      setIsExporting(false)
    }
  }

  return (
    <Ficha className="overflow-hidden" padded={false}>
      <details className="group" open={wide}>
        <summary className="block cursor-pointer list-none p-4 sm:cursor-default sm:p-5 [&::-webkit-details-marker]:hidden">
          <span className="flex items-center justify-between gap-2">
            <Folio value={report.folio} />
            <span className="flex shrink-0 items-center gap-2">
              <span className="sm:hidden"><CaseTag status={report.status} /></span>
              <span className="hidden sm:block"><CaseStamp status={report.status} /></span>
              <ChevronDown className="size-4 transition-transform group-open:rotate-180 sm:hidden" style={{ color: t.muted }} />
            </span>
          </span>
          <span className="mt-1 line-clamp-1 text-[17px] font-medium leading-snug sm:line-clamp-2 sm:text-[22px]" style={{ fontFamily: serif }}>{report.description}</span>
          <span className="mt-1 line-clamp-2 text-[13px] leading-5 sm:line-clamp-1" style={{ color: t.muted }}>
            {report.classification.category ?? "Sin clasificar"}
            {" · "}
            <span style={{ color: resolved ? t.forest : t.coral }}>{whereIsIt(report)}</span>
          </span>
        </summary>

        <div className="px-4 pb-4 sm:px-5 sm:pb-5">
          <div className="grid gap-4 border-t pt-4 sm:grid-cols-3" style={{ borderColor: t.rule }}>
            <Info label="Ubicación" value={report.location.label} />
            <Info label="Urgencia" value={report.classification.urgency ?? "Pendiente"} />
            <Info label="Recibido" value={formatDateTime(report.created_at)} />
          </div>

          <div className="mt-4 rounded-lg p-3" style={{ background: t.paper }}>
            <Marginalia className="flex items-center gap-2"><Building2 className="size-3.5" /> Entidades que lo atienden</Marginalia>
            {report.current_entities.length > 0 ? (
              <div className="mt-2 flex flex-wrap gap-2">
                {report.current_entities.map((item) => (
                  <span className="inline-flex items-center gap-2 rounded-md border px-2.5 py-1 text-[13px]" key={`${item.entity.code}-${item.status}`} style={{ background: t.white, borderColor: t.rule }}>
                    {item.entity.name} <Tag tone={participationTone(item.status)}>{item.status}</Tag>
                  </span>
                ))}
              </div>
            ) : (
              <p className="mt-2 text-[14px]" style={{ color: t.muted }}>{resolved ? "Caso resuelto." : "La JDL está preparando el envío a las entidades."}</p>
            )}
          </div>

          {report.reports_count > 1 && <p className="mt-3 text-[13px]" style={{ color: t.forest }}>Este problema reúne {report.reports_count} reportes vecinales.</p>}

          <div className="mt-4 flex flex-wrap items-center gap-3">
            <Button disabled={isExporting} onClick={() => void exportPdf()} size="xs" tone="outline">
              {isExporting ? <LoaderCircle className="size-4 animate-spin" /> : <Download className="size-4" />} {isExporting ? "Generando PDF…" : "Exportar PDF"}
            </Button>
          </div>

          <details className="mt-4">
            <summary className="cursor-pointer text-[14px] font-semibold" style={{ color: t.forest }}>Ver historial del expediente</summary>
            <ol className="mt-3 space-y-3 border-l-[1.5px] pl-4" style={{ borderColor: t.rule }}>
              {report.history.map((entry, index) => (
                <li className="relative text-[14px]" key={`${entry.created_at}-${index}`}>
                  <span className="absolute -left-[1.36rem] top-1.5 size-2.5 rounded-full border-2" style={{ background: t.white, borderColor: t.forest }} />
                  <Marginalia className="block">{formatDateTime(entry.created_at)}{entry.entity ? ` · ${entry.entity}` : ""}</Marginalia>
                  <p className="mt-0.5 font-medium">{entry.event.replaceAll("_", " ")}{entry.previous && entry.new ? ` · ${entry.previous} → ${entry.new}` : ""}</p>
                  {entry.note && <p className="mt-0.5 text-[13px] leading-5" style={{ color: t.muted }}>{entry.note}</p>}
                </li>
              ))}
            </ol>
          </details>
        </div>
      </details>
    </Ficha>
  )
}
