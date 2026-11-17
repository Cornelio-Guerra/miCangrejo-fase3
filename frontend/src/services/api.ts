export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api/v1"

export type WasteSite = {
  id: string
  name: string
  kind: string
  latitude: number
  longitude: number
  description: string | null
  image_url: string | null
}

export type Restaurant = {
  id: string
  name: string
  latitude: number
  longitude: number
  category: string | null
  rating: number | null
  review_count: number | null
  price_range: string | null
  description: string | null
  image_url: string | null
  maps_url: string
}

export type ReportLocation = {
  label: string
  latitude: number | null
  longitude: number | null
}

export type CaseStatus = "Recibido" | "En gestión" | "Enviado a entidades" | "Resuelto"
export type ParticipationStatus = "Asignada" | "Recibida" | "En atención" | "Derivada" | "Resuelta"

export type EntityRef = { code: string; name: string }
export type ClassificationEntity = EntityRef & { responsibility: string }

export type Participation = {
  id: number
  entity: EntityRef
  responsibility: string
  status: ParticipationStatus
  note: string | null
  received_at: string | null
  attention_at: string | null
  derived_at: string | null
  resolved_at: string | null
  derived_to: EntityRef | null
  email_status: "pendiente" | "enviado" | "simulado" | "fallido"
  email_sent_at: string | null
  email_error: string | null
  days_in_entity: number | null
  overdue: boolean
}

export type CurrentEntity = { entity: EntityRef; status: ParticipationStatus; since: string | null }

export type ReportHistory = {
  event: string
  previous: string | null
  new: string | null
  note: string | null
  actor: string
  entity: string | null
  created_at: string
}

export type Classification = {
  category: string | null
  urgency: "Baja" | "Media" | "Alta" | null
  summary: string | null
  status: "pendiente" | "lista" | "provisional" | "fallida"
  source: "gemini" | "reglas" | null
  error: string | null
  entities: ClassificationEntity[]
}

export type Report = {
  id: number
  folio: string
  status: CaseStatus
  description: string
  location: ReportLocation
  photo_url: string | null
  ticket_311: string | null
  source: "web" | "whatsapp"
  reports_count: number
  merged_into: string | null
  classification: Classification
  current_entities: CurrentEntity[]
  participations: Participation[]
  history: ReportHistory[]
  validated_at: string | null
  created_at: string
  updated_at: string
}

export type ReportSummary = {
  id: number
  folio: string
  status: CaseStatus
  category: string | null
  urgency: string | null
  summary: string | null
  description: string
  location: ReportLocation
  photo_url: string | null
  source: "web" | "whatsapp"
  classification_status: Classification["status"]
  entities: CurrentEntity[]
  reports_count: number
  created_at: string
}

export type PaginatedReports = { items: ReportSummary[]; total: number; page: number; page_size: number }
export type EntityCatalogItem = EntityRef & { email: string; is_active: boolean }

export type EntityStats = {
  entity: EntityRef
  open_cases: number
  avg_response_days: number | null
  derived_more_than_once: number
  overdue: number
  resolved: number
}

export type AdminStats = {
  sla_dias: number
  total_cases: number
  by_status: Record<string, number>
  by_category: Record<string, number>
  entities: EntityStats[]
}

export type CreateReportPayload = {
  description: string
  location: ReportLocation
  category?: string
  ticket_311?: string
}

export type AdminReportFilters = {
  status?: string
  category?: string
  urgency?: string
  page?: number
  pageSize?: number
}

export class ApiError extends Error {
  readonly status: number | null

  constructor(message: string, status: number | null = null) {
    super(message)
    this.name = "ApiError"
    this.status = status
  }
}

type WasteSiteResponse = { source: string; total: number; sites: WasteSite[] }
type RestaurantResponse = { source: string; total: number; restaurants: Restaurant[] }
type SignUploadResponse = { upload_url: string; headers: Record<string, string>; path: string }
type SendResult = { participation_id: number; entity: string; email_status: string; error: string | null }
export type SendReportResult = { folio: string; status: CaseStatus; results: SendResult[] }

async function readError(response: Response, fallback: string): Promise<ApiError> {
  try {
    const body = (await response.json()) as { detail?: unknown }
    if (typeof body.detail === "string") return new ApiError(body.detail, response.status)
    if (Array.isArray(body.detail) && typeof body.detail[0]?.msg === "string") return new ApiError(body.detail[0].msg, response.status)
  } catch {
    // El servidor puede responder sin JSON; se usa el mensaje de la interfaz.
  }
  return new ApiError(fallback, response.status)
}

async function requestJson<T>(path: string, init: RequestInit, fallback: string): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, init)
  if (!response.ok) throw await readError(response, fallback)
  return (await response.json()) as T
}

