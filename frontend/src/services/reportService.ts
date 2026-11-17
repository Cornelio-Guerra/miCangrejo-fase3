import type { Report } from "@/services/api"

const STORAGE_KEY = "micangrejo.reportFolios"
const LEGACY_STORAGE_KEY = "micangrejo.mockReports"

type StoredReportReference = {
  folio: string
  createdAt: string
}

/** Guarda solo el folio en este navegador; el expediente siempre se consulta a la API. */
export function rememberReport(report: Report): void {
  const current = readReportReferences().filter((item) => item.folio !== report.folio)
  const next = [{ folio: report.folio, createdAt: report.created_at }, ...current].slice(0, 20)
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(next))
}

export function getRememberedFolios(): string[] {
  return readReportReferences().map((item) => item.folio)
}

function readReportReferences(): StoredReportReference[] {
  try {
    const stored = window.localStorage.getItem(STORAGE_KEY)
    if (stored) return normalize(JSON.parse(stored))

    // Conserva los folios creados con la demostración anterior, si existen.
    const legacy = window.localStorage.getItem(LEGACY_STORAGE_KEY)
    return legacy ? normalize(JSON.parse(legacy)) : []
  } catch {
    return []
  }
}

function normalize(value: unknown): StoredReportReference[] {
  if (!Array.isArray(value)) return []

  return value.flatMap((item) => {
    if (typeof item === "string") return [{ folio: item, createdAt: "" }]
    if (item && typeof item === "object" && "folio" in item && typeof item.folio === "string") {
      return [{
        folio: item.folio,
        createdAt: "createdAt" in item && typeof item.createdAt === "string" ? item.createdAt : "",
      }]
    }
    return []
  })
}