export async function getWasteSites(signal?: AbortSignal): Promise<WasteSiteResponse> {
  return requestJson<WasteSiteResponse>("/waste-sites", { signal }, "No fue posible cargar los puntos comunitarios.")
}

export async function getRestaurants(signal?: AbortSignal): Promise<RestaurantResponse> {
  return requestJson<RestaurantResponse>("/restaurants", { signal }, "No fue posible cargar los restaurantes.")
}

export function getWasteSiteImageUrl(siteId: string): string {
  return `${API_BASE_URL}/waste-sites/${encodeURIComponent(siteId)}/image`
}

export function getRestaurantLogoUrl(restaurantId: string): string {
  return `${API_BASE_URL}/restaurants/${encodeURIComponent(restaurantId)}/logo`
}

export async function uploadReportPhoto(file: File): Promise<string | null> {
  const sign = await fetch(`${API_BASE_URL}/uploads/sign`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ filename: file.name, content_type: file.type, size: file.size }),
  })
  if (sign.status === 503) return null
  if (!sign.ok) throw await readError(sign, "La foto no es válida. Usa JPG, PNG o WEBP de hasta 5 MB.")

  const signedUpload = (await sign.json()) as SignUploadResponse
  try {
    const upload = await fetch(signedUpload.upload_url, { method: "PUT", headers: signedUpload.headers, body: file })
    return upload.ok ? signedUpload.path : null
  } catch {
    return null
  }
}

export async function createReport(payload: CreateReportPayload, photo?: File | null): Promise<Report> {
  const photo_path = photo ? await uploadReportPhoto(photo) : null
  return requestJson<Report>(
    "/reports",
    { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ ...payload, photo_path }) },
    "No fue posible enviar el reporte. Inténtalo de nuevo.",
  )
}

export async function getReport(folio: string, signal?: AbortSignal): Promise<Report> {
  return requestJson<Report>(`/reports/${encodeURIComponent(folio)}`, { signal }, "No encontramos ese folio.")
}

export async function getAdminReports(filters: AdminReportFilters = {}, signal?: AbortSignal): Promise<PaginatedReports> {
  const query = new URLSearchParams()
  if (filters.status) query.set("status", filters.status)
  if (filters.category) query.set("category", filters.category)
  if (filters.urgency) query.set("urgency", filters.urgency)
  query.set("page", String(filters.page ?? 1))
  query.set("page_size", String(filters.pageSize ?? 20))
  return requestJson<PaginatedReports>(`/admin/reports?${query.toString()}`, { signal }, "No fue posible cargar los reportes.")
}

export async function getAdminReport(id: number, signal?: AbortSignal): Promise<Report> {
  return requestJson<Report>(`/admin/reports/${id}`, { signal }, "No fue posible cargar el expediente.")
}

export async function getAdminStats(signal?: AbortSignal): Promise<AdminStats> {
  return requestJson<AdminStats>("/admin/stats", { signal }, "No fue posible cargar las métricas.")
}

export async function getAdminCategories(signal?: AbortSignal): Promise<string[]> {
  return requestJson<string[]>("/admin/categories", { signal }, "No fue posible cargar las categorías.")
}

export async function getAdminEntities(signal?: AbortSignal): Promise<EntityCatalogItem[]> {
  return requestJson<EntityCatalogItem[]>("/admin/entities", { signal }, "No fue posible cargar las entidades.")
}

export async function patchAdminReport(id: number, patch: { validated?: boolean; category?: string; urgency?: string; summary?: string; ticket_311?: string }): Promise<Report> {
  return requestJson<Report>(
    `/admin/reports/${id}`,
    { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(patch) },
    "No fue posible actualizar el expediente.",
  )
}

export async function reclassifyAdminReport(id: number): Promise<Report> {
  return requestJson<Report>(`/admin/reports/${id}/classify`, { method: "POST" }, "No fue posible reclasificar el expediente.")
}

export async function updateParticipation(id: number, participationId: number, patch: { status?: ParticipationStatus; note?: string }): Promise<Report> {
  return requestJson<Report>(
    `/admin/reports/${id}/entities/${participationId}`,
    { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(patch) },
    "No fue posible actualizar la participación.",
  )
}

export async function deriveParticipation(id: number, participationId: number, payload: { to_entity_code: string; responsibility: string; note?: string }): Promise<Report> {
  return requestJson<Report>(
    `/admin/reports/${id}/entities/${participationId}/derive`,
    { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) },
    "No fue posible derivar el caso.",
  )
}

export async function sendReportToEntities(id: number): Promise<SendReportResult> {
  return requestJson<SendReportResult>(`/admin/reports/${id}/send`, { method: "POST" }, "No fue posible enviar el expediente a las entidades.")
}
